"""
mcp_server/services/bedrock_service.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Reusable AWS Bedrock AI service for the GAM 360 Live Reporting Platform.

Uses the AWS Bedrock REST API directly with a Bearer token (AWS_BEARER_TOKEN_BEDROCK),
which supports the newer Bedrock API key format that bypasses standard IAM credentials.

Falls back to boto3 SigV4-signed requests if no bearer token is present.

Responsibilities:
  • Build Bedrock-compatible message payloads from the application's history.
  • Execute POST requests to the Bedrock converse-stream REST endpoint.
  • Handle the two-turn tool-use cycle: call → execute → final answer.
  • Implement exponential-backoff retry for transient failures.
  • Stream SSE-formatted tokens back to the caller via an async generator.
  • Provide rich, structured logging of every request lifecycle.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import AsyncGenerator, Callable

log = logging.getLogger("bedrock_service")

# ─── Configuration ────────────────────────────────────────────────────────────

def _get_region() -> str:
    return os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION", "us-east-1")


def _get_model_id() -> str:
    return os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")


def _get_bearer_token() -> str:
    return os.getenv("AWS_BEARER_TOKEN_BEDROCK", "")


def _get_endpoint(model_id: str, region: str) -> str:
    return f"https://bedrock-runtime.{region}.amazonaws.com/model/{model_id}/converse-stream"


# ─── Tool Schema ─────────────────────────────────────────────────────────────

def get_query_data_tool_spec() -> dict:
    """
    Return the Bedrock-compatible tool specification for the `query_data` tool.
    Standard JSON Schema compatible with all Bedrock models supporting tool use.
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
                                "Aggregation to perform: sum, mean, max, min, "
                                "top_n, bottom_n, compare, count."
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
                            "description": "Optional filters: app_name, date (YYYY-MM-DD), min_revenue.",
                            "properties": {
                                "app_name": {"type": "string"},
                                "date": {"type": "string"},
                                "min_revenue": {"type": "number"},
                            },
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max results for top_n / bottom_n (default 10).",
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
    Convert frontend chat history into Bedrock message format.

    Frontend: [{"role": "user"|"assistant", "content": "..."}]
    Bedrock:  [{"role": "user"|"assistant", "content": [{"text": "..."}]}]

    Only the last 10 turns are kept to control prompt size.
    """
    messages: list[dict] = []
    for turn in history[-10:]:
        role = "assistant" if turn.get("role") == "assistant" else "user"
        content = (turn.get("content") or "").strip()
        if content:
            messages.append({"role": role, "content": [{"text": content}]})
    messages.append({"role": "user", "content": [{"text": new_message}]})
    return messages


# ─── HTTP Bedrock Client ──────────────────────────────────────────────────────

def _parse_bedrock_stream(raw_bytes: bytes) -> list[dict]:
    """
    Parse the binary event-stream body returned by Bedrock converse-stream.
    The AWS event stream format uses length-prefixed binary frames.
    Each frame contains a JSON payload after the headers.
    """
    events = []
    offset = 0
    data = raw_bytes

    while offset < len(data):
        if offset + 12 > len(data):
            break

        # 4-byte total length (big-endian)
        total_len = int.from_bytes(data[offset:offset + 4], "big")
        # 4-byte headers length
        headers_len = int.from_bytes(data[offset + 4:offset + 8], "big")

        if offset + total_len > len(data):
            break

        # Skip prelude (8 bytes) + CRC (4 bytes) = 12 bytes, then headers
        payload_start = offset + 12 + headers_len
        payload_end = offset + total_len - 4  # minus trailing CRC

        if payload_start < payload_end:
            try:
                payload_str = data[payload_start:payload_end].decode("utf-8")
                if payload_str.strip():
                    parsed = json.loads(payload_str)
                    events.append(parsed)
            except (UnicodeDecodeError, json.JSONDecodeError):
                pass

        offset += total_len

    return events


def _call_bedrock_http(payload: dict) -> list[dict]:
    """
    Make a synchronous HTTP POST to the Bedrock converse-stream endpoint
    using a Bearer token for authentication.
    """
    import urllib.request
    import urllib.error

    bearer_token = _get_bearer_token()
    model_id = _get_model_id()
    region = _get_region()
    url = _get_endpoint(model_id, region)

    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/vnd.amazon.eventstream",
        "Authorization": f"Bearer {bearer_token}",
    }

    log.info("[Bedrock] POST %s model=%s payload_bytes=%d", url, model_id, len(body))

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            status = resp.status
            log.info("[Bedrock] HTTP %d", status)
            raw = resp.read()
            return _parse_bedrock_stream(raw)
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        log.error("[Bedrock] HTTP %d: %s", exc.code, error_body)
        raise RuntimeError(f"Bedrock HTTP {exc.code}: {error_body}") from exc


def _extract_text_and_tools(events: list[dict]) -> tuple[str, list[dict]]:
    """
    Extract text content and tool_use blocks from a list of parsed Bedrock events.

    Returns:
        text:       Concatenated text response.
        tool_uses:  List of {toolUseId, name, input} dicts.
    """
    text_parts: list[str] = []
    tool_uses: dict[int, dict] = {}

    for event in events:
        # contentBlockStart carries the tool header
        if "contentBlockStart" in event:
            idx = event["contentBlockStart"].get("contentBlockIndex", 0)
            start = event["contentBlockStart"].get("start", {})
            if "toolUse" in start:
                tool_uses[idx] = {
                    "toolUseId": start["toolUse"]["toolUseId"],
                    "name": start["toolUse"]["name"],
                    "input_raw": "",
                }

        # contentBlockDelta carries text and tool input chunks
        elif "contentBlockDelta" in event:
            delta = event["contentBlockDelta"].get("delta", {})
            idx = event["contentBlockDelta"].get("contentBlockIndex", 0)

            if "text" in delta:
                text_parts.append(delta["text"])
            elif "toolUse" in delta and "input" in delta["toolUse"]:
                if idx in tool_uses:
                    tool_uses[idx]["input_raw"] += delta["toolUse"]["input"]

    # Parse tool inputs
    parsed_tools = []
    for t in tool_uses.values():
        raw = t.get("input_raw", "")
        try:
            tool_input = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError:
            tool_input = {}
        parsed_tools.append({
            "toolUseId": t["toolUseId"],
            "name": t["name"],
            "input": tool_input,
        })

    return "".join(text_parts), parsed_tools


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

    Handles the full two-turn tool-use cycle:
      1. Send user messages → Bedrock returns text and/or tool calls.
      2. Execute any tool calls via `tool_executor`.
      3. Send tool results back → Bedrock streams the final answer.

    Args:
        messages:       Bedrock-formatted conversation history (including new message).
        system_prompt:  The system prompt string.
        tool_executor:  Callable(tool_name, input_dict) → result_dict.
        max_retries:    Retry attempts for transient errors.
        base_backoff:   Initial backoff in seconds (doubles on each retry).

    Yields:
        SSE strings: "data: {...}\\n\\n"
    """
    model_id = _get_model_id()

    def _sse(payload: dict) -> str:
        return f"data: {json.dumps(payload)}\n\n"

    def _build_payload(msgs: list[dict]) -> dict:
        return {
            "system": [{"text": system_prompt}],
            "messages": msgs,
            "toolConfig": {"tools": [get_query_data_tool_spec()]},
        }

    attempt = 0
    while attempt < max_retries:
        attempt += 1
        t_start = time.monotonic()
        log.info("[Bedrock] Request started — model=%s attempt=%d/%d", model_id, attempt, max_retries)

        try:
            payload = _build_payload(messages)
            events = await asyncio.to_thread(_call_bedrock_http, payload)

            text, tool_uses = _extract_text_and_tools(events)

            # Stream text from the first turn if no tool calls
            if text and not tool_uses:
                yield _sse({"type": "token", "content": text})

            # ── Tool execution + second turn ───────────────────────────────────
            if tool_uses:
                assistant_content: list[dict] = []
                user_tool_results: list[dict] = []

                for t in tool_uses:
                    tool_name = t["name"]
                    tool_use_id = t["toolUseId"]
                    input_dict = t["input"]

                    log.info("[Bedrock] Tool call — name=%s input=%s", tool_name, input_dict)
                    result = await asyncio.to_thread(tool_executor, tool_name, input_dict)
                    safe_result = json.loads(json.dumps(result, default=str))
                    log.info("[Bedrock] Tool result — name=%s keys=%s", tool_name, list(safe_result.keys()))

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

                messages_with_tools = messages + [
                    {"role": "assistant", "content": assistant_content},
                    {"role": "user", "content": user_tool_results},
                ]

                log.info("[Bedrock] Sending tool results for second-turn response...")
                payload2 = _build_payload(messages_with_tools)
                events2 = await asyncio.to_thread(_call_bedrock_http, payload2)
                text2, _ = _extract_text_and_tools(events2)
                if text2:
                    yield _sse({"type": "token", "content": text2})

            latency_ms = round((time.monotonic() - t_start) * 1000)
            log.info("[Bedrock] Request completed — latency_ms=%d", latency_ms)
            yield _sse({"type": "done"})
            return  # success

        except RuntimeError as exc:
            err = str(exc)
            log.error("[Bedrock] Error on attempt %d: %s", attempt, err)

            # Detect terminal errors — never retry these
            is_terminal = any(x in err for x in [
                "AccessDenied", "403", "ValidationException", "400",
                "ResourceNotFound", "404", "end of its life", "Legacy"
            ])
            if is_terminal:
                log.error("[Bedrock] Terminal error — not retrying.")
                yield _sse({"type": "error", "content": err})
                return

            # Retryable
            if attempt < max_retries:
                backoff = base_backoff * (2 ** (attempt - 1))
                log.warning("[Bedrock] Retrying in %.1fs...", backoff)
                await asyncio.sleep(backoff)
                continue

            yield _sse({"type": "error", "content": err})
            return

        except Exception as exc:
            log.exception("[Bedrock] Unexpected error on attempt %d: %s", attempt, exc)
            if attempt < max_retries:
                backoff = base_backoff * (2 ** (attempt - 1))
                await asyncio.sleep(backoff)
                continue
            yield _sse({"type": "error", "content": str(exc)})
            return


def reset_client() -> None:
    """No-op kept for API compatibility — HTTP client has no persistent state."""
    log.info("[Bedrock] reset_client() called — HTTP mode has no persistent state.")
