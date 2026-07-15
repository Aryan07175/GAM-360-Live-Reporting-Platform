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
import math
import logging
import asyncio
import time
from contextlib import asynccontextmanager
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
import numpy as np


def sanitize_for_json(obj):
    """
    Recursively replace float('inf'), float('-inf'), and float('nan') with 0
    so the response is always valid JSON. Also converts numpy scalar types
    to native Python types.
    """
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_for_json(v) for v in obj]
    # Handle numpy integer types (np.int64, np.int32, etc.)
    if isinstance(obj, np.integer):
        return int(obj)
    # Handle numpy float types (np.float64, np.float32, etc.) AND native float
    if isinstance(obj, (float, np.floating)):
        if math.isnan(obj) or math.isinf(obj):
            return 0
        return float(obj)  # convert np.float64 → native float
    # Handle numpy bool
    if isinstance(obj, np.bool_):
        return bool(obj)
    return obj

import sys
import os
# Allow imports from the project root (fixes IDE warnings and CLI execution)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import time
from mcp_server.gam_client import GAMClient
from mcp_server.recipients_store import get_recipients, add_recipient, remove_recipient, get_preferences, update_preferences
from mcp_server.email_service import send_alert_email, send_daily_report_email, send_test_email, log_credential_status

_last_alert_sent = {}  # title -> timestamp

# AWS Bedrock service
try:
    from mcp_server.services.bedrock_service import (
        stream_bedrock_response,
        build_bedrock_messages,
        reset_client,
    )
    HAS_BEDROCK = True
except ImportError:
    HAS_BEDROCK = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("mcp_server")

# Log Gmail credential presence at startup (values never printed)
log_credential_status()

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

def build_chat_system_prompt(compact_summary: dict) -> str:
    """
    Build the system prompt with today's date injected so the model can
    compute exact calendar dates for any relative phrase the user types.
    """
    today = date.today()
    yesterday = today - timedelta(days=1)
    past7   = today - timedelta(days=7)
    past30  = today - timedelta(days=30)
    past45  = today - timedelta(days=45)
    past60  = today - timedelta(days=60)
    past90  = today - timedelta(days=90)
    past180 = today - timedelta(days=180)
    past365 = today - timedelta(days=365)
    mtd_start = today.replace(day=1)
    ytd_start = today.replace(month=1, day=1)
    last_month_end   = today.replace(day=1) - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    last_year_cal_start = today.replace(year=today.year - 1, month=1, day=1)
    last_year_cal_end   = today.replace(year=today.year - 1, month=12, day=31)

    import json as _json
    summary_str = _json.dumps(compact_summary, indent=2, default=str)

    return f"""You are **Ask GAM 360**, an AI analyst with LIVE access to Google Ad Manager data.
You can answer ANY question about revenue, impressions, clicks, eCPM, CTR, fill rate, ad requests,
or Ad Exchange match rate for ANY time period — not just what the dashboard currently shows.

## Tools Available
- **`query_gam_data`** (PRIMARY): Fetches LIVE data directly from the Google Ad Manager API
  for any date range, dimension, and metric. Use this for EVERY question involving a time period
  or a breakdown by app / website / ad unit / child network.
- **`query_data`** (SECONDARY): Aggregates/filters the current dashboard session data.
  Use only for follow-up comparisons within the same already-loaded session.

## CRITICAL RULES
1. **For ANY question, ALWAYS call `query_gam_data` first.** Do NOT answer from memory.
2. **NEVER state a number that was not returned by a tool in this conversation.**
3. Compute the exact YYYY-MM-DD dates from the Date Reference table below BEFORE calling the tool.
4. **DEFAULT (no time period mentioned):** Use start_date={ytd_start} (Jan 1 this year), end_date={today} (YTD).
   Always label the answer: “From January 1, {today.year} to today ({today.strftime('%B %-d, %Y')})…”
5. Keep answers concise: bold key numbers, 1–4 sentences max.
6. Format revenue as `$X.XX` (or `$X.XXXXXX` for very small values). Use commas for large numbers.
7. If GAM returns zero / empty data, say so honestly — don’t fabricate numbers.
8. For **Ad Exchange** questions (match rate, AdX revenue, AdX impressions), set channel="ad_exchange".
9. For **website** questions (e.g., “cardekho.com revenue”), set dimension="website" and pass filter_name=<domain>.
10. For **child network breakdown** (MCM), set dimension="child_network".

## Date Reference (today = {today.isoformat()})
| Phrase | start_date | end_date |
|---|---|---|
| today | {today} | {today} |
| yesterday | {yesterday} | {yesterday} |
| past 7 days / last 7 days | {past7} | {today} |
| past 30 days / last 30 days | {past30} | {today} |
| past 45 days | {past45} | {today} |
| past 60 days | {past60} | {today} |
| past 3 months / past 90 days | {past90} | {today} |
| past 6 months / last 6 months | {past180} | {today} |
| past 1 year / past 12 months / last year (rolling) | {past365} | {today} |
| this month / MTD | {mtd_start} | {today} |
| last month | {last_month_start} | {last_month_end} |
| this year / YTD | {ytd_start} | {today} |
| last year (calendar) | {last_year_cal_start} | {last_year_cal_end} |
| no period mentioned (default) | {ytd_start} | {today} |

## Metric Definitions

### Ad Server (direct-sold)
- **revenue** = `ad_server_cpm_and_cpc_revenue`: Ad Server CPM+CPC revenue (USD)
- **impressions** = `ad_server_impressions`: Ad Server impressions
- **clicks** = `ad_server_clicks`: Ad Server clicks
- **ctr** = derived: Clicks/Impressions x 100 (%)
- **ecpm** = derived: Revenue/Impressions x 1000 (USD)
- **ad_requests** = `ad_server_ad_requests`: Ad Server ad requests
- **fill_rate** = derived: Impressions/Ad Requests x 100 (%) — Ad Server only

### Ad Exchange (programmatic)
- **adx_revenue** = `ad_exchange_line_item_level_revenue`: AdX revenue only
- **adx_impressions** = `ad_exchange_line_item_level_impressions`: AdX impressions
- **adx_clicks** = `ad_exchange_line_item_level_clicks`: AdX clicks
- **adx_ctr** = `ad_exchange_line_item_level_ctr`: AdX CTR (%)
- **adx_ecpm** = `ad_exchange_line_item_level_average_ecpm`: AdX avg eCPM (USD)
- **match_rate** = derived: AdX Impressions/Total Requests x 100 (%) — use channel="ad_exchange"
- **programmatic_match_rate** = `programmatic_match_rate`: GAM native programmatic match rate

### AdSense
- **adsense_revenue** = `adsense_line_item_level_revenue`: AdSense revenue
- **adsense_impressions** = `adsense_line_item_level_impressions`: AdSense impressions
- **adsense_clicks** = `adsense_line_item_level_clicks`: AdSense clicks
- **adsense_ctr** = `adsense_line_item_level_ctr`: AdSense CTR (%)
- **adsense_ecpm** = `adsense_line_item_level_average_ecpm`: AdSense avg eCPM (USD)

### Network-Wide (all demand channels)
- **total_ad_requests** = `total_ad_requests`: True total ad requests (PREFERRED over ad_requests)
- **total_responses_served** = `total_responses_served`: Total responses served
- **total_fill_rate** = `total_fill_rate`: Network-wide fill rate (%)
- **total_code_served** = `total_code_served_count`: Total code served count

## Natural-Language to Tool Reference
| User phrase | metric= | channel= | dimension= |
|---|---|---|---|
| "fill rate" / "ad server fill rate" | fill_rate | ad_server | none |
| "total fill rate" / "overall fill rate" | total_fill_rate | all | none |
| "match rate" / "AdX match rate" | match_rate | ad_exchange | none |
| "programmatic match rate" | programmatic_match_rate | all | none |
| "total ad requests" | total_ad_requests | all | none |
| "unmatched ad requests" / "unmatched requests" | total_unmatched_ad_requests | all | none |
| "code served" / "total code served" | total_code_served | all | none |
| "responses served" / "total responses served" | total_responses_served | all | none |
| "AdX CTR" | adx_ctr | ad_exchange | none |
| "AdX eCPM" | adx_ecpm | ad_exchange | none |
| "AdSense revenue" | adsense_revenue | adsense | none |
| "AdSense eCPM" | adsense_ecpm | adsense | none |
| "total revenue" / "all demand revenue" | total_revenue | all | none |
| "total CPM and CPC revenue" | total_cpm_and_cpc_revenue | all | none |
| "total impressions" | total_impressions | all | none |
| "total clicks" | total_clicks | all | none |
| "total CTR" | total_ctr | all | none |
| "total eCPM" / "total average eCPM" | total_average_ecpm | all | none |
| "total eCPM with CPD" / "total average eCPM w/ CPD" | total_average_ecpm_with_cpd | all | none |
| "targeted impressions" / "total targeted impressions" | total_targeted_impressions | all | none |
| "targeted clicks" / "total targeted clicks" | total_targeted_clicks | all | none |
| "unfilled impressions" / "unfilled" | unfilled_impressions | all | none |
| "drop-off rate" / "dropoff rate" | drop_off_rate | all | none |
| "begin to render" / "inactive begin to render" | inactive_begin_to_render_impressions | all | none |
| "Active View eligible" / "total AV eligible" | total_active_view_eligible_impressions | all | none |
| "Active View measurable" / "total AV measurable" | total_active_view_measurable_impressions | all | none |
| "Active View viewable" / "total AV viewable" | total_active_view_viewable_impressions | all | none |
| "% measurable" / "AV measurable rate" | total_active_view_measurable_impressions_rate | all | none |
| "% viewable" / "viewable rate" / "AV viewable rate" | total_active_view_viewable_impressions_rate | all | none |
| "viewable time" / "avg viewable time" | total_active_view_average_viewable_time | all | none |
| "Active View revenue" / "total AV revenue" | total_active_view_revenue | all | none |
| "by app" / "by ad unit" | revenue | all | app |
| "top-level ad units" | revenue | all | ad_unit_top |
| "by website" / "by domain" | revenue | all | website |
| "by advertiser" | revenue | all | advertiser |
| "by country" | revenue | all | country |
| "by child network" / "MCM" | revenue | all | child_network |
| "muted impressions" / "mute eligible" / "overdelivered" / "rewards" / "unloaded" / "opportunities" / "audible and visible" | (UNSUPPORTED) | all | none |

**Note on UNSUPPORTED metrics:** For "muted impressions", "mute eligible impressions", "overdelivered impressions", "MCM auto-payment revenue", "rewards granted", "unloaded impressions due to CPU/network", "opportunities", and "Active View audible and visible at completion" -- these are UI-only or BETA columns not available in the SOAP Reporting API v202602. Report them as "not available for this period via the API" and direct the user to the native GAM UI report builder.

## Dimension Options
- `none` -- network-wide totals only (no breakdown)
- `app` / `ad_unit` -- breakdown by ad unit / mobile app name
- `ad_unit_top` -- breakdown by top-level ad unit (first segment before "/")
- `website` -- breakdown by website domain; use filter_name for a specific site
- `advertiser` -- breakdown by advertiser name
- `advertiser_classified` -- breakdown by classified advertiser
- `country` -- breakdown by country name
- `child_network` -- breakdown by MCM child publisher network code


## Few-Shot Examples
**Example 1 -- no time period (YTD default):**
User: "What is total revenue?"
-> Call: query_gam_data(start_date="{ytd_start}", end_date="{today}", metric="revenue", dimension="none", channel="all")
-> Answer: "From January 1, {today.year} to today ({today.strftime('%B %-d, %Y')}), total revenue was **$X.XX**."

**Example 2 -- yesterday:**
User: "Revenue yesterday"
-> Call: query_gam_data(start_date="{yesterday}", end_date="{yesterday}", metric="revenue", dimension="none", channel="all")

**Example 3 -- past 30 days:**
User: "Impressions past 30 days"
-> Call: query_gam_data(start_date="{past30}", end_date="{today}", metric="impressions", dimension="none", channel="all")

**Example 4 -- past 6 months:**
User: "Total revenue past 6 months"
-> Call: query_gam_data(start_date="{past180}", end_date="{today}", metric="revenue", dimension="none", channel="all")

**Example 5 -- past 1 year (rolling):**
User: "Revenue past 1 year"
-> Call: query_gam_data(start_date="{past365}", end_date="{today}", metric="revenue", dimension="none", channel="all")

**Example 6 -- Ad Exchange match rate:**
User: "Ad Exchange match rate yesterday"
-> Call: query_gam_data(start_date="{yesterday}", end_date="{yesterday}", metric="match_rate", dimension="none", channel="ad_exchange")

**Example 7 -- website revenue:**
User: "cardekho.com revenue past 30 days"
-> Call: query_gam_data(start_date="{past30}", end_date="{today}", metric="revenue", dimension="website", channel="all", filter_name="cardekho.com")

**Example 8 -- child network breakdown:**
User: "Revenue by child network code past 30 days"
-> Call: query_gam_data(start_date="{past30}", end_date="{today}", metric="revenue", dimension="child_network", channel="all")

**Example 9 -- by country:**
User: "Revenue by country this month"
-> Call: query_gam_data(start_date="{mtd_start}", end_date="{today}", metric="revenue", dimension="country", channel="all")

**Example 10 -- by advertiser:**
User: "Top advertisers by revenue past 7 days"
-> Call: query_gam_data(start_date="{past7}", end_date="{today}", metric="revenue", dimension="advertiser", channel="all")

**Example 11 -- total ad requests:**
User: "Total ad requests yesterday"
-> Call: query_gam_data(start_date="{yesterday}", end_date="{yesterday}", metric="total_ad_requests", dimension="none", channel="all")

**Example 12 -- AdSense eCPM:**
User: "AdSense eCPM past 7 days"
-> Call: query_gam_data(start_date="{past7}", end_date="{today}", metric="adsense_ecpm", dimension="none", channel="adsense")

**Rule: fill rate vs match rate -- NEVER substitute one for the other:**
- fill_rate = Ad Server: impressions/ad_requests (channel="ad_server")
- match_rate = Ad Exchange: AdX impressions/total requests (channel="ad_exchange")

## Current Dashboard Context (reference only — do NOT use these numbers to answer questions)
{summary_str}
"""


# ─── Live GAM Query for Chat ─────────────────────────────────────────────────

# Date-phrase presets the model may still pass (server resolves them as fallback)
def _resolve_chat_dates(start_raw: str, end_raw: str) -> tuple[date, date]:
    """
    Resolve start/end date strings for the chat query_gam_data tool.
    Accepts YYYY-MM-DD strings or common English presets.

    The model should already have computed real dates from the system prompt
    date reference table, but this provides a safety net for any phrase
    that slips through as a key word (e.g. "ytd", "past30days").

    Note on counting:
      'past N days' uses INCLUSIVE counting matching GAM UI: past 7 days = today - 7.
      'last N days' historically used exclusive (today - 6 = 7 rows incl. today).
      We standardise both to today - N for simplicity.
    """
    today = date.today()
    yesterday = today - timedelta(days=1)

    # Relativedelta-style month arithmetic without dateutil
    def months_ago(n: int) -> date:
        m = today.month - n
        y = today.year + m // 12 if m < 1 else today.year
        m = m % 12 or 12
        import calendar
        last_day = calendar.monthrange(y, m)[1]
        return today.replace(year=y, month=m, day=min(today.day, last_day))

    presets = {
        "today":           (today, today),
        "yesterday":       (yesterday, yesterday),
        # past N days (inclusive, matches GAM UI)
        "past7days":       (today - timedelta(days=7),   today),
        "past14days":      (today - timedelta(days=14),  today),
        "past30days":      (today - timedelta(days=30),  today),
        "past45days":      (today - timedelta(days=45),  today),
        "past60days":      (today - timedelta(days=60),  today),
        "past90days":      (today - timedelta(days=90),  today),
        "past180days":     (today - timedelta(days=180), today),
        "past365days":     (today - timedelta(days=365), today),
        # 'last N days' aliases
        "last7days":       (today - timedelta(days=7),   today),
        "last14days":      (today - timedelta(days=14),  today),
        "last30days":      (today - timedelta(days=30),  today),
        "last60days":      (today - timedelta(days=60),  today),
        "last90days":      (today - timedelta(days=90),  today),
        # month-based ranges
        "past3months":     (today - timedelta(days=90),  today),
        "past6months":     (today - timedelta(days=180), today),
        "last6months":     (today - timedelta(days=180), today),
        "past12months":    (today - timedelta(days=365), today),
        "past1year":       (today - timedelta(days=365), today),
        "lastyear":        (today - timedelta(days=365), today),
        "last1year":       (today - timedelta(days=365), today),
        # calendar-aligned periods
        "thismonth":       (today.replace(day=1), today),
        "mtd":             (today.replace(day=1), today),
        "lastmonth":       (
            (today.replace(day=1) - timedelta(days=1)).replace(day=1),
            today.replace(day=1) - timedelta(days=1),
        ),
        "thisyear":        (today.replace(month=1, day=1), today),
        "ytd":             (today.replace(month=1, day=1), today),
        "lastyearcal":     (
            today.replace(year=today.year - 1, month=1, day=1),
            today.replace(year=today.year - 1, month=12, day=31),
        ),
    }

    def _normalise(raw: str) -> str:
        """Strip whitespace, hyphens, underscores, spaces for key lookup."""
        return raw.lower().replace(" ", "").replace("-", "").replace("_", "")

    def _parse(raw: str) -> date:
        key = _normalise(raw)
        if key in presets:
            return presets[key][0]  # fallback: return start
        return datetime.strptime(raw, "%Y-%m-%d").date()

    start_key = _normalise(start_raw)
    if start_key in presets:
        return presets[start_key]

    return _parse(start_raw), _parse(end_raw)


async def execute_query_gam_data(input_dict: dict) -> dict:
    """
    Execute a live query_gam_data tool call from the Bedrock chat.

    Supported metrics: revenue, impressions, clicks, ctr, ecpm, fill_rate,
      ad_requests, total_ad_requests, total_fill_rate, total_responses_served,
      total_code_served, match_rate, programmatic_match_rate,
      adx_impressions, adx_revenue, adx_clicks, adx_ctr, adx_ecpm,
      adsense_impressions, adsense_clicks, adsense_revenue, adsense_ctr, adsense_ecpm

    Supported dimensions: none, app, ad_unit, ad_unit_top, website,
      child_network, advertiser, advertiser_classified, country
    """
    from mcp_server.gam_client import DIMENSION_MAP, DIMENSIONS_NEED_SEPARATE_REPORT

    today = date.today()
    ytd_start = today.replace(month=1, day=1)

    # ── Apply YTD default when no dates provided ─────────────────────────────
    start_raw = input_dict.get("start_date", "").strip()
    end_raw   = input_dict.get("end_date",   "").strip()
    if not start_raw:
        start_raw = ytd_start.isoformat()
        end_raw   = today.isoformat()
        log.info("[Chat:query_gam_data] No date provided — defaulting to YTD: %s to %s", start_raw, end_raw)

    dimension   = input_dict.get("dimension", "none")
    metric      = input_dict.get("metric", "revenue")
    channel     = input_dict.get("channel", "all")
    filter_name = (input_dict.get("filter_name") or "").strip()

    try:
        start_date, end_date = _resolve_chat_dates(start_raw, end_raw)
    except Exception as e:
        return {"error": f"Invalid date format: {e}. Use YYYY-MM-DD."}

    # ── Map channel → demand_channel for gam_client ──────────────────────────
    demand_map = {
        "all":         "all",
        "ad_server":   "all",
        "adsense":     "programmatic",
        "ad_exchange": "programmatic",
    }
    demand_channel = demand_map.get(channel, "all")

    # ── Resolve dimension → extra_dims + separate_report flag ────────────────
    gam_dim_name = DIMENSION_MAP.get(dimension)
    extra_dims: list[str] = []
    separate_report = False
    if gam_dim_name:
        extra_dims = [gam_dim_name]
        if gam_dim_name in DIMENSIONS_NEED_SEPARATE_REPORT:
            separate_report = True

    log.info(
        "[Chat:query_gam_data] Fetching LIVE — %s to %s | dim=%s metric=%s channel=%s "
        "filter=%r extra_dims=%s separate=%s",
        start_date, end_date, dimension, metric, channel,
        filter_name, extra_dims, separate_report,
    )

    try:
        df = await gam.get_live_data_multi_day(
            start_date, end_date, False, demand_channel,
            extra_dims or None, separate_report,
        )
    except Exception as e:
        log.error("[Chat:query_gam_data] GAM fetch failed: %s", e)
        return {"error": f"Failed to fetch data from Google Ad Manager: {e}"}

    if df.empty:
        return {
            "start_date": str(start_date),
            "end_date":   str(end_date),
            "dimension":  dimension,
            "metric":     metric,
            "channel":    channel,
            "total":      0,
            "rows":       [],
            "note":       "No data returned by GAM for this date range / channel combination.",
        }

    # ── Helper: safe column sum ───────────────────────────────────────────────
    def _col(name: str, default=0):
        if name in df.columns:
            v = df[name].sum()
            return float(v) if isinstance(default, float) else int(v)
        return default

    # ── Column mappings (metric name → DataFrame column for sort) ────────────
    METRIC_COL = {
        "revenue":                 "ad_server_cpm_and_cpc_revenue",
        "impressions":             "ad_server_impressions",
        "clicks":                  "ad_server_clicks",
        "ad_requests":             "ad_server_ad_requests",
        "ctr":                     None,
        "ecpm":                    None,
        "fill_rate":               None,
        "match_rate":              "adx_match_rate",
        "adx_impressions":         "adx_impressions",
        "adx_revenue":             "adx_revenue",
        "adx_clicks":              "adx_clicks",
        "adx_ctr":                 "ad_exchange_line_item_level_ctr",
        "adx_ecpm":                "ad_exchange_line_item_level_average_ecpm",
        "adsense_impressions":     "adsense_line_item_level_impressions",
        "adsense_clicks":          "adsense_line_item_level_clicks",
        "adsense_revenue":         "adsense_line_item_level_revenue",
        "adsense_ctr":             "adsense_line_item_level_ctr",
        "adsense_ecpm":            "adsense_line_item_level_average_ecpm",
        "total_ad_requests":       "total_ad_requests",
        "total_responses_served":  "total_responses_served",
        "total_fill_rate":         "total_fill_rate",
        "total_code_served":       "total_code_served_count",
        "programmatic_match_rate": "programmatic_match_rate",
        # --- New Total-group metrics ---
        "total_revenue":                            "total_line_item_level_all_revenue",
        "total_cpm_and_cpc_revenue":                "total_line_item_level_cpm_and_cpc_revenue",
        "total_impressions":                        "total_line_item_level_impressions",
        "total_clicks":                             "total_line_item_level_clicks",
        "total_targeted_impressions":               "total_line_item_level_targeted_impressions",
        "total_targeted_clicks":                    "total_line_item_level_targeted_clicks",
        "total_ctr":                                "total_line_item_level_ctr",
        "total_average_ecpm":                       "total_line_item_level_without_cpd_average_ecpm",
        "total_average_ecpm_with_cpd":              "total_line_item_level_with_cpd_average_ecpm",
        "total_unmatched_ad_requests":              "total_unmatched_ad_requests",
        "unfilled_impressions":                     "total_inventory_level_unfilled_impressions",
        "drop_off_rate":                            "dropoff_rate",
        "inactive_begin_to_render_impressions":     "ad_server_begin_to_render_impressions",
        # --- Total Active View ---
        "total_active_view_eligible_impressions":          "total_active_view_eligible_impressions",
        "total_active_view_measurable_impressions":        "total_active_view_measurable_impressions",
        "total_active_view_viewable_impressions":          "total_active_view_viewable_impressions",
        "total_active_view_measurable_impressions_rate":   "total_active_view_measurable_impressions_rate",
        "total_active_view_viewable_impressions_rate":     "total_active_view_viewable_impressions_rate",
        "total_active_view_average_viewable_time":         "total_active_view_average_viewable_time",
        "total_active_view_revenue":                       "total_active_view_revenue",
    }

    # ── Compute network-wide totals ───────────────────────────────────────────
    total_rev   = _col("ad_server_cpm_and_cpc_revenue", 0.0)
    total_imp   = _col("ad_server_impressions")
    total_clk   = _col("ad_server_clicks")
    total_req   = _col("ad_server_ad_requests")

    true_ad_req  = _col("total_ad_requests")
    true_resp    = _col("total_responses_served")
    true_unmatch = _col("total_unmatched_ad_requests")
    true_fill    = _col("total_fill_rate", 0.0)
    true_code    = _col("total_code_served_count")
    prog_match   = _col("programmatic_match_rate", 0.0)
    prog_resp    = _col("programmatic_responses_served")

    adx_imp      = _col("adx_impressions")
    adx_rev      = _col("adx_revenue", 0.0)
    adx_clk      = _col("adx_clicks")
    adx_ctr_val  = _col("ad_exchange_line_item_level_ctr", 0.0)
    adx_ecpm_val = _col("ad_exchange_line_item_level_average_ecpm", 0.0)

    as_imp  = _col("adsense_line_item_level_impressions")
    as_clk  = _col("adsense_line_item_level_clicks")
    as_rev  = _col("adsense_line_item_level_revenue", 0.0)
    as_ctr  = _col("adsense_line_item_level_ctr", 0.0)
    as_ecpm = _col("adsense_line_item_level_average_ecpm", 0.0)

    # Total-group totals
    total_all_rev   = _col("total_line_item_level_all_revenue", 0.0)
    total_cpm_cpc_rev = _col("total_line_item_level_cpm_and_cpc_revenue", 0.0)
    total_li_imp    = _col("total_line_item_level_impressions")
    total_li_clk    = _col("total_line_item_level_clicks")
    total_tgt_imp   = _col("total_line_item_level_targeted_impressions")
    total_tgt_clk   = _col("total_line_item_level_targeted_clicks")
    total_li_ctr    = _col("total_line_item_level_ctr", 0.0)
    total_ecpm_no_cpd = _col("total_line_item_level_without_cpd_average_ecpm", 0.0)
    total_ecpm_w_cpd  = _col("total_line_item_level_with_cpd_average_ecpm", 0.0)
    unfilled_imp    = _col("total_inventory_level_unfilled_impressions")
    dropoff         = _col("dropoff_rate", 0.0)
    begin_to_render = _col("ad_server_begin_to_render_impressions")

    # Total Active View totals
    av_eligible     = _col("total_active_view_eligible_impressions")
    av_measurable   = _col("total_active_view_measurable_impressions")
    av_viewable     = _col("total_active_view_viewable_impressions")
    av_meas_rate    = _col("total_active_view_measurable_impressions_rate", 0.0)
    av_view_rate    = _col("total_active_view_viewable_impressions_rate", 0.0)
    av_view_time    = _col("total_active_view_average_viewable_time", 0.0)
    av_revenue      = _col("total_active_view_revenue", 0.0)

    total_ecpm = round((total_rev / total_imp * 1000), 6) if total_imp > 0 else 0.0
    total_ctr  = round((total_clk / total_imp * 100),  4) if total_imp > 0 else 0.0
    fill_rate  = round((total_imp / total_req * 100),  2) if total_req > 0 else 0.0
    match_rate = round((adx_imp  / total_req * 100),   4) if total_req > 0 else 0.0

    best_fill  = round(float(true_fill), 2) if true_fill > 0 else fill_rate
    best_req   = true_ad_req if true_ad_req > 0 else total_req
    best_match = round(float(prog_match), 4) if prog_match > 0 else match_rate

    metric_total_map = {
        "revenue":                 round(total_rev, 6),
        "impressions":             total_imp,
        "clicks":                  total_clk,
        "ad_requests":             total_req,
        "total_ad_requests":       true_ad_req,
        "total_responses_served":  true_resp,
        "total_fill_rate":         best_fill,
        "total_code_served":       true_code,
        "ctr":                     total_ctr,
        "ecpm":                    total_ecpm,
        "fill_rate":               best_fill,
        "match_rate":              best_match,
        "programmatic_match_rate": best_match,
        "adx_impressions":         adx_imp,
        "adx_revenue":             round(adx_rev, 6),
        "adx_clicks":              adx_clk,
        "adx_ctr":                 round(adx_ctr_val, 4),
        "adx_ecpm":                round(adx_ecpm_val, 6),
        "adsense_impressions":     as_imp,
        "adsense_clicks":          as_clk,
        "adsense_revenue":         round(as_rev, 6),
        "adsense_ctr":             round(as_ctr, 4),
        "adsense_ecpm":            round(as_ecpm, 6),
        # Total-group
        "total_revenue":                            round(total_all_rev, 6),
        "total_cpm_and_cpc_revenue":                round(total_cpm_cpc_rev, 6),
        "total_impressions":                        total_li_imp,
        "total_clicks":                             total_li_clk,
        "total_targeted_impressions":               total_tgt_imp,
        "total_targeted_clicks":                    total_tgt_clk,
        "total_ctr":                                round(total_li_ctr, 4),
        "total_average_ecpm":                       round(total_ecpm_no_cpd, 6),
        "total_average_ecpm_with_cpd":              round(total_ecpm_w_cpd, 6),
        "total_unmatched_ad_requests":              true_unmatch,
        "unfilled_impressions":                     unfilled_imp,
        "drop_off_rate":                            round(dropoff, 4),
        "inactive_begin_to_render_impressions":     begin_to_render,
        # Total Active View
        "total_active_view_eligible_impressions":          av_eligible,
        "total_active_view_measurable_impressions":        av_measurable,
        "total_active_view_viewable_impressions":          av_viewable,
        "total_active_view_measurable_impressions_rate":   round(av_meas_rate, 4),
        "total_active_view_viewable_impressions_rate":     round(av_view_rate, 4),
        "total_active_view_average_viewable_time":         round(av_view_time, 4),
        "total_active_view_revenue":                       round(av_revenue, 6),
    }
    scalar_total = metric_total_map.get(metric, round(total_rev, 6))

    # For BETA/optional metrics — if value is 0 and column name suggests BETA,
    # we note it in the result so the AI can communicate it properly.
    BETA_METRICS = {
        "inactive_begin_to_render_impressions",
        "total_active_view_revenue",
        "total_active_view_eligible_impressions",
        "total_active_view_measurable_impressions",
        "total_active_view_viewable_impressions",
        "total_active_view_measurable_impressions_rate",
        "total_active_view_viewable_impressions_rate",
        "total_active_view_average_viewable_time",
    }
    # Metrics that are GENUINELY UNAVAILABLE for this API version
    UNSUPPORTED_METRICS = {
        "total_muted_impressions",
        "total_mute_eligible_impressions",
        "total_overdelivered_impressions",
        "total_mcm_autopayment_revenue",
        "total_rewards_granted",
        "total_unloaded_impressions_cpu",
        "total_unloaded_impressions_network",
        "total_opportunities",
        "total_active_view_audible_and_visible",
    }
    if metric in UNSUPPORTED_METRICS:
        return {
            "start_date": str(start_date),
            "end_date":   str(end_date),
            "metric":     metric,
            "channel":    channel,
            "primary_total": None,
            "rows": [],
            "note": (
                f"Metric '{metric}' is not available in the GAM SOAP Reporting API "
                "(v202602) for this account. It may exist in the UI under a different "
                "report type, or require a beta feature flag. Please check the native "
                "GAM report builder for availability."
            ),
        }

    result = {
        "start_date":                    str(start_date),
        "end_date":                      str(end_date),
        "dimension":                     dimension,
        "metric":                        metric,
        "channel":                       channel,
        # Core Ad Server totals
        "total_revenue_usd":             round(total_rev, 6),
        "total_impressions":             total_imp,
        "total_clicks":                  total_clk,
        "total_ad_requests":             best_req,
        "total_responses_served":        true_resp,
        "total_unmatched_ad_requests":   true_unmatch,
        "total_code_served_count":       true_code,
        "avg_ecpm_usd":                  total_ecpm,
        "avg_ctr_pct":                   total_ctr,
        "fill_rate_pct":                 best_fill,
        # Ad Exchange
        "adx_impressions":               adx_imp,
        "adx_revenue_usd":               round(adx_rev, 6),
        "adx_clicks":                    adx_clk,
        "adx_ctr_pct":                   round(adx_ctr_val, 4),
        "adx_ecpm_usd":                  round(adx_ecpm_val, 6),
        "adx_match_rate_pct":            match_rate,
        "programmatic_match_rate_pct":   best_match,
        "programmatic_responses_served": prog_resp,
        # AdSense
        "adsense_impressions":           as_imp,
        "adsense_clicks":                as_clk,
        "adsense_revenue_usd":           round(as_rev, 6),
        "adsense_ctr_pct":               round(as_ctr, 4),
        "adsense_ecpm_usd":              round(as_ecpm, 6),
        # Total-group (network-wide pre-aggregated)
        "total_all_revenue_usd":         round(total_all_rev, 6),
        "total_cpm_and_cpc_revenue_usd": round(total_cpm_cpc_rev, 6),
        "total_li_impressions":          total_li_imp,
        "total_li_clicks":               total_li_clk,
        "total_targeted_impressions":    total_tgt_imp,
        "total_targeted_clicks":         total_tgt_clk,
        "total_li_ctr_pct":              round(total_li_ctr, 4),
        "total_avg_ecpm_usd":            round(total_ecpm_no_cpd, 6),
        "total_avg_ecpm_with_cpd_usd":   round(total_ecpm_w_cpd, 6),
        "unfilled_impressions":          unfilled_imp,
        "drop_off_rate_pct":             round(dropoff, 4),
        "begin_to_render_impressions":   begin_to_render,
        # Total Active View
        "total_av_eligible_impressions":        av_eligible,
        "total_av_measurable_impressions":      av_measurable,
        "total_av_viewable_impressions":        av_viewable,
        "total_av_measurable_rate_pct":         round(av_meas_rate, 4),
        "total_av_viewable_rate_pct":           round(av_view_rate, 4),
        "total_av_average_viewable_time_sec":   round(av_view_time, 4),
        "total_av_revenue_usd":                 round(av_revenue, 6),
        # Primary metric
        "primary_metric":                metric,
        "primary_total":                 scalar_total,
        "rows":                          [],
    }

    # Add a note if the requested metric is BETA and returns 0
    if metric in BETA_METRICS and scalar_total == 0:
        result["note"] = (
            f"Metric '{metric}' returned 0. This may be a BETA feature not yet "
            "available for this date range or account. Verify in the native GAM "
            "report builder — if it shows data there, the column may need account-level "
            "enablement in the API."
        )

    # ── Helper: compute per-row derived stats ─────────────────────────────────
    def _add_derived_cols(g: pd.DataFrame) -> pd.DataFrame:
        g = g.copy()
        rev_c = next((c for c in ["ad_server_cpm_and_cpc_revenue",
                                   "total_line_item_level_cpm_and_cpc_revenue"]
                      if c in g.columns), None)
        imp_c = next((c for c in ["ad_server_impressions",
                                   "total_line_item_level_impressions"]
                      if c in g.columns), None)
        clk_c = next((c for c in ["ad_server_clicks",
                                   "total_line_item_level_clicks"]
                      if c in g.columns), None)
        req_c = next((c for c in ["ad_server_ad_requests", "total_ad_requests"]
                      if c in g.columns), None)
        if rev_c and imp_c:
            g["ecpm_usd"] = (g[rev_c] / g[imp_c] * 1000).where(g[imp_c] > 0, 0).round(6)
        if clk_c and imp_c:
            g["ctr_pct"] = (g[clk_c] / g[imp_c] * 100).where(g[imp_c] > 0, 0).round(4)
        if imp_c and req_c:
            g["fill_rate_pct"] = (g[imp_c] / g[req_c] * 100).where(g[req_c] > 0, 0).round(2)
        if "adx_impressions" in g.columns and req_c:
            g["adx_match_rate_pct"] = (
                g["adx_impressions"] / g[req_c] * 100
            ).where(g[req_c] > 0, 0).round(4)
        return g

    # Aggregation columns — different for separate-report mode
    if separate_report:
        AGG_COLS = {c: "sum" for c in [
            "total_line_item_level_cpm_and_cpc_revenue",
            "total_line_item_level_impressions",
            "total_line_item_level_clicks",
            "total_ad_requests", "total_responses_served", "total_fill_rate",
        ] if c in df.columns}
    else:
        AGG_COLS = {
            "ad_server_cpm_and_cpc_revenue": "sum",
            "ad_server_impressions":         "sum",
            "ad_server_clicks":              "sum",
            "ad_server_ad_requests":         "sum",
        }
        for extra_c in [
            "adx_impressions", "adx_revenue", "adx_clicks",
            "adsense_line_item_level_impressions", "adsense_line_item_level_clicks",
            "adsense_line_item_level_revenue", "adsense_line_item_level_ctr",
            "adsense_line_item_level_average_ecpm",
            "ad_exchange_line_item_level_ctr", "ad_exchange_line_item_level_average_ecpm",
            "total_ad_requests", "total_responses_served",
            "programmatic_match_rate", "programmatic_responses_served",
        ]:
            if extra_c in df.columns:
                AGG_COLS[extra_c] = "sum"

    def _sort_and_store(grouped: pd.DataFrame):
        sort_col = METRIC_COL.get(metric)
        if not sort_col or sort_col not in grouped.columns:
            for cand in ["ad_server_cpm_and_cpc_revenue",
                         "total_line_item_level_cpm_and_cpc_revenue"]:
                if cand in grouped.columns:
                    sort_col = cand
                    break
        if sort_col and sort_col in grouped.columns:
            grouped = grouped.sort_values(sort_col, ascending=False)
        result["rows"] = sanitize_for_json(grouped.head(50).to_dict(orient="records"))

    # ── Dimension breakdown ───────────────────────────────────────────────────

    if dimension in ("app", "ad_unit"):
        if "ad_unit_name" not in df.columns:
            result["note"] = "ad_unit_name not available."
        else:
            grouped = df.groupby("ad_unit_name").agg(AGG_COLS).reset_index()
            grouped = grouped.rename(columns={"ad_unit_name": "name"})
            if filter_name:
                mask = grouped["name"].str.lower().str.contains(
                    filter_name.lower().replace("www.", ""), na=False)
                if mask.any():
                    grouped = grouped[mask]
            grouped = _add_derived_cols(grouped)
            _sort_and_store(grouped)

    elif dimension == "ad_unit_top":
        if "ad_unit_name" not in df.columns:
            result["note"] = "ad_unit_name not available."
        else:
            df_copy = df.copy()
            df_copy["top_unit"] = df_copy["ad_unit_name"].apply(
                lambda n: n.split("/")[0].strip() if isinstance(n, str) else n)
            grouped = df_copy.groupby("top_unit").agg(AGG_COLS).reset_index()
            grouped = grouped.rename(columns={"top_unit": "name"})
            if filter_name:
                mask = grouped["name"].str.lower().str.contains(
                    filter_name.lower().replace("www.", ""), na=False)
                if mask.any():
                    grouped = grouped[mask]
            grouped = _add_derived_cols(grouped)
            _sort_and_store(grouped)

    elif dimension == "website":
        if "ad_unit_name" not in df.columns:
            result["note"] = "ad_unit_name not available."
        else:
            import re as _re
            def _norm_domain(s: str) -> str:
                s = s.lower()
                s = _re.sub(r'^https?://', '', s)
                s = _re.sub(r'^www\.', '', s)
                return s.strip('/')

            df_copy = df.copy()
            df_copy["name"] = df_copy["ad_unit_name"].apply(_extract_domain)
            grouped = df_copy.groupby("name").agg(AGG_COLS).reset_index()
            grouped = _add_derived_cols(grouped)
            if filter_name:
                qn = _norm_domain(filter_name)
                exact = grouped["name"].apply(_norm_domain) == qn
                if exact.any():
                    grouped = grouped[exact]
                else:
                    sub = grouped["name"].apply(_norm_domain).str.contains(qn, regex=False, na=False)
                    if sub.any():
                        grouped = grouped[sub]
            _sort_and_store(grouped)

    elif dimension == "child_network":
        group_col = "child_network_code" if "child_network_code" in df.columns else None
        if group_col:
            grouped = df.groupby(group_col).agg(AGG_COLS).reset_index()
            grouped = grouped.rename(columns={group_col: "name"})
            grouped = _add_derived_cols(grouped)
            _sort_and_store(grouped)
        else:
            result["note"] = (
                "child_network_code column not present. "
                "This account may not be an MCM network manager."
            )

    elif dimension in ("advertiser", "advertiser_classified"):
        group_col = (
            "advertiser_name" if dimension == "advertiser"
            else "classified_advertiser_name"
        )
        if group_col not in df.columns:
            result["note"] = (
                f"'{group_col}' not available. Advertiser dimension may not be "
                "supported for this account/date range."
            )
        else:
            grouped = df.groupby(group_col).agg(AGG_COLS).reset_index()
            grouped = grouped.rename(columns={group_col: "name"})
            if filter_name:
                mask = grouped["name"].str.lower().str.contains(filter_name.lower(), na=False)
                if mask.any():
                    grouped = grouped[mask]
            grouped = _add_derived_cols(grouped)
            _sort_and_store(grouped)

    elif dimension == "country":
        group_col = "country_name" if "country_name" in df.columns else None
        if group_col:
            grouped = df.groupby(group_col).agg(AGG_COLS).reset_index()
            grouped = grouped.rename(columns={group_col: "name"})
            if filter_name:
                mask = grouped["name"].str.lower().str.contains(filter_name.lower(), na=False)
                if mask.any():
                    grouped = grouped[mask]
            grouped = _add_derived_cols(grouped)
            _sort_and_store(grouped)
        else:
            result["note"] = "country_name column not present in this report."

    # dimension="none": rows stays empty — totals only
    log.info(
        "[Chat:query_gam_data] Done — %s to %s | %s=%s | %d rows",
        start_date, end_date, metric, scalar_total, len(result["rows"]),
    )
    return result


# ─── Chat Endpoint ───────────────────────────────────────────────────────────

def _make_tool_executor(cached_df):
    """
    Return an ASYNC tool executor closure.

    Handles two tools:
    - query_gam_data: goes live to the GAM API (async, any date range)
    - query_data:     aggregates the in-session cached DataFrame (sync wrapped)
    """
    async def _execute(tool_name: str, input_dict: dict) -> dict:
        if tool_name == "query_gam_data":
            return await execute_query_gam_data(input_dict)

        if tool_name == "query_data":
            # Run sync function in a thread to keep event loop free
            return await asyncio.to_thread(
                execute_query_data,
                cached_df,
                input_dict.get("operation", "sum"),
                input_dict.get("dimension"),
                input_dict.get("metric"),
                input_dict.get("filters"),
                int(input_dict.get("limit", 10)),
            )

        return {"error": f"Unknown tool: {tool_name}"}

    return _execute


async def handle_chat(request):
    """
    POST /api/chat — SSE streaming chat endpoint.
    Accepts { session_id, message, history[], date_range: { startDate, endDate } }
    Streams AWS Bedrock (Claude) responses token-by-token as SSE events.

    The chat now calls query_gam_data directly for any date / metric question,
    so it is no longer limited to whatever date range the dashboard has loaded.
    """
    if request.method == "OPTIONS":
        return JSONResponse({}, headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        })

    if not HAS_BEDROCK:
        return JSONResponse(
            {"error": "AWS Boto3 SDK not installed. Run: pip install boto3"},
            status_code=500,
            headers={"Access-Control-Allow-Origin": "*"},
        )

    try:
        body = await request.json()
        message = body.get("message", "").strip()
        history = body.get("history", [])
        date_range = body.get("date_range", {})

        if not message:
            return JSONResponse(
                {"error": "No message provided"},
                status_code=400,
                headers={"Access-Control-Allow-Origin": "*"},
            )

        # ── Pull dashboard session cache (used for query_data fallback only) ──
        start_str  = date_range.get("startDate", "")
        end_str    = date_range.get("endDate", "")
        demand     = date_range.get("demandChannel", "all")
        cache_key  = _cache_key(start_str, end_str, demand)

        cached = _session_cache.get(cache_key)
        if not cached and _session_cache:
            cache_key = list(_session_cache.keys())[-1]
            cached = _session_cache[cache_key]

        # Provide a lightweight context summary (reference only — chat uses tool for real numbers)
        data_summary = cached["summary"] if cached else {}
        cached_df    = cached["df"]      if cached else pd.DataFrame()

        compact_summary = {
            "dashboard_period":  data_summary.get("period", f"{start_str} to {end_str}" if start_str else "unknown"),
            "metrics":           data_summary.get("metrics", {}),
            "top_apps":          data_summary.get("top_apps", [])[:5],
        }

        # ── Build system prompt (includes today's date reference table) ────────
        system_prompt = build_chat_system_prompt(compact_summary)

        # ── Build Bedrock message list (history + new message) ─────────────────
        bedrock_messages = build_bedrock_messages(history, message)

        log.info("[Chat] session=%s message=%.80s...", cache_key, message)

        # ── Stream via the Bedrock service ────────────────────────────────────
        return StreamingResponse(
            stream_bedrock_response(
                messages=bedrock_messages,
                system_prompt=system_prompt,
                tool_executor=_make_tool_executor(cached_df),
            ),
            media_type="text/event-stream",
            headers={
                "Access-Control-Allow-Origin": "*",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    except Exception as e:
        log.exception("[Chat] Request error: %s", e)
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

def compute_alerts(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []
        
    summary = df.groupby(["ad_unit_name"]).agg({
        "ad_server_impressions": "sum",
        "ad_server_cpm_and_cpc_revenue": "sum",
        "ad_server_ad_requests": "sum",
        "ad_server_clicks": "sum"
    }).reset_index()
    
    alerts = []
    for _, row in summary.iterrows():
        app_name = row["ad_unit_name"]
        imp = int(row["ad_server_impressions"])
        rev = float(row["ad_server_cpm_and_cpc_revenue"])
        req = int(row["ad_server_ad_requests"])
        clicks = int(row["ad_server_clicks"])
        
        fill_rate = (imp / req * 100) if req > 0 else 0
        ctr = (clicks / imp * 100) if imp > 0 else 0
        ecpm = (rev / imp * 1000) if imp > 0 else 0
        
        if req > 500 and imp == 0:
            alerts.append({"title": f"Zero Fill Rate in {app_name}", "severity": "critical", "metric": "Fill Rate", "value": "0%"})
        elif req > 1000 and 0 < fill_rate < 30:
            alerts.append({"title": f"Very low fill rate ({fill_rate:.1f}%) in {app_name}", "severity": "warning", "metric": "Fill Rate", "value": f"{fill_rate:.1f}%"})
            
        if imp > 1000 and ctr > 15:
            alerts.append({"title": f"Suspiciously high CTR ({ctr:.1f}%) in {app_name}", "severity": "warning", "metric": "CTR", "value": f"{ctr:.1f}%"})
            
        if imp > 5000 and ecpm < 0.10 and ecpm > 0:
            alerts.append({"title": f"Extremely low eCPM (${ecpm:.2f}) in {app_name}", "severity": "warning", "metric": "eCPM", "value": f"${ecpm:.2f}"})
            
    return alerts


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
        
    # Sum only absolute metrics to avoid summing percentages mathematically incorrectly
    summary = df.groupby(["ad_unit_name", "ad_unit_id"]).agg({
        "ad_server_cpm_and_cpc_revenue": "sum",
        "ad_server_impressions": "sum",
        "ad_server_clicks": "sum",
        "ad_server_ad_requests": "sum",
    }).reset_index()
    
    # Safely recalculate derived metrics — replace inf AND nan (both produced by division by 0)
    summary["ad_server_ctr"] = (summary["ad_server_clicks"] / summary["ad_server_impressions"] * 100).replace([np.inf, -np.inf], 0).fillna(0)
    summary["ad_server_fill_rate"] = (summary["ad_server_impressions"] / summary["ad_server_ad_requests"] * 100).replace([np.inf, -np.inf], 0).fillna(0)
    summary["ad_server_without_cpd_average_ecpm"] = (summary["ad_server_cpm_and_cpc_revenue"] / summary["ad_server_impressions"] * 1000).replace([np.inf, -np.inf], 0).fillna(0)
    
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
    """
    Detect meaningful revenue and impression anomalies by comparing current vs previous period.

    Improvements over the naive % change approach:
    - Minimum absolute revenue floor ($0.50) — eliminates near-zero / new-app false positives
    - Minimum absolute impression floor (500 impressions) — eliminates tiny traffic noise
    - Minimum previous period value check — a new app going from $0 to $0.01 is NOT an anomaly
    - Smart severity tiers: Low / Medium / High / Critical
    - Results capped at 50 to keep the UI manageable
    - Drops are prioritised over spikes (drops are more actionable)
    """
    if df_current.empty or df_previous.empty:
        return []

    anomalies = []

    # ── Revenue anomalies ──────────────────────────────────────────────────────
    MIN_REVENUE_FLOOR = 0.50          # minimum $ in either period to care about
    MIN_REVENUE_CHANGE = threshold    # % threshold (default 20%)

    current_rev = df_current.groupby("ad_unit_name")["ad_server_cpm_and_cpc_revenue"].sum()
    previous_rev = df_previous.groupby("ad_unit_name")["ad_server_cpm_and_cpc_revenue"].sum()

    for app_name in current_rev.index:
        curr = float(current_rev.get(app_name, 0))
        prev = float(previous_rev.get(app_name, 0))

        # Skip if both periods have negligible revenue (new/inactive apps)
        if prev < MIN_REVENUE_FLOOR and curr < MIN_REVENUE_FLOOR:
            continue

        # Skip if previous period had no revenue (brand new app — not an anomaly)
        if prev < MIN_REVENUE_FLOOR:
            continue

        change_pct = ((curr - prev) / prev) * 100

        # Only flag if change is significant enough
        if abs(change_pct) < MIN_REVENUE_CHANGE:
            continue

        # Severity tiers
        abs_pct = abs(change_pct)
        if abs_pct >= 200:
            severity = "Critical"
        elif abs_pct >= 80:
            severity = "High"
        elif abs_pct >= 40:
            severity = "Medium"
        else:
            severity = "Low"

        direction = "drop" if change_pct < 0 else "spike"
        anomalies.append({
            "id": f"anomaly-{len(anomalies)+1}",
            "ad_unit_name": app_name,
            "metric": "revenue",
            "currentValue": round(curr, 4),
            "previousValue": round(prev, 4),
            "changePct": round(change_pct, 2),
            "severity": severity,
            "description": (
                f"Revenue {direction} of {abs_pct:.1f}% for {app_name} "
                f"(${prev:.4f} → ${curr:.4f})"
            ),
        })

    # ── Impression anomalies ───────────────────────────────────────────────────
    MIN_IMP_FLOOR = 500               # minimum impressions in previous period to care about
    MIN_IMP_CHANGE = threshold * 2    # impressions need 2x the revenue threshold to flag (default 40%)

    current_imp = df_current.groupby("ad_unit_name")["ad_server_impressions"].sum()
    previous_imp = df_previous.groupby("ad_unit_name")["ad_server_impressions"].sum()

    for app_name in current_imp.index:
        curr = float(current_imp.get(app_name, 0))
        prev = float(previous_imp.get(app_name, 0))

        # Skip tiny traffic — noise, not signal
        if prev < MIN_IMP_FLOOR:
            continue

        change_pct = ((curr - prev) / prev) * 100

        if abs(change_pct) < MIN_IMP_CHANGE:
            continue

        abs_pct = abs(change_pct)
        if abs_pct >= 200:
            severity = "Critical"
        elif abs_pct >= 100:
            severity = "High"
        elif abs_pct >= 60:
            severity = "Medium"
        else:
            severity = "Low"

        direction = "drop" if change_pct < 0 else "spike"
        anomalies.append({
            "id": f"anomaly-{len(anomalies)+1}",
            "ad_unit_name": app_name,
            "metric": "impressions",
            "currentValue": int(curr),
            "previousValue": int(prev),
            "changePct": round(change_pct, 2),
            "severity": severity,
            "description": (
                f"Impressions {direction} of {abs_pct:.1f}% for {app_name} "
                f"({int(prev):,} → {int(curr):,})"
            ),
        })

    # Sort: drops first (more critical), then by absolute % change descending
    anomalies.sort(key=lambda x: (x["changePct"] > 0, -abs(x["changePct"])))

    # Re-assign sequential IDs after sort
    for i, a in enumerate(anomalies):
        a["id"] = f"anomaly-{i+1}"

    # Cap at 50 to keep UI usable
    return anomalies[:50]


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

        # ── Email Notifications (Alerts) ──
        if not df.empty:
            def _trigger_alerts():
                alerts = compute_alerts(df)
                if not alerts:
                    return
                prefs = get_preferences()
                recipients = get_recipients()
                to_emails = [r["email"] for r in recipients]
                if not to_emails:
                    log.info("[EMAIL_SKIPPED] No recipients configured — skipping alert emails.")
                    return

                now = time.time()
                for alert in alerts:
                    sev = alert["severity"]
                    title = alert["title"]

                    if sev == "critical" and not prefs.get("critical_alerts"):
                        log.info("[EMAIL_SKIPPED] critical_alerts toggle is OFF — skipping: %s", title)
                        continue
                    if sev == "warning" and not prefs.get("warning_alerts"):
                        log.info("[EMAIL_SKIPPED] warning_alerts toggle is OFF — skipping: %s", title)
                        continue

                    # 30-second dedup per alert title
                    if title in _last_alert_sent and now - _last_alert_sent[title] < 30:
                        continue

                    _last_alert_sent[title] = now

                    async def _send_and_log(a=alert, emails=to_emails, p=prefs):
                        try:
                            result = await asyncio.to_thread(send_alert_email, a, emails, p)
                            if result.get("status") != "success":
                                log.error("[EMAIL_SEND_FAILED] Alert email failed: %s", result)
                        except Exception as exc:
                            log.error("[EMAIL_SEND_FAILED] Exception sending alert email: %s", exc, exc_info=True)

                    asyncio.create_task(_send_and_log())

            _trigger_alerts()

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
        return [types.TextContent(type="text", text=json.dumps(sanitize_for_json(result), default=str))]
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

        return JSONResponse(sanitize_for_json(response_data), headers={
            "Access-Control-Allow-Origin": "*",
        })
    except Exception as e:
        log.exception(f"REST /api/tool error: {e}")
        return JSONResponse(
            {"error": str(e), "status": "error"},
            status_code=500,
            headers={"Access-Control-Allow-Origin": "*"},
        )

async def daily_report_loop():
    """Runs once daily to generate and email the executive report."""
    log.info("Started daily report background job.")
    while True:
        try:
            await asyncio.sleep(86400)

            prefs = get_preferences()
            if not prefs.get("daily_report"):
                log.info("[EMAIL_SKIPPED] Daily report emails toggle is OFF — skipping.")
                continue

            recipients = get_recipients()
            to_emails = [r["email"] for r in recipients]
            if not to_emails:
                log.info("[EMAIL_SKIPPED] No recipients configured — skipping daily report.")
                continue

            log.info("[EMAIL_DAILY] Generating daily report for %d recipient(s)...", len(to_emails))
            today = date.today()
            yesterday = today - timedelta(days=1)

            df = await gam.get_live_data_multi_day(yesterday, yesterday, force_refresh=True)
            if df.empty:
                log.warning("[EMAIL_DAILY] DataFrame empty — skipping daily report email.")
                continue

            report_data = {
                "executive_summary": compute_executive_summary(df, yesterday, yesterday),
                "top_apps": compute_revenue_by_app(df)[:10],
            }

            day_before = yesterday - timedelta(days=1)
            df_prev = await gam.get_live_data_multi_day(day_before, day_before, force_refresh=True)
            report_data["anomalies"] = compute_anomalies(df, df_prev)
            report_data["recommendations"] = []

            async def _send_daily(rd=report_data, emails=to_emails):
                try:
                    result = await asyncio.to_thread(send_daily_report_email, rd, emails)
                    if result.get("status") == "success":
                        log.info("[EMAIL_DAILY] Daily report sent successfully to %s", emails)
                    else:
                        log.error("[EMAIL_SEND_FAILED] Daily report email failed: %s", result)
                except Exception as exc:
                    log.error("[EMAIL_SEND_FAILED] Exception in daily report email: %s", exc, exc_info=True)

            asyncio.create_task(_send_daily())

        except asyncio.CancelledError:
            break
        except Exception as e:
            log.error("[EMAIL_DAILY] Unexpected error in daily report loop: %s", e, exc_info=True)
            await asyncio.sleep(60)

async def handle_api_recipients(request):
    if request.method == "OPTIONS":
        return JSONResponse({}, headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        })
    if request.method == "GET":
        data = {
            "recipients": get_recipients(),
            "preferences": get_preferences()
        }
        return JSONResponse(data, headers={"Access-Control-Allow-Origin": "*"})
    if request.method == "POST":
        body = await request.json()
        try:
            if "preferences" in body:
                prefs = update_preferences(body["preferences"])
                return JSONResponse({"preferences": prefs}, headers={"Access-Control-Allow-Origin": "*"})
            else:
                email = body.get("email")
                label = body.get("label", "")
                if not email:
                    raise ValueError("Email is required")
                new_rec = add_recipient(email, label)
                return JSONResponse(new_rec, headers={"Access-Control-Allow-Origin": "*"})
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=400, headers={"Access-Control-Allow-Origin": "*"})

async def handle_api_recipients_delete(request):
    if request.method == "OPTIONS":
        return JSONResponse({}, headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        })
    if request.method == "DELETE":
        recipient_id = request.path_params.get("id")
        success = remove_recipient(recipient_id)
        return JSONResponse({"success": success}, headers={"Access-Control-Allow-Origin": "*"})

async def handle_api_test_email(request):
    """POST /api/test-email — send a diagnostic test email and return the full result."""
    if request.method == "OPTIONS":
        return JSONResponse({}, headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        })

    try:
        body = await request.json()
        to_email = body.get("email")

        recipients = get_recipients()
        log.info("[TEST_EMAIL] Current recipients in store: %s", [r['email'] for r in recipients])

        if not to_email:
            # Fall back to first saved recipient
            if recipients:
                to_email = recipients[0]["email"]
            else:
                return JSONResponse(
                    {"status": "error", "error": "No email provided and no recipients saved."},
                    status_code=400,
                    headers={"Access-Control-Allow-Origin": "*"},
                )

        log.info("[TEST_EMAIL] Sending test email to: %s", to_email)
        result = await asyncio.to_thread(send_test_email, to_email)
        log.info("[TEST_EMAIL] Result: %s", result)

        status_code = 200 if result.get("status") == "success" else 500
        return JSONResponse(result, status_code=status_code, headers={"Access-Control-Allow-Origin": "*"})

    except Exception as e:
        log.error("[TEST_EMAIL] Exception: %s", e, exc_info=True)
        return JSONResponse(
            {"status": "error", "error": str(e)},
            status_code=500,
            headers={"Access-Control-Allow-Origin": "*"},
        )

async def handle_health(request):
    """
    GET /health — lightweight health-check endpoint.
    Returns instantly without making any GAM or Bedrock calls.
    Used by Render's health check and the frontend keep-alive ping.
    """
    _start_time = getattr(handle_health, "_start_time", None)
    if _start_time is None:
        handle_health._start_time = time.time()
    uptime_s = int(time.time() - handle_health._start_time)

    # Check if GAM credentials file exists
    creds_path = os.getenv("GAM_CREDENTIALS_PATH", "config/googleads.yaml")
    gam_creds_present = os.path.exists(creds_path)
    sa_path = os.path.join(os.path.dirname(creds_path), "service_account.json")
    sa_present = os.path.exists(sa_path)
    network_code = os.getenv("GAM_NETWORK_CODE", gam.network_code if gam else "")

    return JSONResponse(
        {
            "status": "ok",
            "service": "GAM 360 Live Reporting Platform",
            "uptime_seconds": uptime_s,
            "gam": {
                "credentials_file_present": gam_creds_present,
                "service_account_present": sa_present,
                "network_code": str(network_code) if network_code else None,
                "api_version": os.getenv("GAM_API_VERSION", "v202602"),
            },
            "bedrock": {
                "available": HAS_BEDROCK,
                "bearer_token_set": bool(os.getenv("AWS_BEARER_TOKEN_BEDROCK")),
                "access_key_set": bool(os.getenv("AWS_ACCESS_KEY_ID")),
                "region": os.getenv("AWS_REGION", "us-east-1"),
            },
            "email": {
                "gmail_sender_set": bool(os.getenv("GMAIL_SENDER_EMAIL")),
                "gmail_password_set": bool(os.getenv("GMAIL_APP_PASSWORD")),
            },
        },
        headers={"Access-Control-Allow-Origin": "*"},
    )



@asynccontextmanager
async def lifespan(app):
    task = asyncio.create_task(daily_report_loop())
    yield
    task.cancel()

starlette_app = Starlette(
    debug=True,
    routes=[
        Route("/health", endpoint=handle_health, methods=["GET"]),
        Route("/sse", endpoint=handle_sse),
        Route("/messages/", endpoint=handle_messages, methods=["POST"]),
        Route("/api/tool", endpoint=handle_api_tool, methods=["POST", "OPTIONS"]),
        Route("/api/chat", endpoint=handle_chat, methods=["POST", "OPTIONS"]),
        Route("/api/recipients", endpoint=handle_api_recipients, methods=["GET", "POST", "OPTIONS"]),
        Route("/api/recipients/{id}", endpoint=handle_api_recipients_delete, methods=["DELETE", "OPTIONS"]),
        Route("/api/test-email", endpoint=handle_api_test_email, methods=["POST", "OPTIONS"]),
    ],
    lifespan=lifespan,
    middleware=[
        Middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]),
    ],
)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(starlette_app, host="0.0.0.0", port=port)
