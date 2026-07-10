"""
GAM 360 MCP Server — Live Reporting Engine

Every tool fetches LIVE data from Google Ad Manager.
No database. No cache. No ETL. No stored reports.

18+ tools covering: Executive Summary, Revenue, Trends, Applications,
Websites, Impressions, Clicks, CTR, eCPM, Fill Rate, Ad Requests,
Performance Ranking, Anomalies, Recommendations, and Full Report.
"""

import json
import logging
from datetime import date, timedelta, datetime

from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("mcp_server")

app = Server("gam360-live-reporting")
sse = SseServerTransport("/messages/")

gam = GAMClient()


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
    ],
    middleware=[
        Middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]),
    ],
)

if __name__ == "__main__":
    uvicorn.run(starlette_app, host="0.0.0.0", port=8000)
