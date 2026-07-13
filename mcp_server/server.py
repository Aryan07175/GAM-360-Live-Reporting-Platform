"""
GAM 360 MCP Server — Live Reporting Engine

Every tool fetches LIVE data from Google Ad Manager.
No database. No cache. No ETL. No stored reports.

18+ tools covering: Executive Summary, Revenue, Trends, Applications,
Websites, Impressions, Clicks, CTR, eCPM, Fill Rate, Ad Requests,
Performance Ranking, Anomalies, Recommendations, and Full Report.

Plus: Ask GAM 360 — AI chat grounded in live dashboard data.
"""

import json
import logging
import asyncio
from datetime import date, timedelta, datetime

from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse, StreamingResponse
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp import types
import uvicorn
import pandas as pd

import sys
import os
# Allow imports from the project root (fixes IDE warnings and CLI execution)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from mcp_server.gam_client import GAMClient

# Google Gemini (lazy — only imported when chat is used)
try:
    import google.generativeai as genai
    from google.generativeai.types import content_types
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("mcp_server")

app = Server("gam360-live-reporting")
sse = SseServerTransport("/messages/")

gam = GAMClient()


# ─── In-Memory Data Cache (for Ask GAM 360 chat) ─────────────────────────────

_session_cache: dict[str, dict] = {}
# Structure: { "session_key": { "df": DataFrame, "summary": dict, "stored_at": datetime, "start": str, "end": str } }


def _cache_key(start_date: str, end_date: str, demand_channel: str = "all") -> str:
    return f"{start_date}_{end_date}_{demand_channel}"


def build_data_summary(df: pd.DataFrame, start: date, end: date) -> dict:
    """
    Build a compact JSON data summary from the report DataFrame.
    This is the chat's SINGLE SOURCE OF TRUTH — Claude answers only from this.
    """
    if df.empty:
        return {
            "period": f"{start} to {end}",
            "metrics": {},
            "revenue_trend": [],
            "top_apps": [],
            "all_apps": [],
        }

    rev = float(df["ad_server_cpm_and_cpc_revenue"].sum())
    imp = int(df["ad_server_impressions"].sum())
    clicks = int(df["ad_server_clicks"].sum())
    ad_requests = int(df["ad_server_ad_requests"].sum())
    ecpm = (rev / imp * 1000) if imp > 0 else 0.0
    ctr = (clicks / imp * 100) if imp > 0 else 0.0
    fill_rate = (imp / ad_requests * 100) if ad_requests > 0 else 0.0
    dau = ad_requests // 5 if ad_requests > 0 else 0

    app_summary = df.groupby("ad_unit_name").agg({
        "ad_server_cpm_and_cpc_revenue": "sum",
        "ad_server_impressions": "sum",
        "ad_server_clicks": "sum",
        "ad_server_ad_requests": "sum",
    }).reset_index()
    app_summary = app_summary.sort_values("ad_server_cpm_and_cpc_revenue", ascending=False)

    # Per-app metrics
    all_apps = []
    for _, row in app_summary.iterrows():
        a_imp = int(row["ad_server_impressions"])
        a_rev = float(row["ad_server_cpm_and_cpc_revenue"])
        a_clicks = int(row["ad_server_clicks"])
        a_req = int(row["ad_server_ad_requests"])
        all_apps.append({
            "name": row["ad_unit_name"],
            "revenue_usd": round(a_rev, 6),
            "impressions": a_imp,
            "clicks": a_clicks,
            "ad_requests": a_req,
            "ecpm_usd": round((a_rev / a_imp * 1000), 6) if a_imp > 0 else 0.0,
            "ctr_pct": round((a_clicks / a_imp * 100), 4) if a_imp > 0 else 0.0,
            "fill_rate_pct": round((a_imp / a_req * 100), 2) if a_req > 0 else 0.0,
        })

    # Revenue trend
    revenue_trend = []
    if "date" in df.columns:
        daily = df.groupby("date").agg({
            "ad_server_cpm_and_cpc_revenue": "sum",
            "ad_server_impressions": "sum",
            "ad_server_clicks": "sum",
            "ad_server_ad_requests": "sum",
        }).reset_index().sort_values("date")
        for _, row in daily.iterrows():
            d_imp = int(row["ad_server_impressions"])
            d_rev = float(row["ad_server_cpm_and_cpc_revenue"])
            revenue_trend.append({
                "date": str(row["date"]),
                "revenue_usd": round(d_rev, 6),
                "impressions": d_imp,
                "clicks": int(row["ad_server_clicks"]),
                "ad_requests": int(row["ad_server_ad_requests"]),
                "ecpm_usd": round((d_rev / d_imp * 1000), 6) if d_imp > 0 else 0.0,
            })

    return {
        "period": f"{start} to {end}",
        "metrics": {
            "total_revenue_usd": round(rev, 6),
            "total_impressions": imp,
            "total_clicks": clicks,
            "total_ad_requests": ad_requests,
            "avg_ecpm_usd": round(ecpm, 6),
            "avg_ctr_pct": round(ctr, 4),
            "fill_rate_pct": round(fill_rate, 2),
            "active_apps": len(app_summary),
            "daily_active_users": dau,
        },
        "revenue_trend": revenue_trend,
        "top_apps": all_apps[:10],
        "all_apps": all_apps,
    }


def execute_query_data(df: pd.DataFrame, operation: str, dimension: str = None,
                       metric: str = None, filters: dict = None, limit: int = 10) -> dict:
    """
    Execute whitelisted Pandas aggregations against the cached DataFrame.
    This is the single tool given to Claude — never arbitrary code execution.
    """
    METRIC_MAP = {
        "revenue": "ad_server_cpm_and_cpc_revenue",
        "impressions": "ad_server_impressions",
        "clicks": "ad_server_clicks",
        "ad_requests": "ad_server_ad_requests",
        "ecpm": "ad_server_cpm_and_cpc_revenue",  # will compute
        "ctr": "ad_server_clicks",  # will compute
        "fill_rate": "ad_server_impressions",  # will compute
    }
    DIM_MAP = {
        "app": "ad_unit_name",
        "date": "date",
    }

    if df.empty:
        return {"result": "No data available for this query."}

    try:
        work_df = df.copy()

        # Apply filters
        if filters:
            if "app_name" in filters and filters["app_name"]:
                name_filter = filters["app_name"].lower()
                work_df = work_df[work_df["ad_unit_name"].str.lower().str.contains(name_filter, na=False)]
            if "date" in filters and filters["date"]:
                work_df = work_df[work_df["date"] == filters["date"]]
            if "min_revenue" in filters:
                grouped = work_df.groupby("ad_unit_name")["ad_server_cpm_and_cpc_revenue"].sum()
                valid_apps = grouped[grouped >= float(filters["min_revenue"])].index
                work_df = work_df[work_df["ad_unit_name"].isin(valid_apps)]

        if work_df.empty:
            return {"result": "No data matches the specified filters."}

        col = METRIC_MAP.get(metric, "ad_server_cpm_and_cpc_revenue") if metric else "ad_server_cpm_and_cpc_revenue"
        dim_col = DIM_MAP.get(dimension, "ad_unit_name") if dimension else None

        if operation == "sum":
            if dim_col and dim_col in work_df.columns:
                result = work_df.groupby(dim_col)[col].sum().reset_index()
                result = result.sort_values(col, ascending=False)
                return {"result": result.head(limit).to_dict(orient="records")}
            return {"result": float(work_df[col].sum())}

        elif operation == "mean":
            if dim_col and dim_col in work_df.columns:
                result = work_df.groupby(dim_col)[col].mean().reset_index()
                return {"result": result.head(limit).to_dict(orient="records")}
            return {"result": float(work_df[col].mean())}

        elif operation == "max":
            if dim_col and dim_col in work_df.columns:
                result = work_df.groupby(dim_col)[col].sum().reset_index()
                idx = result[col].idxmax()
                return {"result": result.loc[idx].to_dict()}
            return {"result": float(work_df[col].max())}

        elif operation == "min":
            if dim_col and dim_col in work_df.columns:
                result = work_df.groupby(dim_col)[col].sum().reset_index()
                idx = result[col].idxmin()
                return {"result": result.loc[idx].to_dict()}
            return {"result": float(work_df[col].min())}

        elif operation == "top_n":
            if dim_col and dim_col in work_df.columns:
                result = work_df.groupby(dim_col)[col].sum().reset_index()
                result = result.sort_values(col, ascending=False).head(limit)
                return {"result": result.to_dict(orient="records")}
            return {"result": f"Need a dimension (app or date) for top_n."}

        elif operation == "bottom_n":
            if dim_col and dim_col in work_df.columns:
                result = work_df.groupby(dim_col)[col].sum().reset_index()
                result = result.sort_values(col, ascending=True).head(limit)
                return {"result": result.to_dict(orient="records")}
            return {"result": f"Need a dimension (app or date) for bottom_n."}

        elif operation == "compare":
            if dim_col and dim_col in work_df.columns:
                result = work_df.groupby(dim_col).agg({
                    "ad_server_cpm_and_cpc_revenue": "sum",
                    "ad_server_impressions": "sum",
                    "ad_server_clicks": "sum",
                    "ad_server_ad_requests": "sum",
                }).reset_index()
                result["ecpm_usd"] = (result["ad_server_cpm_and_cpc_revenue"] / result["ad_server_impressions"] * 1000).where(result["ad_server_impressions"] > 0, 0)
                result["fill_rate_pct"] = (result["ad_server_impressions"] / result["ad_server_ad_requests"] * 100).where(result["ad_server_ad_requests"] > 0, 0)
                result = result.sort_values("ad_server_cpm_and_cpc_revenue", ascending=False).head(limit)
                return {"result": result.to_dict(orient="records")}
            return {"result": "Need a dimension for compare."}

        elif operation == "count":
            if dim_col and dim_col in work_df.columns:
                return {"result": int(work_df[dim_col].nunique())}
            return {"result": len(work_df)}

        else:
            return {"result": f"Unknown operation: {operation}. Use sum, mean, max, min, top_n, bottom_n, compare, or count."}

    except Exception as e:
        log.exception(f"query_data failed: {e}")
        return {"error": str(e)}


# ─── Chat System Prompt ──────────────────────────────────────────────────────

CHAT_SYSTEM_PROMPT = """You are **Ask GAM 360**, an AI assistant embedded in the GAM 360 Live Analytics dashboard. You answer questions about Google Ad Manager data that is currently displayed on the user's dashboard.

## Your Data Source
You have access to a data summary of the dashboard's current view. This summary contains:
- **Top-card metrics**: Total Revenue, Impressions, Clicks, Avg eCPM, CTR, Fill Rate, Ad Requests, Active Apps, Daily Active Users (DAU)
- **Revenue Trend**: Day-by-day revenue, impressions, eCPM for the selected date range
- **Top Performing Apps**: All apps ranked by revenue with their impressions, eCPM, fill rate, CTR

## Rules — CRITICAL
1. **ONLY state numbers that exist in the data summary or a query_data tool result.** Never invent, estimate, or hallucinate numbers.
2. If the user asks about data you don't have, say: "I don't have that in the current dashboard view."
3. Keep answers **short and dashboard-native**: 1-3 sentences, bold key numbers, optionally a brief explanation.
4. When a metric is **0 or 0.00%** (e.g., Fill Rate 0.00%, Daily Active Users 0, Ad Requests 0), explain it honestly — likely no data was returned by GAM for that metric/date, not necessarily that the actual value is zero.
5. Format currency as `$X.XXXXXX` for small values or `$X.XX` for larger values. Format large numbers with commas.
6. When comparing apps, use the query_data tool to get precise figures rather than approximating from the summary.
7. You can reference the data summary directly for simple lookups. Use the query_data tool for aggregations, filtering, sorting, or comparisons not already in the summary.

## Metric Definitions
- **Total Revenue**: Sum of all ad revenue (CPM + CPC) across all ad units, in USD
- **Impressions**: Total number of ad impressions served
- **Clicks**: Total ad clicks
- **Avg eCPM**: Effective cost per mille = (Revenue / Impressions) × 1000
- **CTR**: Click-through rate = (Clicks / Impressions) × 100
- **Fill Rate**: Percentage of ad requests that resulted in an impression = (Impressions / Ad Requests) × 100
- **Ad Requests**: Total number of ad requests made to GAM
- **Active Apps**: Number of distinct ad units with data in the selected period
- **Daily Active Users (DAU)**: Estimated as Ad Requests / 5 (proxy metric)

## Current Dashboard Data Summary
{data_summary}
"""


# ─── Chat Endpoint ───────────────────────────────────────────────────────────

def get_query_data_tool():
    """Returns the tool definition for Gemini."""
    return {
        "function_declarations": [
            {
                "name": "query_data",
                "description": "Query the current dashboard's GAM data with whitelisted aggregations. Use this for comparisons, filtering, sorting, or detailed breakdowns not already in the data summary.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "operation": {
                            "type": "STRING",
                            "description": "The aggregation operation to perform (sum, mean, max, min, top_n, bottom_n, compare, count)."
                        },
                        "dimension": {
                            "type": "STRING",
                            "description": "The dimension to group by (app = ad unit, date = calendar day)."
                        },
                        "metric": {
                            "type": "STRING",
                            "description": "The metric to aggregate (revenue, impressions, clicks, ad_requests, ecpm, ctr, fill_rate)."
                        },
                        "filters": {
                            "type": "OBJECT",
                            "description": "Optional filters: app_name (substring match), date (exact YYYY-MM-DD), min_revenue (number).",
                            "properties": {
                                "app_name": {"type": "STRING"},
                                "date": {"type": "STRING"},
                                "min_revenue": {"type": "NUMBER"}
                            }
                        },
                        "limit": {
                            "type": "INTEGER",
                            "description": "Max number of results for top_n/bottom_n (default 10)."
                        }
                    },
                    "required": ["operation"]
                }
            }
        ]
    }


async def handle_chat(request):
    """
    POST /api/chat — SSE streaming chat endpoint.
    Accepts { session_id, message, history[], date_range: { startDate, endDate } }
    Streams Gemini responses token-by-token as SSE events.
    """
    if request.method == "OPTIONS":
        return JSONResponse({}, headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        })

    if not HAS_GEMINI:
        return JSONResponse(
            {"error": "Google Generative AI SDK not installed. Run: pip install google-generativeai"},
            status_code=500,
            headers={"Access-Control-Allow-Origin": "*"},
        )

    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        return JSONResponse(
            {"error": "GEMINI_API_KEY not set"},
            status_code=500,
            headers={"Access-Control-Allow-Origin": "*"},
        )

    try:
        body = await request.json()
        message = body.get("message", "").strip()
        history = body.get("history", [])
        date_range = body.get("date_range", {})
        session_id = body.get("session_id", "")

        if not message:
            return JSONResponse(
                {"error": "No message provided"},
                status_code=400,
                headers={"Access-Control-Allow-Origin": "*"},
            )

        # Find cached data for this session
        start_str = date_range.get("startDate", "")
        end_str = date_range.get("endDate", "")
        demand = date_range.get("demandChannel", "all")
        cache_key = _cache_key(start_str, end_str, demand)

        cached = _session_cache.get(cache_key)
        if not cached:
            # Fallback: try the most recent cached session
            if _session_cache:
                cache_key = list(_session_cache.keys())[-1]
                cached = _session_cache[cache_key]

        # If still no cached data, fetch LIVE from GAM on-demand
        if not cached and start_str and end_str:
            try:
                log.info(f"[Chat] No cached data found. Fetching live data for {start_str} to {end_str}...")
                chat_start = datetime.strptime(start_str, "%Y-%m-%d").date()
                chat_end = datetime.strptime(end_str, "%Y-%m-%d").date()
                live_df = await gam.get_live_data_multi_day(chat_start, chat_end, False, demand)
                if not live_df.empty:
                    summary = build_data_summary(live_df, chat_start, chat_end)
                    cache_key = _cache_key(start_str, end_str, demand)
                    _session_cache[cache_key] = {
                        "df": live_df.copy(),
                        "summary": summary,
                        "stored_at": datetime.now(),
                        "start": start_str,
                        "end": end_str,
                    }
                    cached = _session_cache[cache_key]
                    log.info(f"[Chat] On-demand fetch successful: {len(live_df)} rows, {len(summary.get('all_apps', []))} apps")
            except Exception as fetch_err:
                log.warning(f"[Chat] On-demand data fetch failed: {fetch_err}")

        data_summary = cached["summary"] if cached else {"metrics": {}, "revenue_trend": [], "top_apps": [], "all_apps": []}
        cached_df = cached["df"] if cached else pd.DataFrame()

        # Build a COMPACT data summary for the system prompt to minimize token usage.
        # The full data is still available via the query_data tool.
        compact_summary = {
            "period": data_summary.get("period", ""),
            "metrics": data_summary.get("metrics", {}),
            "top_apps": data_summary.get("top_apps", [])[:10],
            "revenue_trend": data_summary.get("revenue_trend", [])[-7:],  # Last 7 days only
        }

        # Build messages array for Gemini
        system_prompt = CHAT_SYSTEM_PROMPT.format(
            data_summary=json.dumps(compact_summary, indent=2, default=str)
        )

        gemini_history = []
        for h in history[-10:]:
            # Gemini roles: 'user' and 'model'
            role = "model" if h.get("role") == "assistant" else "user"
            content = h.get("content", "").strip()
            # Skip empty messages — Gemini rejects history entries with empty text
            if not content:
                continue
            gemini_history.append({
                "role": role,
                "parts": [{"text": content}]
            })

        log.info(f"[Chat] session={cache_key} message={message[:80]}...")

        async def stream_response():
            # gemini-2.0-flash-lite has 2x higher free-tier quota (30 RPM vs 15 RPM)
            # Use it as primary; fall back to flash only on the last attempt
            MODELS = ["gemini-2.0-flash-lite", "gemini-2.0-flash"]
            MAX_RETRIES = 3
            last_error = None

            for attempt in range(MAX_RETRIES):
                try:
                    # Use primary lite model first, try full flash on last attempt
                    model_name = MODELS[0] if attempt < 2 else MODELS[-1]
                    
                    genai.configure(api_key=api_key)
                    
                    # Create the model with system instruction and tools
                    model = genai.GenerativeModel(
                        model_name=model_name,
                        system_instruction=system_prompt,
                        tools=get_query_data_tool()
                    )

                    # Initialize chat session
                    chat = model.start_chat(history=gemini_history)
                    
                    log.info(f"[Chat] Attempt {attempt+1}/{MAX_RETRIES} using model={model_name}")
                    
                    # Send the message
                    response = chat.send_message(message, stream=True)
                    
                    tool_called = False
                    
                    # We need to process the stream
                    tool_calls_to_execute = []
                    for chunk in response:
                        # Check for function calls
                        for part in chunk.parts:
                            if hasattr(part, 'function_call') and part.function_call and part.function_call.name:
                                tool_called = True
                                tool_calls_to_execute.append(part.function_call)
                            else:
                                # Safely extract text — avoid accessing .text on non-text parts
                                try:
                                    text = part.text
                                    if text:
                                        yield f"data: {json.dumps({'type': 'token', 'content': text})}\n\n"
                                except (ValueError, AttributeError):
                                    pass  # Part is not a text part (e.g. function_call), skip it
                                
                    # The first stream is fully consumed. Now we can send tool results if any.
                    if tool_calls_to_execute:
                        tool_response_parts = []
                        for fc in tool_calls_to_execute:
                            tool_name = fc.name
                            
                            # Convert protobuf Struct to dict
                            kwargs = {}
                            for k, v in fc.args.items():
                                kwargs[k] = v
                                
                            log.info(f"[Chat] Tool call: {tool_name}({kwargs})")
                            
                            if tool_name == "query_data":
                                result = execute_query_data(
                                    cached_df,
                                    operation=kwargs.get("operation", "sum"),
                                    dimension=kwargs.get("dimension"),
                                    metric=kwargs.get("metric"),
                                    filters=kwargs.get("filters"),
                                    limit=int(kwargs.get("limit", 10)),
                                )
                            else:
                                result = {"error": f"Unknown tool: {tool_name}"}
                            
                            # Serialize through JSON to ensure all values are
                            # pure Python types (protobuf Struct rejects numpy int64/float64)
                            safe_result = json.loads(json.dumps(result, default=str))
                            
                            tool_response_parts.append(
                                genai.protos.Part(
                                    function_response=genai.protos.FunctionResponse(
                                        name=tool_name,
                                        response=safe_result
                                    )
                                )
                            )
                            
                        # Stream the model's response to the tool result
                        second_response = chat.send_message(tool_response_parts, stream=True)
                        for second_chunk in second_response:
                            # Safely iterate parts to avoid "Could not convert part.function_call to text"
                            for part in second_chunk.parts:
                                try:
                                    text = part.text
                                    if text:
                                        yield f"data: {json.dumps({'type': 'token', 'content': text})}\n\n"
                                except (ValueError, AttributeError):
                                    pass  # Skip non-text parts (e.g. unexpected function_call)
                                
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                    return  # Success — exit retry loop

                except Exception as e:
                    last_error = e
                    error_str = str(e).lower()
                    is_quota_error = "429" in str(e) or "quota" in error_str or "resource has been exhausted" in error_str or "rate limit" in error_str
                    
                    log.exception(f"[Chat] Stream error (attempt {attempt+1}): {e}")
                    
                    # If it's a quota error, do NOT sleep/retry because if limit is 0, it never recovers and just hangs the UI
                    if is_quota_error:
                        user_msg = "The AI service is temporarily rate-limited (Quota Exceeded). Please wait and try again."
                        yield f"data: {json.dumps({'type': 'error', 'content': user_msg})}\n\n"
                        return
                        
                    # For non-quota errors, we can retry without long sleeps
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(2)
                        continue
                        
                    # User-friendly error messages
                    user_msg = str(e)
                    yield f"data: {json.dumps({'type': 'error', 'content': user_msg})}\n\n"
                    return

        return StreamingResponse(
            stream_response(),
            media_type="text/event-stream",
            headers={
                "Access-Control-Allow-Origin": "*",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    except Exception as e:
        log.exception(f"[Chat] Request error: {e}")
        return JSONResponse(
            {"error": str(e)},
            status_code=500,
            headers={"Access-Control-Allow-Origin": "*"},
        )


# ─── Domain Extraction ───────────────────────────────────────────────────────

def _extract_domain(ad_unit_name: str) -> str:
    """Robustly extract the domain/website from an ad unit name."""
    if not isinstance(ad_unit_name, str):
        return str(ad_unit_name)
    name = ad_unit_name.strip()
    if " - " in name:
        name = name.split(" - ")[0]
    if " (" in name:
        name = name.split(" (")[0]
    if "/" in name:
        parts = name.split("/")
        name = parts[-1] if len(parts) > 1 else parts[0]
    return name.strip()


# ─── Date Resolution ─────────────────────────────────────────────────────────

def _resolve_dates(args: dict) -> tuple[date, date, int, int]:
    """Resolve startDate, endDate, startTime, and endTime from arguments."""
    start_raw = args.get("startDate", args.get("date", "yesterday"))
    end_raw = args.get("endDate", start_raw)

    today = date.today()
    yesterday = today - timedelta(days=1)

    presets = {
        "today": (today, today),
        "yesterday": (yesterday, yesterday),
        "last7days": (today - timedelta(days=6), today),
        "last30days": (today - timedelta(days=29), today),
        "thisMonth": (today.replace(day=1), today),
        "lastMonth": (
            (today.replace(day=1) - timedelta(days=1)).replace(day=1),
            today.replace(day=1) - timedelta(days=1),
        ),
    }

    if start_raw in presets:
        d_start, d_end = presets[start_raw]
    else:
        def parse_date(raw: str) -> date:
            if raw == "yesterday":
                return yesterday
            if raw == "today":
                return today
            return datetime.strptime(raw, "%Y-%m-%d").date()
        d_start, d_end = parse_date(start_raw), parse_date(end_raw)
        
    start_time = args.get("startTime", "00:00")
    end_time = args.get("endTime", "23:59")
    
    try:
        start_hour = int(start_time.split(":")[0])
    except Exception:
        start_hour = 0
        
    try:
        end_hour = int(end_time.split(":")[0])
    except Exception:
        end_hour = 23
        
    return d_start, d_end, start_hour, end_hour


# ─── Analytics Engine ─────────────────────────────────────────────────────────

def compute_executive_summary(df: pd.DataFrame, start: date, end: date) -> dict:
    """Compute comprehensive executive summary from live data."""
    if df.empty:
        return {
            "total_revenue_usd": 0, "total_impressions": 0, "total_clicks": 0,
            "total_ad_requests": 0, "average_ecpm": 0, "average_ctr": 0,
            "average_fill_rate": 0, "app_count": 0,
            "top_app_name": "N/A", "top_app_revenue": 0,
            "period": f"{start} to {end}",
        }

    rev = float(df["ad_server_cpm_and_cpc_revenue"].sum())
    imp = int(df["ad_server_impressions"].sum())
    clicks = int(df["ad_server_clicks"].sum())
    ad_requests = int(df["ad_server_ad_requests"].sum())
    ecpm = (rev / imp * 1000) if imp > 0 else 0
    ctr = (clicks / imp * 100) if imp > 0 else 0
    fill_rate = (imp / ad_requests * 100) if ad_requests > 0 else 0

    app_summary = df.groupby("ad_unit_name")["ad_server_cpm_and_cpc_revenue"].sum()
    app_count = len(app_summary)
    top_app_name = app_summary.idxmax() if not app_summary.empty else "N/A"
    top_app_revenue = float(app_summary.max()) if not app_summary.empty else 0

    return {
        "total_revenue_usd": rev,
        "total_impressions": imp,
        "total_clicks": clicks,
        "total_ad_requests": ad_requests,
        "average_ecpm": ecpm,
        "average_ctr": ctr,
        "average_fill_rate": fill_rate,
        "app_count": app_count,
        "top_app_name": top_app_name,
        "top_app_revenue": top_app_revenue,
        "period": f"{start} to {end}",
    }


def compute_revenue_by_app(df: pd.DataFrame) -> list[dict]:
    """Revenue breakdown by application, sorted descending."""
    if df.empty:
        return []
    summary = df.groupby(["ad_unit_name", "ad_unit_id"]).sum(numeric_only=True).reset_index()
    summary = summary.sort_values(by="ad_server_cpm_and_cpc_revenue", ascending=False)
    return summary.to_dict(orient="records")


def compute_revenue_trend(df: pd.DataFrame) -> list[dict]:
    """Day-by-day revenue trend from the DataFrame."""
    if df.empty:
        return []
    daily = df.groupby("date").agg({
        "ad_server_cpm_and_cpc_revenue": "sum",
        "ad_server_impressions": "sum",
        "ad_server_clicks": "sum",
        "ad_server_ad_requests": "sum",
    }).reset_index()
    # Compute eCPM correctly: (Revenue * 1000) / Impressions
    # Never average daily eCPMs — always derive from totals.
    daily["ecpm_usd"] = daily.apply(
        lambda r: (r["ad_server_cpm_and_cpc_revenue"] / r["ad_server_impressions"] * 1000)
        if r["ad_server_impressions"] > 0 else 0,
        axis=1,
    )
    daily = daily.sort_values("date")
    return daily.rename(columns={
        "date": "report_date",
        "ad_server_cpm_and_cpc_revenue": "revenue_usd",
        "ad_server_impressions": "impressions",
        "ad_server_clicks": "clicks",
        "ad_server_ad_requests": "ad_requests",
    }).to_dict(orient="records")


def compute_top_bottom_apps(df: pd.DataFrame, limit: int = 10) -> tuple[list, list]:
    """Return top N and bottom N apps by revenue."""
    apps = compute_revenue_by_app(df)
    top = apps[:limit]
    bottom = list(reversed(apps[-limit:])) if len(apps) >= limit else list(reversed(apps))
    return top, bottom


def compute_performance_ranking(df: pd.DataFrame) -> list[dict]:
    """Rank apps by a composite performance score."""
    if df.empty:
        return []
    summary = df.groupby(["ad_unit_name", "ad_unit_id"]).agg({
        "ad_server_cpm_and_cpc_revenue": "sum",
        "ad_server_impressions": "sum",
        "ad_server_clicks": "sum",
        "ad_server_ad_requests": "sum",
    }).reset_index()

    # Derive rate metrics from totals — never average pre-computed rates.
    summary["ad_server_fill_rate"] = (
        (summary["ad_server_impressions"] / summary["ad_server_ad_requests"] * 100)
        .where(summary["ad_server_ad_requests"] > 0, 0)
    )
    summary["ad_server_ctr"] = (
        (summary["ad_server_clicks"] / summary["ad_server_impressions"] * 100)
        .where(summary["ad_server_impressions"] > 0, 0)
    )
    summary["ad_server_without_cpd_average_ecpm"] = (
        (summary["ad_server_cpm_and_cpc_revenue"] / summary["ad_server_impressions"] * 1000)
        .where(summary["ad_server_impressions"] > 0, 0)
    )

    # Composite score: weighted combination
    max_rev = summary["ad_server_cpm_and_cpc_revenue"].max() or 1
    max_imp = summary["ad_server_impressions"].max() or 1
    summary["score"] = (
        (summary["ad_server_cpm_and_cpc_revenue"] / max_rev) * 40 +
        (summary["ad_server_impressions"] / max_imp) * 25 +
        (summary["ad_server_fill_rate"] / 100) * 20 +
        (summary["ad_server_ctr"] / 100) * 15
    )
    summary = summary.sort_values("score", ascending=False)
    summary["rank"] = range(1, len(summary) + 1)
    return summary.to_dict(orient="records")


def compute_anomalies(df_current: pd.DataFrame, df_previous: pd.DataFrame, threshold: float = 20.0) -> list[dict]:
    """Detect anomalies by comparing current vs previous period."""
    if df_current.empty or df_previous.empty:
        return []

    current_by_app = df_current.groupby("ad_unit_name")["ad_server_cpm_and_cpc_revenue"].sum()
    previous_by_app = df_previous.groupby("ad_unit_name")["ad_server_cpm_and_cpc_revenue"].sum()

    anomalies = []
    for app_name in current_by_app.index:
        current_rev = float(current_by_app.get(app_name, 0))
        prev_rev = float(previous_by_app.get(app_name, 0))

        if prev_rev > 0:
            change_pct = ((current_rev - prev_rev) / prev_rev) * 100
            if abs(change_pct) >= threshold:
                severity = "High" if abs(change_pct) >= 50 else "Medium" if abs(change_pct) >= 30 else "Low"
                direction = "drop" if change_pct < 0 else "spike"
                anomalies.append({
                    "id": f"anomaly-{len(anomalies)+1}",
                    "ad_unit_name": app_name,
                    "metric": "revenue",
                    "currentValue": current_rev,
                    "previousValue": prev_rev,
                    "changePct": round(change_pct, 2),
                    "severity": severity,
                    "description": f"Revenue {direction} of {abs(change_pct):.1f}% for {app_name} (${prev_rev:.4f} → ${current_rev:.4f})",
                })

    # Also check impressions
    current_imp = df_current.groupby("ad_unit_name")["ad_server_impressions"].sum()
    previous_imp = df_previous.groupby("ad_unit_name")["ad_server_impressions"].sum()
    for app_name in current_imp.index:
        curr = float(current_imp.get(app_name, 0))
        prev = float(previous_imp.get(app_name, 0))
        if prev > 0:
            change = ((curr - prev) / prev) * 100
            if abs(change) >= threshold * 1.5:  # Higher threshold for impressions
                anomalies.append({
                    "id": f"anomaly-{len(anomalies)+1}",
                    "ad_unit_name": app_name,
                    "metric": "impressions",
                    "currentValue": curr,
                    "previousValue": prev,
                    "changePct": round(change, 2),
                    "severity": "High" if abs(change) >= 50 else "Medium",
                    "description": f"Impressions {'drop' if change < 0 else 'spike'} of {abs(change):.1f}% for {app_name}",
                })

    anomalies.sort(key=lambda x: abs(x["changePct"]), reverse=True)
    return anomalies


def generate_recommendations(summary: dict, apps: list[dict], anomalies: list[dict]) -> list[dict]:
    """Generate AI-style recommendations based on live data analysis."""
    recs = []
    rec_id = 1

    # Revenue concentration warning
    if apps and len(apps) >= 2:
        total_rev = sum(a.get("ad_server_cpm_and_cpc_revenue", 0) for a in apps)
        if total_rev > 0:
            top_rev = apps[0].get("ad_server_cpm_and_cpc_revenue", 0)
            top_pct = (top_rev / total_rev) * 100
            if top_pct > 50:
                recs.append({
                    "id": f"rec-{rec_id}", "category": "revenue",
                    "icon": "⚠️", "priority": "High",
                    "title": "Revenue Concentration Risk",
                    "description": f"{apps[0]['ad_unit_name']} accounts for {top_pct:.1f}% of total revenue. Diversify monetization to reduce dependency."
                })
                rec_id += 1

    # Low fill rate apps
    low_fill = [a for a in apps if a.get("ad_server_fill_rate", 0) < 50 and a.get("ad_server_ad_requests", 0) > 100]
    if low_fill:
        names = ", ".join(a["ad_unit_name"] for a in low_fill[:3])
        recs.append({
            "id": f"rec-{rec_id}", "category": "performance",
            "icon": "📉", "priority": "Medium",
            "title": f"{len(low_fill)} Apps with Low Fill Rate",
            "description": f"Consider adding more demand partners or adjusting floor prices for: {names}"
        })
        rec_id += 1

    # High CTR apps (potential for optimization)
    high_ctr = [a for a in apps if a.get("ad_server_ctr", 0) > 5]
    if high_ctr:
        recs.append({
            "id": f"rec-{rec_id}", "category": "recommendation",
            "icon": "🎯", "priority": "Medium",
            "title": f"{len(high_ctr)} Apps with High CTR",
            "description": "These apps show strong user engagement. Consider increasing ad density or testing premium ad formats."
        })
        rec_id += 1

    # Anomaly-driven recommendations
    drops = [a for a in anomalies if a["changePct"] < -20 and a["metric"] == "revenue"]
    if drops:
        recs.append({
            "id": f"rec-{rec_id}", "category": "anomaly",
            "icon": "🔴", "priority": "High",
            "title": f"{len(drops)} Apps with Significant Revenue Drops",
            "description": "Investigate demand partner issues, ad blocking, or traffic quality changes for affected apps."
        })
        rec_id += 1

    # Zero revenue apps
    zero_rev = [a for a in apps if a.get("ad_server_cpm_and_cpc_revenue", 0) == 0 and a.get("ad_server_impressions", 0) > 0]
    if zero_rev:
        recs.append({
            "id": f"rec-{rec_id}", "category": "performance",
            "icon": "💡", "priority": "Low",
            "title": f"{len(zero_rev)} Apps with Impressions but Zero Revenue",
            "description": "Review ad unit configuration and ensure proper monetization setup."
        })
        rec_id += 1

    # General health
    if summary.get("average_fill_rate", 0) < 70:
        recs.append({
            "id": f"rec-{rec_id}", "category": "performance",
            "icon": "📊", "priority": "Medium",
            "title": "Network Fill Rate Below 70%",
            "description": f"Current fill rate is {summary.get('average_fill_rate', 0):.1f}%. Add more demand partners or adjust targeting to improve fill."
        })
        rec_id += 1

    return recs


def generate_insights(summary: dict, apps: list[dict], trend: list[dict]) -> list[dict]:
    """Generate business insights from live data analysis."""
    insights = []
    ins_id = 1

    # Revenue insight
    rev = summary.get("total_revenue_usd", 0)
    imp = summary.get("total_impressions", 0)
    if rev > 0:
        insights.append({
            "id": f"ins-{ins_id}", "category": "revenue", "icon": "💰",
            "title": "Revenue Overview",
            "description": f"Total revenue of ${rev:.4f} from {imp:,} impressions across {summary.get('app_count', 0)} ad units."
        })
        ins_id += 1

    # eCPM insight
    ecpm = summary.get("average_ecpm", 0)
    if ecpm > 0:
        insights.append({
            "id": f"ins-{ins_id}", "category": "performance", "icon": "📈",
            "title": "eCPM Analysis",
            "description": f"Network average eCPM is ${ecpm:.4f}. {'Strong' if ecpm > 1 else 'Consider optimizing'} ad performance."
        })
        ins_id += 1

    # Top performer
    if apps:
        top = apps[0]
        total_rev = sum(a.get("ad_server_cpm_and_cpc_revenue", 0) for a in apps)
        top_pct = (top.get("ad_server_cpm_and_cpc_revenue", 0) / total_rev * 100) if total_rev > 0 else 0
        insights.append({
            "id": f"ins-{ins_id}", "category": "revenue", "icon": "🏆",
            "title": "Top Performer",
            "description": f"{top['ad_unit_name']} leads with {top_pct:.1f}% of total revenue."
        })
        ins_id += 1

    # Trend insight
    if trend and len(trend) >= 2:
        latest = trend[-1].get("revenue_usd", 0) if isinstance(trend[-1], dict) else 0
        previous = trend[-2].get("revenue_usd", 0) if isinstance(trend[-2], dict) else 0
        if previous > 0:
            change = ((latest - previous) / previous) * 100
            direction = "up" if change > 0 else "down"
            insights.append({
                "id": f"ins-{ins_id}", "category": "revenue", "icon": "📊",
                "title": f"Revenue Trending {'Up' if change > 0 else 'Down'}",
                "description": f"Revenue is {direction} {abs(change):.1f}% compared to the previous day."
            })
            ins_id += 1

    return insights


# ─── MCP Tools Registration ──────────────────────────────────────────────────

DATE_SCHEMA = {
    "type": "object",
    "properties": {
        "startDate": {"type": "string", "description": "Start date (YYYY-MM-DD) or preset: today, yesterday, last7days, last30days, thisMonth, lastMonth"},
        "endDate": {"type": "string", "description": "End date (YYYY-MM-DD). Defaults to startDate if not provided."},
        "startTime": {"type": "string", "description": "Start time (HH:MM). Defaults to 00:00."},
        "endTime": {"type": "string", "description": "End time (HH:MM). Defaults to 23:59."},
        "date": {"type": "string", "description": "Single date (YYYY-MM-DD) or preset. Used if startDate not provided."},
        "demand_channel": {"type": "string", "description": "Filter by demand channel: 'all' or 'programmatic' (default 'all')"},
        "force_refresh": {"type": "boolean", "description": "If true, bypass deduplication and generate a fresh GAM report."},
    },
}


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(name="getExecutiveSummary", description="Network-wide KPIs: revenue, impressions, clicks, CTR, fill rate, eCPM, ad requests, app count.", inputSchema=DATE_SCHEMA),
        types.Tool(name="getRevenue", description="Total revenue for the date range.", inputSchema=DATE_SCHEMA),
        types.Tool(name="getRevenueTrend", description="Day-by-day revenue, impressions, eCPM trend.", inputSchema=DATE_SCHEMA),
        types.Tool(name="getRevenueByApplication", description="Revenue breakdown by application, sorted descending.", inputSchema=DATE_SCHEMA),
        types.Tool(name="getRevenueByWebsite", description="Revenue breakdown by website (parsed from ad unit names).", inputSchema=DATE_SCHEMA),
        types.Tool(name="getTopApplications", description="Top N applications by revenue.", inputSchema={
            **DATE_SCHEMA,
            "properties": {**DATE_SCHEMA["properties"], "limit": {"type": "integer", "description": "Number of top apps (default 10)"}},
        }),
        types.Tool(name="getBottomApplications", description="Bottom N applications by revenue.", inputSchema={
            **DATE_SCHEMA,
            "properties": {**DATE_SCHEMA["properties"], "limit": {"type": "integer", "description": "Number of bottom apps (default 10)"}},
        }),
        types.Tool(name="getTopWebsites", description="Top N websites by revenue.", inputSchema={
            **DATE_SCHEMA,
            "properties": {**DATE_SCHEMA["properties"], "limit": {"type": "integer", "description": "Number of top websites (default 10)"}},
        }),
        types.Tool(name="getBottomWebsites", description="Bottom N websites by revenue.", inputSchema={
            **DATE_SCHEMA,
            "properties": {**DATE_SCHEMA["properties"], "limit": {"type": "integer", "description": "Number of bottom websites (default 10)"}},
        }),
        types.Tool(name="getImpressions", description="Total and per-app impression data.", inputSchema=DATE_SCHEMA),
        types.Tool(name="getClicks", description="Total and per-app click data.", inputSchema=DATE_SCHEMA),
        types.Tool(name="getCTR", description="Click-through rate analysis by app.", inputSchema=DATE_SCHEMA),
        types.Tool(name="geteCPM", description="eCPM analysis by app.", inputSchema=DATE_SCHEMA),
        types.Tool(name="getFillRate", description="Fill rate analysis by app.", inputSchema=DATE_SCHEMA),
        types.Tool(name="getAdRequests", description="Ad request volume by app.", inputSchema=DATE_SCHEMA),
        types.Tool(name="getPerformanceRanking", description="Apps ranked by composite performance score.", inputSchema=DATE_SCHEMA),
        types.Tool(name="getAnomalies", description="Detect revenue and impression anomalies by comparing to previous period.", inputSchema={
            **DATE_SCHEMA,
            "properties": {**DATE_SCHEMA["properties"], "threshold_pct": {"type": "number", "description": "Minimum % change to flag as anomaly (default 20)"}},
        }),
        types.Tool(name="getRecommendations", description="AI-generated recommendations based on live data analysis.", inputSchema=DATE_SCHEMA),
        types.Tool(name="generateFullReport", description="Complete analytics report with all sections in one response.", inputSchema=DATE_SCHEMA),
    ]


async def execute_tool_logic(name: str, arguments: dict) -> list[types.TextContent]:
    try:
        start_date, end_date, start_hour, end_hour = _resolve_dates(arguments)
        force_refresh = arguments.get("force_refresh", False)
        demand_channel = arguments.get("demand_channel", "all")

        # Fetch live data from GAM
        df = await gam.get_live_data_multi_day(start_date, end_date, force_refresh, demand_channel)
        
        # Filter by hour if hour dimension is present and hour bounds are restrictive
        if "hour" in df.columns and not df.empty:
            if start_hour > 0 or end_hour < 23:
                df = df[(df["hour"] >= start_hour) & (df["hour"] <= end_hour)]

        # ── Cache DataFrame + data summary for Ask GAM 360 chat ──
        if not df.empty:
            cache_key = _cache_key(str(start_date), str(end_date), demand_channel)
            summary = build_data_summary(df, start_date, end_date)
            _session_cache[cache_key] = {
                "df": df.copy(),
                "summary": summary,
                "stored_at": datetime.now(),
                "start": str(start_date),
                "end": str(end_date),
            }
            # Keep cache bounded — remove oldest if > 10 entries
            while len(_session_cache) > 10:
                oldest_key = next(iter(_session_cache))
                del _session_cache[oldest_key]
            log.info(f"[Chat Cache] Stored data for {cache_key} ({len(df)} rows, {len(summary.get('all_apps', []))} apps)")

        # ── Debug logging: raw totals before any formatting ──
        if not df.empty:
            raw_rev = float(df["ad_server_cpm_and_cpc_revenue"].sum())
            raw_imp = int(df["ad_server_impressions"].sum())
            raw_ecpm = (raw_rev / raw_imp * 1000) if raw_imp > 0 else 0
            log.info(
                "[DEBUG] Tool=%s | Date=%s→%s | Demand=%s\n"
                "  Raw Revenue:     %.6f\n"
                "  Raw Impressions: %d\n"
                "  Raw eCPM:        %.6f\n"
                "  Total rows:      %d",
                name, start_date, end_date, demand_channel,
                raw_rev, raw_imp, raw_ecpm, len(df),
            )

        result = {
            "status": "ok",
            "fetched_at": datetime.now().isoformat(),
            "startDate": str(start_date),
            "endDate": str(end_date),
            "startTime": f"{start_hour:02d}:00",
            "endTime": f"{end_hour:02d}:59",
        }

        if name == "getExecutiveSummary":
            result.update(compute_executive_summary(df, start_date, end_date))

        elif name == "getRevenue":
            rev = float(df["ad_server_cpm_and_cpc_revenue"].sum()) if not df.empty else 0
            result["total_revenue_usd"] = rev

        elif name == "getRevenueTrend":
            result["trend"] = compute_revenue_trend(df)

        elif name == "getRevenueByApplication":
            result["apps"] = compute_revenue_by_app(df)

        elif name == "getRevenueByWebsite":
            # Parse website/domain from ad unit names
            if not df.empty:
                df_copy = df.copy()
                df_copy["website"] = df_copy["ad_unit_name"].apply(_extract_domain)
                website_summary = df_copy.groupby("website").agg({
                    "ad_server_cpm_and_cpc_revenue": "sum",
                    "ad_server_impressions": "sum",
                    "ad_server_clicks": "sum",
                    "ad_server_ad_requests": "sum",
                }).reset_index().sort_values("ad_server_cpm_and_cpc_revenue", ascending=False)
                result["websites"] = website_summary.to_dict(orient="records")
            else:
                result["websites"] = []

        elif name == "getTopApplications":
            limit = int(arguments.get("limit", 10))
            apps = compute_revenue_by_app(df)
            result["apps"] = apps[:limit]

        elif name == "getBottomApplications":
            limit = int(arguments.get("limit", 10))
            apps = compute_revenue_by_app(df)
            result["apps"] = list(reversed(apps[-limit:])) if len(apps) >= limit else list(reversed(apps))

        elif name == "getTopWebsites":
            limit = int(arguments.get("limit", 10))
            if not df.empty:
                df_copy = df.copy()
                df_copy["website"] = df_copy["ad_unit_name"].apply(_extract_domain)
                ws = df_copy.groupby("website")["ad_server_cpm_and_cpc_revenue"].sum().reset_index()
                ws = ws.sort_values("ad_server_cpm_and_cpc_revenue", ascending=False).head(limit)
                result["websites"] = ws.to_dict(orient="records")
            else:
                result["websites"] = []

        elif name == "getBottomWebsites":
            limit = int(arguments.get("limit", 10))
            if not df.empty:
                df_copy = df.copy()
                df_copy["website"] = df_copy["ad_unit_name"].apply(_extract_domain)
                ws = df_copy.groupby("website")["ad_server_cpm_and_cpc_revenue"].sum().reset_index()
                ws = ws.sort_values("ad_server_cpm_and_cpc_revenue", ascending=True).head(limit)
                result["websites"] = ws.to_dict(orient="records")
            else:
                result["websites"] = []

        elif name == "getImpressions":
            if not df.empty:
                total = int(df["ad_server_impressions"].sum())
                by_app = df.groupby("ad_unit_name")["ad_server_impressions"].sum().reset_index()
                by_app = by_app.sort_values("ad_server_impressions", ascending=False)
                result["total_impressions"] = total
                result["by_app"] = by_app.to_dict(orient="records")
            else:
                result["total_impressions"] = 0
                result["by_app"] = []

        elif name == "getClicks":
            if not df.empty:
                total = int(df["ad_server_clicks"].sum())
                by_app = df.groupby("ad_unit_name")["ad_server_clicks"].sum().reset_index()
                by_app = by_app.sort_values("ad_server_clicks", ascending=False)
                result["total_clicks"] = total
                result["by_app"] = by_app.to_dict(orient="records")
            else:
                result["total_clicks"] = 0
                result["by_app"] = []

        elif name == "getCTR":
            if not df.empty:
                by_app = df.groupby("ad_unit_name").agg({
                    "ad_server_impressions": "sum",
                    "ad_server_clicks": "sum",
                }).reset_index()
                by_app["ctr"] = (by_app["ad_server_clicks"] / by_app["ad_server_impressions"] * 100).where(by_app["ad_server_impressions"] > 0, 0)
                by_app = by_app.sort_values("ctr", ascending=False)
                total_imp = int(df["ad_server_impressions"].sum())
                total_clicks = int(df["ad_server_clicks"].sum())
                result["average_ctr"] = (total_clicks / total_imp * 100) if total_imp > 0 else 0
                result["by_app"] = by_app.to_dict(orient="records")
            else:
                result["average_ctr"] = 0
                result["by_app"] = []

        elif name == "geteCPM":
            if not df.empty:
                by_app = df.groupby("ad_unit_name").agg({
                    "ad_server_cpm_and_cpc_revenue": "sum",
                    "ad_server_impressions": "sum",
                }).reset_index()
                by_app["ecpm"] = (by_app["ad_server_cpm_and_cpc_revenue"] / by_app["ad_server_impressions"] * 1000).where(by_app["ad_server_impressions"] > 0, 0)
                by_app = by_app.sort_values("ecpm", ascending=False)
                total_rev = float(df["ad_server_cpm_and_cpc_revenue"].sum())
                total_imp = int(df["ad_server_impressions"].sum())
                result["average_ecpm"] = (total_rev / total_imp * 1000) if total_imp > 0 else 0
                result["by_app"] = by_app.to_dict(orient="records")
            else:
                result["average_ecpm"] = 0
                result["by_app"] = []

        elif name == "getFillRate":
            if not df.empty:
                by_app = df.groupby("ad_unit_name").agg({
                    "ad_server_impressions": "sum",
                    "ad_server_ad_requests": "sum",
                }).reset_index()
                by_app["fill_rate"] = (by_app["ad_server_impressions"] / by_app["ad_server_ad_requests"] * 100).where(by_app["ad_server_ad_requests"] > 0, 0)
                by_app = by_app.sort_values("fill_rate", ascending=False)
                total_imp = int(df["ad_server_impressions"].sum())
                total_req = int(df["ad_server_ad_requests"].sum())
                result["average_fill_rate"] = (total_imp / total_req * 100) if total_req > 0 else 0
                result["by_app"] = by_app.to_dict(orient="records")
            else:
                result["average_fill_rate"] = 0
                result["by_app"] = []

        elif name == "getAdRequests":
            if not df.empty:
                total = int(df["ad_server_ad_requests"].sum())
                by_app = df.groupby("ad_unit_name")["ad_server_ad_requests"].sum().reset_index()
                by_app = by_app.sort_values("ad_server_ad_requests", ascending=False)
                result["total_ad_requests"] = total
                result["by_app"] = by_app.to_dict(orient="records")
            else:
                result["total_ad_requests"] = 0
                result["by_app"] = []

        elif name == "getPerformanceRanking":
            result["rankings"] = compute_performance_ranking(df)

        elif name == "getAnomalies":
            # Fetch previous period for comparison
            period_days = (end_date - start_date).days + 1
            prev_end = start_date - timedelta(days=1)
            prev_start = prev_end - timedelta(days=period_days - 1)
            try:
                df_previous = await gam.get_live_data_multi_day(prev_start, prev_end, force_refresh)
            except Exception as e:
                log.warning(f"Could not fetch previous period for anomaly detection: {e}")
                df_previous = pd.DataFrame()
            threshold = float(arguments.get("threshold_pct", 20.0))
            result["anomalies"] = compute_anomalies(df, df_previous, threshold)

        elif name == "getRecommendations":
            summary = compute_executive_summary(df, start_date, end_date)
            apps = compute_revenue_by_app(df)
            # Get anomalies for recommendations
            period_days = (end_date - start_date).days + 1
            prev_end = start_date - timedelta(days=1)
            prev_start = prev_end - timedelta(days=period_days - 1)
            try:
                df_previous = await gam.get_live_data_multi_day(prev_start, prev_end, force_refresh)
                anomalies = compute_anomalies(df, df_previous)
            except Exception:
                anomalies = []
            result["recommendations"] = generate_recommendations(summary, apps, anomalies)

        elif name == "generateFullReport":
            # Complete report — all sections in one response
            summary = compute_executive_summary(df, start_date, end_date)
            apps = compute_revenue_by_app(df)
            trend = compute_revenue_trend(df)
            top_apps, bottom_apps = compute_top_bottom_apps(df)
            rankings = compute_performance_ranking(df)

            # Previous period for anomalies
            period_days = (end_date - start_date).days + 1
            prev_end = start_date - timedelta(days=1)
            prev_start = prev_end - timedelta(days=period_days - 1)
            try:
                df_previous = await gam.get_live_data_multi_day(prev_start, prev_end, force_refresh)
                anomalies = compute_anomalies(df, df_previous)
            except Exception:
                anomalies = []

            recommendations = generate_recommendations(summary, apps, anomalies)
            insights = generate_insights(summary, apps, trend)

            result.update({
                "summary": summary,
                "apps": apps,
                "trend": trend,
                "topApps": top_apps,
                "bottomApps": bottom_apps,
                "rankings": rankings,
                "anomalies": anomalies,
                "recommendations": recommendations,
                "insights": insights,
            })
        else:
            return [types.TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}", "status": "error"}))]
        return [types.TextContent(type="text", text=json.dumps(result, default=str))]
    except Exception as e:
        log.exception(f"Tool {name} failed")
        return [types.TextContent(type="text", text=json.dumps({"error": str(e), "status": "error"}))]

@app.call_tool()
async def call_tool_wrapper(name: str, arguments: dict) -> list[types.TextContent]:
    return await execute_tool_logic(name, arguments)

# ─── Server Setup ─────────────────────────────────────────────────────────────

async def handle_sse(request):
    async with sse.connect_sse(request.scope, request.receive, request._send) as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())

async def handle_messages(request):
    await sse.handle_post_message(request.scope, request.receive, request._send)

async def handle_api_tool(request):
    """
    REST endpoint for the Next.js frontend.
    POST /api/tool  { "name": "toolName", "arguments": { ... } }
    Returns the MCP tool result as JSON.
    """
    if request.method == "OPTIONS":
        return JSONResponse({}, headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        })

    try:
        body = await request.json()
        tool_name = body.get("name", "")
        tool_args = body.get("arguments", {})

        results = await execute_tool_logic(tool_name, tool_args)

        if results and len(results) > 0:
            response_data = json.loads(results[0].text)
        else:
            response_data = {"error": "No result", "status": "error"}

        return JSONResponse(response_data, headers={
            "Access-Control-Allow-Origin": "*",
        })
    except Exception as e:
        log.exception(f"REST /api/tool error: {e}")
        return JSONResponse(
            {"error": str(e), "status": "error"},
            status_code=500,
            headers={"Access-Control-Allow-Origin": "*"},
        )

starlette_app = Starlette(
    debug=True,
    routes=[
        Route("/sse", endpoint=handle_sse),
        Route("/messages/", endpoint=handle_messages, methods=["POST"]),
        Route("/api/tool", endpoint=handle_api_tool, methods=["POST", "OPTIONS"]),
        Route("/api/chat", endpoint=handle_chat, methods=["POST", "OPTIONS"]),
    ],
    middleware=[
        Middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]),
    ],
)

if __name__ == "__main__":
    uvicorn.run(starlette_app, host="0.0.0.0", port=8000)
