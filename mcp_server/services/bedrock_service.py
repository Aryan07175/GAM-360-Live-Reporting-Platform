"""
mcp_server/services/bedrock_service.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Reusable AWS Bedrock AI service for the GAM 360 Live Reporting Platform.

Uses the AWS Bedrock REST API (converse endpoint — JSON, not binary event stream)
with a Bearer token (AWS_BEARER_TOKEN_BEDROCK).

The response is received as a complete JSON object, then streamed
character-by-character to the frontend as SSE tokens — preserving the
live typing effect without requiring complex binary stream parsing.

Tool use (two-turn cycle) is fully supported.
tool_executor is now an ASYNC callable: async def executor(name, input) -> dict
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import urllib.request
import urllib.error
from typing import AsyncGenerator, Callable, Awaitable

log = logging.getLogger("bedrock_service")

# ─── Configuration ────────────────────────────────────────────────────────────

def _get_region() -> str:
    return os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION", "us-east-1")


def _get_model_id() -> str:
    return os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")


def _get_bearer_token() -> str:
    return os.getenv("AWS_BEARER_TOKEN_BEDROCK", "")


def _get_endpoint(model_id: str, region: str) -> str:
    """Use the plain /converse endpoint (returns clean JSON, no binary stream)."""
    return f"https://bedrock-runtime.{region}.amazonaws.com/model/{model_id}/converse"


# ─── Tool Schemas ─────────────────────────────────────────────────────────────

def get_query_gam_data_tool_spec() -> dict:
    """
    Bedrock tool spec for query_gam_data.

    This tool goes DIRECTLY to the live Google Ad Manager SOAP API for exactly
    the requested date range and dimension — it is completely independent of
    whatever the dashboard currently has loaded.

    The model MUST call this tool for any question involving a time period
    or breakdown by app / website / ad unit.
    """
    return {
        "toolSpec": {
            "name": "query_gam_data",
            "description": (
                "Fetch LIVE data directly from Google Ad Manager for any date range, "
                "dimension, and metric. "
                "ALWAYS call this tool when the user asks about revenue, impressions, clicks, "
                "eCPM, CTR, fill rate, or ad requests for any time period "
                "(today, yesterday, last 7/30/90 days, this month, last month, "
                "this year, last year, MTD, YTD, or any custom date range). "
                "NEVER answer time-based or breakdown questions from memory — always "
                "call this tool first and use only the numbers it returns."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "start_date": {
                            "type": "string",
                            "description": (
                                "Start date in YYYY-MM-DD format. "
                                "Compute the actual calendar date from phrases like "
                                "'today', 'yesterday', 'last 30 days', 'last year', 'MTD', 'YTD'. "
                                "Use the reference dates provided in the system prompt."
                            ),
                        },
                        "end_date": {
                            "type": "string",
                            "description": "End date in YYYY-MM-DD format (inclusive).",
                        },
                        "dimension": {
                            "type": "string",
                            "enum": ["none", "app", "website", "ad_unit"],
                            "description": (
                                "How to break down the result. "
                                "'none' = network totals only. "
                                "'app' = breakdown by mobile app / ad unit name. "
                                "'website' = breakdown by website domain. "
                                "'ad_unit' = breakdown by ad unit name (same as app)."
                            ),
                        },
                        "metric": {
                            "type": "string",
                            "enum": ["revenue", "impressions", "clicks", "ctr", "ecpm", "fill_rate", "ad_requests"],
                            "description": (
                                "Primary metric to report. "
                                "revenue = total ad revenue in USD. "
                                "impressions = total ad impressions served. "
                                "clicks = total ad clicks. "
                                "ctr = click-through rate (%). "
                                "ecpm = effective CPM in USD. "
                                "fill_rate = impression fill rate (%). "
                                "ad_requests = total ad requests."
                            ),
                        },
                        "channel": {
                            "type": "string",
                            "enum": ["all", "ad_server", "adsense", "ad_exchange"],
                            "description": (
                                "Demand channel filter. "
                                "'all' = unified view (Ad Server + AdSense + Ad Exchange totals). "
                                "'ad_server' = direct-sold only. "
                                "'adsense' = AdSense backfill only. "
                                "'ad_exchange' = programmatic/Ad Exchange only. "
                                "Default: 'all'."
                            ),
                        },
                    },
                    "required": ["start_date", "end_date"],
                }
            },
        }
    }


def get_query_data_tool_spec() -> dict:
    """Bedrock-compatible tool specification for the query_data tool (in-session aggregations)."""
    return {
        "toolSpec": {
            "name": "query_data",
            "description": (
                "Aggregate or filter the CURRENT dashboard session's already-loaded data. "
                "Use this only for follow-up questions about the same date range that is "
                "already displayed on the dashboard (comparisons, sorting, filtering). "
                "For ANY question involving a specific time period that might differ from "
                "the current dashboard view, use query_gam_data instead."
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


# ─── HTTP Bedrock Client (JSON converse endpoint) ─────────────────────────────

def _call_bedrock(payload: dict) -> dict:
    """
    Make a synchronous HTTP POST to the Bedrock /converse endpoint.
    Returns the full parsed JSON response dict.
    Raises RuntimeError with a descriptive message on failure.
    """
    bearer_token = _get_bearer_token()
    model_id = _get_model_id()
    region = _get_region()
    url = _get_endpoint(model_id, region)

    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {bearer_token}",
    }

    log.info("[Bedrock] POST %s model=%s bytes=%d", url, model_id, len(body))

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            log.info("[Bedrock] HTTP %d — response %d bytes", resp.status, len(raw))
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        log.error("[Bedrock] HTTP %d — %s", exc.code, error_body)
        raise RuntimeError(f"Bedrock HTTP {exc.code}: {error_body}") from exc
    except Exception as exc:
        log.error("[Bedrock] Request failed: %s", exc)
        raise RuntimeError(f"Bedrock request failed: {exc}") from exc


def _extract_text_and_tools(response: dict) -> tuple[str, list[dict]]:
    """
    Extract the assistant's text reply and any tool_use blocks
    from a Bedrock /converse JSON response.

    Returns:
        text:       The assistant's text response (may be empty if tools used).
        tool_uses:  List of {toolUseId, name, input} dicts.
    """
    output = response.get("output", {})
    message = output.get("message", {})
    content_blocks = message.get("content", [])

    text_parts: list[str] = []
    tool_uses: list[dict] = []

    for block in content_blocks:
        if "text" in block:
            text_parts.append(block["text"])
        elif "toolUse" in block:
            tool_uses.append({
                "toolUseId": block["toolUse"]["toolUseId"],
                "name": block["toolUse"]["name"],
                "input": block["toolUse"].get("input", {}),
            })

    return "".join(text_parts), tool_uses


# ─── Core Streaming Generator ─────────────────────────────────────────────────

async def stream_bedrock_response(
    messages: list[dict],
    system_prompt: str,
    tool_executor: Callable[[str, dict], Awaitable[dict]],
    *,
    max_retries: int = 3,
    base_backoff: float = 1.0,
) -> AsyncGenerator[str, None]:
    """
    Fetch an AI response from AWS Bedrock and stream it as SSE tokens.

    Uses /converse (non-streaming JSON) internally, then yields the text
    word-by-word as SSE events to preserve the live typing effect on the
    frontend without needing binary event-stream parsing.

    Handles the full two-turn tool-use cycle:
      1. Send messages → Bedrock returns text and/or tool calls.
      2. Execute any tool calls via `tool_executor` (async).
      3. Send tool results → Bedrock returns the final text answer.

    tool_executor MUST be an async callable: async def(name, input) -> dict

    Yields SSE strings: "data: {...}\\n\\n"
    """
    model_id = _get_model_id()

    def _sse(payload: dict) -> str:
        return f"data: {json.dumps(payload)}\n\n"

    def _build_payload(msgs: list[dict]) -> dict:
        return {
            "system": [{"text": system_prompt}],
            "messages": msgs,
            "toolConfig": {
                "tools": [
                    get_query_gam_data_tool_spec(),   # PRIMARY: live GAM queries
                    get_query_data_tool_spec(),        # SECONDARY: in-session aggregations
                ]
            },
        }

    async def _stream_text(text: str):
        """Yield the text split into small chunks to simulate streaming."""
        words = text.split(" ")
        for i, word in enumerate(words):
            chunk = word if i == 0 else " " + word
            if chunk:
                yield _sse({"type": "token", "content": chunk})
                await asyncio.sleep(0.01)  # small delay for typing effect

    attempt = 0
    while attempt < max_retries:
        attempt += 1
        t_start = time.monotonic()
        log.info("[Bedrock] Request — model=%s attempt=%d/%d", model_id, attempt, max_retries)

        try:
            payload = _build_payload(messages)
            response = await asyncio.to_thread(_call_bedrock, payload)

            text, tool_uses = _extract_text_and_tools(response)
            log.info("[Bedrock] First turn — text_len=%d tool_uses=%d", len(text), len(tool_uses))

            # ── No tool calls: stream reply directly ──────────────────────────
            if not tool_uses:
                if text:
                    async for chunk in _stream_text(text):
                        yield chunk
                else:
                    yield _sse({"type": "error", "content": "No response from AI model."})

            # ── Tool calls: execute (async), then second turn ─────────────────
            else:
                assistant_content: list[dict] = []
                user_tool_results: list[dict] = []

                for t in tool_uses:
                    tool_name = t["name"]
                    tool_use_id = t["toolUseId"]
                    input_dict = t["input"]

                    log.info("[Bedrock] Tool call — name=%s input=%s", tool_name, input_dict)

                    # tool_executor is async — await it directly
                    result = await tool_executor(tool_name, input_dict)

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
                response2 = await asyncio.to_thread(_call_bedrock, payload2)
                text2, _ = _extract_text_and_tools(response2)
                log.info("[Bedrock] Second turn — text_len=%d", len(text2))

                if text2:
                    async for chunk in _stream_text(text2):
                        yield chunk
                else:
                    yield _sse({"type": "error", "content": "No response from AI model on second turn."})

            latency_ms = round((time.monotonic() - t_start) * 1000)
            log.info("[Bedrock] Completed — latency_ms=%d", latency_ms)
            yield _sse({"type": "done"})
            return  # success

        except RuntimeError as exc:
            err = str(exc)
            log.error("[Bedrock] Error attempt=%d: %s", attempt, err)

            # Terminal errors — never retry
            is_terminal = any(x in err for x in [
                "AccessDenied", "403", "ValidationException", "400",
                "ResourceNotFound", "404", "end of its life", "Legacy",
                "Access denied",
            ])
            if is_terminal:
                log.error("[Bedrock] Terminal error — not retrying.")
                yield _sse({"type": "error", "content": err})
                return

            if attempt < max_retries:
                backoff = base_backoff * (2 ** (attempt - 1))
                log.warning("[Bedrock] Retrying in %.1fs...", backoff)
                await asyncio.sleep(backoff)
                continue

            yield _sse({"type": "error", "content": err})
            return

        except Exception as exc:
            log.exception("[Bedrock] Unexpected error attempt=%d: %s", attempt, exc)
            if attempt < max_retries:
                backoff = base_backoff * (2 ** (attempt - 1))
                await asyncio.sleep(backoff)
                continue
            yield _sse({"type": "error", "content": str(exc)})
            return


def reset_client() -> None:
    """No-op kept for API compatibility — HTTP client has no persistent state."""
    log.info("[Bedrock] reset_client() called — HTTP mode has no persistent state.")
