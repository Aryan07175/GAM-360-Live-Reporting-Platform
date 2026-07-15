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
    or breakdown by app / website / ad unit / child network.
    """
    return {
        "toolSpec": {
            "name": "query_gam_data",
            "description": (
                "Fetch LIVE data directly from Google Ad Manager for any date range, "
                "dimension, and metric. "
                "ALWAYS call this tool when the user asks about revenue, impressions, "
                "clicks, eCPM, CTR, fill rate, ad requests, or match rate for any "
                "time period (today, yesterday, past N days, past N months, "
                "this month/MTD, this year/YTD, last month, last year, past 1 year, "
                "or any custom date range). "
                "When NO time period is mentioned, use start_date=YTD start, end_date=today. "
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
                                "You MUST compute the actual calendar date before calling this tool. "
                                "Date phrase → start_date mapping (use the Date Reference table in the system prompt): "
                                "'today' → today; "
                                "'yesterday' → yesterday; "
                                "'past 7 days' → today minus 7 days; "
                                "'past 30 days' → today minus 30 days; "
                                "'past 45 days' → today minus 45 days; "
                                "'past 60 days' → today minus 60 days; "
                                "'past 3 months' → today minus 90 days; "
                                "'past 6 months' → today minus 180 days; "
                                "'past 1 year' / 'last year' / 'past 12 months' → today minus 365 days; "
                                "'this month' / 'MTD' → 1st day of current month; "
                                "'this year' / 'YTD' → Jan 1 of current year; "
                                "'last month' → 1st day of previous month; "
                                "no time mentioned → Jan 1 of current year (YTD default)."
                            ),
                        },
                        "end_date": {
                            "type": "string",
                            "description": "End date in YYYY-MM-DD format (inclusive). For open-ended ranges like 'past N days', end_date = today.",
                        },
                        "dimension": {
                            "type": "string",
                            "enum": [
                                "none", "app", "ad_unit", "ad_unit_top",
                                "website", "child_network",
                                "advertiser", "advertiser_classified", "country"
                            ],
                            "description": (
                                "How to break down the result. "
                                "'none' = network-wide totals only (no breakdown). "
                                "'app'/'ad_unit' = breakdown by ad unit / mobile app name. "
                                "'ad_unit_top' = breakdown by top-level ad unit (root segment before '/'). "
                                "'website' = breakdown by website domain (strips protocol/www). "
                                "'child_network' = breakdown by MCM child network code. "
                                "'advertiser' = breakdown by advertiser name (uses separate report, no ad-unit split). "
                                "'advertiser_classified' = breakdown by classified advertiser. "
                                "'country' = breakdown by country name (uses separate report, no ad-unit split). "
                                "Use 'advertiser' when user says 'by advertiser'. "
                                "Use 'country' when user says 'by country'. "
                                "Use 'ad_unit_top' when user says 'top-level ad units'."
                            ),
                        },
                        "metric": {
                            "type": "string",
                            "enum": [
                                # --- Ad Server (direct-sold) ---
                                "revenue", "impressions", "clicks", "ctr", "ecpm",
                                "fill_rate", "ad_requests",
                                # --- Ad Exchange ---
                                "match_rate", "programmatic_match_rate",
                                "adx_impressions", "adx_revenue", "adx_clicks",
                                "adx_ctr", "adx_ecpm",
                                # --- AdSense ---
                                "adsense_impressions", "adsense_clicks", "adsense_revenue",
                                "adsense_ctr", "adsense_ecpm",
                                # --- Network-wide request/fill ---
                                "total_ad_requests", "total_responses_served",
                                "total_fill_rate", "total_code_served",
                                # --- Total line-item aggregates (all demand channels) ---
                                "total_revenue",              # Total revenue (all demand, incl. CPD)
                                "total_cpm_and_cpc_revenue",  # Total CPM+CPC revenue
                                "total_impressions",          # Total impressions
                                "total_clicks",               # Total clicks
                                "total_ctr",                  # Total CTR
                                "total_average_ecpm",         # Total avg eCPM (w/o CPD)
                                "total_average_ecpm_with_cpd",# Total avg eCPM (with CPD)
                                "total_targeted_impressions", # Total targeted impressions
                                "total_targeted_clicks",      # Total targeted clicks
                                "total_unmatched_ad_requests",# Total unmatched ad requests
                                "unfilled_impressions",       # Unfilled impressions (inventory-level)
                                "drop_off_rate",              # Drop-off rate
                                "inactive_begin_to_render_impressions",  # Inactive begin-to-render (BETA)
                                # --- Total Active View ---
                                "total_active_view_eligible_impressions",
                                "total_active_view_measurable_impressions",
                                "total_active_view_viewable_impressions",
                                "total_active_view_measurable_impressions_rate",  # % measurable
                                "total_active_view_viewable_impressions_rate",    # % viewable
                                "total_active_view_average_viewable_time",        # avg viewable time (sec)
                                "total_active_view_revenue",
                                # --- BETA / UI-only metrics (returned as 'not available') ---
                                "total_muted_impressions",
                                "total_mute_eligible_impressions",
                                "total_overdelivered_impressions",
                                "total_mcm_autopayment_revenue",
                                "total_rewards_granted",
                                "total_unloaded_impressions_cpu",
                                "total_unloaded_impressions_network",
                                "total_opportunities",
                                "total_active_view_audible_and_visible",
                            ],
                            "description": (
                                "Primary metric to report. "
                                "--- Ad Server (direct-sold) --- "
                                "revenue = Ad Server CPM+CPC revenue (USD). "
                                "impressions = Ad Server impressions. "
                                "clicks = Ad Server clicks. "
                                "ctr = Ad Server CTR (%). "
                                "ecpm = Ad Server effective CPM (USD). "
                                "fill_rate = Ad Server fill rate (impressions/ad_requests x 100). "
                                "ad_requests = Ad Server ad requests. "
                                "--- Ad Exchange / Programmatic --- "
                                "match_rate = AdX match rate (AdX impressions/total requests x 100). Use channel='ad_exchange'. "
                                "programmatic_match_rate = GAM PROGRAMMATIC_MATCH_RATE column. "
                                "adx_revenue/impressions/clicks/ctr/ecpm = AdX-only metrics. "
                                "--- AdSense --- "
                                "adsense_revenue/impressions/clicks/ctr/ecpm = AdSense-only metrics. "
                                "--- Network-wide request/fill (WSDL TOTAL_* columns) --- "
                                "total_ad_requests = TOTAL_AD_REQUESTS (true network total). "
                                "total_responses_served = TOTAL_RESPONSES_SERVED. "
                                "total_fill_rate = TOTAL_FILL_RATE (%). "
                                "total_code_served = TOTAL_CODE_SERVED_COUNT. "
                                "total_unmatched_ad_requests = TOTAL_UNMATCHED_AD_REQUESTS. "
                                "--- Total line-item aggregates (GAM 'Total' column group) --- "
                                "total_revenue = TOTAL_LINE_ITEM_LEVEL_ALL_REVENUE (all demand incl. CPD). "
                                "total_cpm_and_cpc_revenue = TOTAL_LINE_ITEM_LEVEL_CPM_AND_CPC_REVENUE. "
                                "total_impressions = TOTAL_LINE_ITEM_LEVEL_IMPRESSIONS. "
                                "total_clicks = TOTAL_LINE_ITEM_LEVEL_CLICKS. "
                                "total_ctr = TOTAL_LINE_ITEM_LEVEL_CTR (%). "
                                "total_average_ecpm = TOTAL_LINE_ITEM_LEVEL_WITHOUT_CPD_AVERAGE_ECPM. "
                                "total_average_ecpm_with_cpd = TOTAL_LINE_ITEM_LEVEL_WITH_CPD_AVERAGE_ECPM. "
                                "total_targeted_impressions = TOTAL_LINE_ITEM_LEVEL_TARGETED_IMPRESSIONS. "
                                "total_targeted_clicks = TOTAL_LINE_ITEM_LEVEL_TARGETED_CLICKS. "
                                "unfilled_impressions = TOTAL_INVENTORY_LEVEL_UNFILLED_IMPRESSIONS. "
                                "drop_off_rate = DROPOFF_RATE (video). "
                                "inactive_begin_to_render_impressions = AD_SERVER_BEGIN_TO_RENDER_IMPRESSIONS (BETA). "
                                "--- Total Active View --- "
                                "total_active_view_eligible_impressions = TOTAL_ACTIVE_VIEW_ELIGIBLE_IMPRESSIONS. "
                                "total_active_view_measurable_impressions = TOTAL_ACTIVE_VIEW_MEASURABLE_IMPRESSIONS. "
                                "total_active_view_viewable_impressions = TOTAL_ACTIVE_VIEW_VIEWABLE_IMPRESSIONS. "
                                "total_active_view_measurable_impressions_rate = % measurable impressions. "
                                "total_active_view_viewable_impressions_rate = % viewable impressions. "
                                "total_active_view_average_viewable_time = avg viewable time in seconds. "
                                "total_active_view_revenue = TOTAL_ACTIVE_VIEW_REVENUE. "
                                "--- BETA/UI-only (will return 'not available' note) --- "
                                "total_muted_impressions, total_mute_eligible_impressions, "
                                "total_overdelivered_impressions, total_mcm_autopayment_revenue, "
                                "total_rewards_granted, total_unloaded_impressions_cpu, "
                                "total_unloaded_impressions_network, total_opportunities, "
                                "total_active_view_audible_and_visible. "
                                "IMPORTANT: fill_rate != match_rate. Never substitute one for the other."
                            ),
                        },

                        "channel": {
                            "type": "string",
                            "enum": ["all", "ad_server", "adsense", "ad_exchange"],
                            "description": (
                                "Demand channel filter. "
                                "'all' = unified view (Ad Server + AdSense + Ad Exchange totals — default). "
                                "'ad_server' = direct-sold Ad Server only. "
                                "'adsense' = AdSense backfill only. "
                                "'ad_exchange' = Ad Exchange / programmatic only. "
                                "Use 'ad_exchange' when user asks about AdX, Ad Exchange, programmatic, match rate."
                            ),
                        },
                        "filter_name": {
                            "type": "string",
                            "description": (
                                "Optional: filter results to a specific app/website/child-network name. "
                                "E.g. 'cardekho.com', 'cardekho', 'CarDekho'. "
                                "The backend normalizes case and strips www/protocol for website matching. "
                                "Pass the name the user mentioned exactly as they said it."
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

    Auth priority:
    1. AWS SigV4 (standard IAM keys: AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY)
    2. Bearer token (AWS_BEARER_TOKEN_BEDROCK) — for IAM Identity Center / SSO sessions
    """
    bearer_token = _get_bearer_token()
    model_id = _get_model_id()
    region = _get_region()
    url = _get_endpoint(model_id, region)

    body_bytes = json.dumps(payload).encode("utf-8")

    # ── Try SigV4 first (standard IAM auth) ──────────────────────────────────
    access_key = os.getenv("AWS_ACCESS_KEY_ID", "")
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    session_token = os.getenv("AWS_SESSION_TOKEN", "")

    if access_key and secret_key:
        # Build SigV4 signed request using Python stdlib (no boto3 required for signing)
        try:
            import hmac
            import hashlib
            from datetime import datetime as _dt, timezone as _tz
            import urllib.parse

            now = _dt.now(_tz.utc)
            amz_date = now.strftime("%Y%m%dT%H%M%SZ")
            date_stamp = now.strftime("%Y%m%d")
            service = "bedrock"

            # Parse URL for signing
            parsed = urllib.parse.urlparse(url)
            host = parsed.netloc
            canonical_uri = parsed.path or "/"

            payload_hash = hashlib.sha256(body_bytes).hexdigest()

            canonical_headers_dict = {
                "content-type": "application/json",
                "host": host,
                "x-amz-date": amz_date,
            }
            if session_token:
                canonical_headers_dict["x-amz-security-token"] = session_token

            sorted_header_names = sorted(canonical_headers_dict.keys())
            canonical_headers = "".join(f"{k}:{canonical_headers_dict[k]}\n" for k in sorted_header_names)
            signed_headers = ";".join(sorted_header_names)

            canonical_request = "\n".join([
                "POST",
                canonical_uri,
                "",  # canonical query string (empty)
                canonical_headers,
                signed_headers,
                payload_hash,
            ])

            algorithm = "AWS4-HMAC-SHA256"
            credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"
            string_to_sign = "\n".join([
                algorithm,
                amz_date,
                credential_scope,
                hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
            ])

            def _sign(key: bytes, msg: str) -> bytes:
                return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

            signing_key = _sign(
                _sign(
                    _sign(
                        _sign(f"AWS4{secret_key}".encode("utf-8"), date_stamp),
                        region,
                    ),
                    service,
                ),
                "aws4_request",
            )
            signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

            authorization = (
                f"{algorithm} "
                f"Credential={access_key}/{credential_scope}, "
                f"SignedHeaders={signed_headers}, "
                f"Signature={signature}"
            )

            req_headers = {
                "Content-Type": "application/json",
                "X-Amz-Date": amz_date,
                "Authorization": authorization,
            }
            if session_token:
                req_headers["X-Amz-Security-Token"] = session_token

            log.info("[Bedrock] POST %s model=%s bytes=%d (SigV4 auth)", url, model_id, len(body_bytes))
            req = urllib.request.Request(url, data=body_bytes, headers=req_headers, method="POST")

            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    raw = resp.read()
                    log.info("[Bedrock] HTTP %d — response %d bytes (SigV4)", resp.status, len(raw))
                    return json.loads(raw.decode("utf-8"))
            except urllib.error.HTTPError as exc:
                error_body = exc.read().decode("utf-8", errors="replace")
                log.error("[Bedrock] SigV4 HTTP %d — %s", exc.code, error_body)
                # Fall through to Bearer token attempt if 401/403
                if exc.code not in (401, 403) or not bearer_token:
                    raise RuntimeError(f"Bedrock HTTP {exc.code}: {error_body}") from exc
                log.warning("[Bedrock] SigV4 failed with %d — retrying with Bearer token", exc.code)
        except ImportError:
            log.warning("[Bedrock] SigV4 signing failed (import error) — falling back to Bearer token")

    # ── Bearer token auth (IAM Identity Center / SSO) ────────────────────────
    if not bearer_token:
        raise RuntimeError(
            "Bedrock auth not configured: set AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY "
            "(for SigV4) or AWS_BEARER_TOKEN_BEDROCK (for IAM Identity Center)."
        )

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {bearer_token}",
    }
    log.info("[Bedrock] POST %s model=%s bytes=%d (Bearer auth)", url, model_id, len(body_bytes))
    req = urllib.request.Request(url, data=body_bytes, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            log.info("[Bedrock] HTTP %d — response %d bytes (Bearer)", resp.status, len(raw))
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
        """
        Stream the complete Bedrock response text as fixed-size character chunks.

        CRITICAL: Do NOT split by spaces or inject spaces between chunks.
        Splitting on ' ' then prepending ' ' before every word corrupts numbers,
        dates and punctuation: '2026' -> '202 6', 'July 14,' -> 'July  14 ,'.
        Instead, slice the text into fixed-size windows and send each slice
        verbatim so the frontend can append them with zero modification.
        """
        CHUNK_SIZE = 4  # characters per SSE event — small enough for smooth typing
        for i in range(0, len(text), CHUNK_SIZE):
            chunk = text[i : i + CHUNK_SIZE]
            yield _sse({"type": "token", "content": chunk})
            await asyncio.sleep(0.008)  # ~125 chunks/s → smooth typing feel

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
