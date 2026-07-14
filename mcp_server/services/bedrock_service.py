"""
mcp_server/services/bedrock_service.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Reusable AWS Bedrock AI service for the GAM 360 Live Reporting Platform.

This service is the single integration point for all AI functionality.
The rest of the application imports only this module — no AI SDK code
lives anywhere else.

Responsibilities:
  • Initialise and reuse a single boto3 bedrock-runtime client.
  • Build Bedrock-compatible message payloads from the application's
    conversation history.
  • Execute `converse_stream` requests with tool-use support.
  • Handle the two-turn tool-use cycle: call → execute → final answer.
  • Implement exponential-backoff retry for transient AWS failures.
  • Stream SSE-formatted tokens back to the caller via an async generator.
  • Provide rich, structured logging of every request lifecycle.

AWS Credentials are read exclusively from environment variables:
  AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION (or AWS_DEFAULT_REGION),
  BEDROCK_MODEL_ID.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import AsyncGenerator, Callable

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

log = logging.getLogger("bedrock_service")

# ─── Module-level client (reused across requests) ────────────────────────────

_bedrock_client = None
_client_lock = asyncio.Lock()


def _get_region() -> str:
    """Return the AWS region, preferring AWS_REGION then AWS_DEFAULT_REGION."""
    return os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION", "us-east-1")


def _build_client() -> object:
    """
    Construct a thread-safe boto3 Bedrock Runtime client.
    Credentials are automatically sourced from the environment.
    """
    region = _get_region()
    log.info("[Bedrock] Initialising boto3 bedrock-runtime client (region=%s)", region)
    return boto3.client(
        "bedrock-runtime",
        region_name=region,
        config=Config(
            connect_timeout=10,
            read_timeout=60,
            retries={"mode": "standard", "max_attempts": 1},  # we handle retries manually
        ),
    )


def get_bedrock_client() -> object:
    """
    Return the module-level Bedrock client, creating it on first call.
    Thread-safe for synchronous callers (the async lock is for async context).
    """
    global _bedrock_client
    if _bedrock_client is None:
        _bedrock_client = _build_client()
    return _bedrock_client


def reset_client() -> None:
    """Force re-initialisation of the Bedrock client (e.g., after credential rotation)."""
    global _bedrock_client
    _bedrock_client = None
    log.info("[Bedrock] Client reset — will reinitialise on next request.")


# ─── Tool Schema ─────────────────────────────────────────────────────────────

def get_query_data_tool_spec() -> dict:
    """
    Return the Bedrock-compatible tool specification for the `query_data` tool.
    Uses standard JSON Schema so it is compatible with any Bedrock model that
    supports tool use (Anthropic Claude 3+, Amazon Titan, etc.).
    """
    return {
        "toolSpec": {
            "name": "query_data",
            "description": (
                "Query the current dashboard's GAM data with whitelisted aggregations. "
                "Use this for comparisons, filtering, sorting, or detailed breakdowns "
                "not already in the data summary."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "operation": {
                            "type": "string",
                            "description": (
                                "The aggregation operation to perform: "
                                "sum, mean, max, min, top_n, bottom_n, compare, count."
                            ),
                        },
                        "dimension": {
                            "type": "string",
                            "description": "Dimension to group by: 'app' (ad unit) or 'date' (calendar day).",
                        },
                        "metric": {
                            "type": "string",
                            "description": (
                                "Metric to aggregate: revenue, impressions, clicks, "
                                "ad_requests, ecpm, ctr, fill_rate."
                            ),
                        },
                        "filters": {
                            "type": "object",
                            "description": (
                                "Optional filters: app_name (substring match), "
                                "date (exact YYYY-MM-DD), min_revenue (number)."
                            ),
                            "properties": {
                                "app_name": {"type": "string"},
                                "date": {"type": "string"},
                                "min_revenue": {"type": "number"},
                            },
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max number of results for top_n / bottom_n (default 10).",
                        },
                    },
                    "required": ["operation"],
                }
            },
        }
    }


# ─── Message Builder ──────────────────────────────────────────────────────────

def build_bedrock_messages(history: list[dict], new_message: str) -> list[dict]:
    """
    Convert the frontend chat history into Bedrock's expected message format.

    Frontend format:  [{"role": "user"|"assistant", "content": "..."}]
    Bedrock format:   [{"role": "user"|"assistant", "content": [{"text": "..."}]}]

    Only the last 10 history turns are included to keep prompt size manageable.

    Args:
        history:     Frontend chat history (newest last).
        new_message: The user's current message to append.

    Returns:
        List of Bedrock-formatted message dicts.
    """
    messages: list[dict] = []

    for turn in history[-10:]:
        role = "assistant" if turn.get("role") == "assistant" else "user"
        content = (turn.get("content") or "").strip()
        if content:
            messages.append({"role": role, "content": [{"text": content}]})

    messages.append({"role": "user", "content": [{"text": new_message}]})
    return messages


# ─── Retry Helper ────────────────────────────────────────────────────────────

# AWS error codes that are safe to retry with backoff
_RETRYABLE_CODES = {
    "ThrottlingException",
    "ServiceUnavailableException",
    "RequestTimeout",
    "InternalServerException",
    "ModelStreamErrorException",
}

# AWS error codes that should NEVER be retried
_TERMINAL_CODES = {
    "AccessDeniedException",
    "ValidationException",
    "ResourceNotFoundException",
    "ModelNotReadyException",
    "ModelErrorException",
}


def _is_retryable(exc: ClientError) -> bool:
    code = exc.response.get("Error", {}).get("Code", "")
    return code in _RETRYABLE_CODES


def _is_terminal(exc: ClientError) -> bool:
    code = exc.response.get("Error", {}).get("Code", "")
    return code in _TERMINAL_CODES


# ─── Core Streaming Generator ─────────────────────────────────────────────────

async def stream_bedrock_response(
    messages: list[dict],
    system_prompt: str,
    tool_executor: Callable[[str, dict], dict],
    *,
    max_retries: int = 3,
    base_backoff: float = 1.0,
) -> AsyncGenerator[str, None]:
    """
    Stream an AI response from AWS Bedrock as SSE-formatted tokens.

    This function handles the full two-turn tool-use cycle:
      1. Send user messages → Bedrock returns text and/or tool calls.
      2. Execute any tool calls via `tool_executor`.
      3. Send tool results back → Bedrock streams the final answer.

    Args:
        messages:       Bedrock-formatted conversation history (including new message).
        system_prompt:  The system prompt string injected at the start.
        tool_executor:  Callable(tool_name, input_dict) → result_dict.
                        Executed synchronously inside asyncio.to_thread.
        max_retries:    Number of retry attempts for transient AWS errors.
        base_backoff:   Initial backoff in seconds (doubles on each retry).

    Yields:
        SSE-formatted strings: "data: {...}\\n\\n"
        Token events:   {"type": "token", "content": "..."}
        Done event:     {"type": "done"}
        Error event:    {"type": "error", "content": "..."}
    """
    model_id = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0")
    tool_config = {"tools": [get_query_data_tool_spec()]}

    def _sse(payload: dict) -> str:
        return f"data: {json.dumps(payload)}\n\n"

    def _call(msgs: list[dict]) -> dict:
        """Synchronous Bedrock call — runs in a thread pool."""
        client = get_bedrock_client()
        return client.converse_stream(
            modelId=model_id,
            messages=msgs,
            system=[{"text": system_prompt}],
            toolConfig=tool_config,
        )

    # ── Retry loop ────────────────────────────────────────────────────────────
    attempt = 0
    while attempt < max_retries:
        attempt += 1
        t_start = time.monotonic()
        prompt_chars = sum(len(m["content"][0].get("text", "")) for m in messages if m["content"])
        log.info(
            "[Bedrock] Request started — model=%s attempt=%d/%d prompt_chars=%d",
            model_id, attempt, max_retries, prompt_chars,
        )

        try:
            response = await asyncio.to_thread(_call, messages)

            # ── First-turn stream processing ──────────────────────────────────
            tool_uses: dict[int, dict] = {}  # content_block_index → tool_use data

            for event in response.get("stream"):
                if "contentBlockStart" in event:
                    start_data = event["contentBlockStart"]["start"]
                    idx = event["contentBlockStart"]["contentBlockIndex"]
                    if "toolUse" in start_data:
                        tool_uses[idx] = {
                            "toolUseId": start_data["toolUse"]["toolUseId"],
                            "name": start_data["toolUse"]["name"],
                            "input_raw": "",
                        }

                elif "contentBlockDelta" in event:
                    delta = event["contentBlockDelta"]["delta"]
                    idx = event["contentBlockDelta"]["contentBlockIndex"]

                    if "text" in delta:
                        yield _sse({"type": "token", "content": delta["text"]})

                    elif "toolUse" in delta and "input" in delta["toolUse"]:
                        if idx in tool_uses:
                            tool_uses[idx]["input_raw"] += delta["toolUse"]["input"]

            # ── Tool execution + second-turn ───────────────────────────────────
            if tool_uses:
                assistant_content: list[dict] = []
                user_tool_results: list[dict] = []

                for idx, t in tool_uses.items():
                    tool_name = t["name"]
                    tool_use_id = t["toolUseId"]
                    raw_input = t.get("input_raw", "")

                    try:
                        input_dict = json.loads(raw_input) if raw_input.strip() else {}
                    except json.JSONDecodeError:
                        input_dict = {}

                    log.info("[Bedrock] Tool call — name=%s input=%s", tool_name, input_dict)

                    # Execute the tool in a thread (it's synchronous Pandas work)
                    result = await asyncio.to_thread(tool_executor, tool_name, input_dict)
                    safe_result = json.loads(json.dumps(result, default=str))

                    log.info("[Bedrock] Tool result — name=%s result_keys=%s", tool_name, list(safe_result.keys()))

                    assistant_content.append({
                        "toolUse": {
                            "toolUseId": tool_use_id,
                            "name": tool_name,
                            "input": input_dict,
                        }
                    })
                    user_tool_results.append({
                        "toolResult": {
                            "toolUseId": tool_use_id,
                            "content": [{"json": safe_result}],
                            "status": "success",
                        }
                    })

                # Append tool turn to conversation
                messages_with_tools = messages + [
                    {"role": "assistant", "content": assistant_content},
                    {"role": "user", "content": user_tool_results},
                ]

                log.info("[Bedrock] Sending tool results for second-turn response...")
                second_response = await asyncio.to_thread(_call, messages_with_tools)

                for event in second_response.get("stream"):
                    if "contentBlockDelta" in event:
                        delta = event["contentBlockDelta"]["delta"]
                        if "text" in delta:
                            yield _sse({"type": "token", "content": delta["text"]})

            latency_ms = round((time.monotonic() - t_start) * 1000)
            log.info("[Bedrock] Request completed — latency_ms=%d", latency_ms)
            yield _sse({"type": "done"})
            return  # success — exit retry loop

        except ClientError as exc:
            err_code = exc.response.get("Error", {}).get("Code", "Unknown")
            err_msg = exc.response.get("Error", {}).get("Message", str(exc))
            log.error("[Bedrock] ClientError — code=%s message=%s attempt=%d", err_code, err_msg, attempt)

            if _is_terminal(exc):
                log.error("[Bedrock] Terminal error — will not retry.")
                yield _sse({"type": "error", "content": f"AWS Bedrock Error ({err_code}): {err_msg}"})
                return

            if _is_retryable(exc) and attempt < max_retries:
                backoff = base_backoff * (2 ** (attempt - 1))
                log.warning("[Bedrock] Retryable error — backing off %.1fs before retry %d/%d", backoff, attempt + 1, max_retries)
                await asyncio.sleep(backoff)
                continue

            # Last attempt failed
            yield _sse({"type": "error", "content": f"AWS Bedrock Error ({err_code}): {err_msg}"})
            return

        except Exception as exc:
            log.exception("[Bedrock] Unexpected error on attempt %d: %s", attempt, exc)
            if attempt < max_retries:
                backoff = base_backoff * (2 ** (attempt - 1))
                log.warning("[Bedrock] Retrying in %.1fs...", backoff)
                await asyncio.sleep(backoff)
                continue
            yield _sse({"type": "error", "content": str(exc)})
            return
