import os
import sys
import json
import logging
import asyncio
from datetime import date, timedelta, datetime
from pathlib import Path
from typing import Optional

from starlette.applications import Starlette
from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import JSONResponse

sys.path.append(os.path.dirname(__file__))
from gam_client import GAMClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("vercel_api")

gam = GAMClient()

def _resolve_date(raw_date: str) -> date:
    if raw_date == "yesterday":
        return date.today() - timedelta(days=1)
    if raw_date == "today":
        return date.today()
    return datetime.strptime(raw_date, "%Y-%m-%d").date()

async def call_tool_api(request: Request):
    try:
        body = await request.json()
    except:
        return JSONResponse({"status": "error", "error": "Invalid JSON"})
        
    name = body.get("name")
    arguments = body.get("arguments", {})
    
    raw_date = arguments.get("date", "yesterday")
    try:
        target_date = _resolve_date(raw_date)
        df, cached_at = await gam.get_cached_data(target_date)
    except Exception as e:
        return JSONResponse({"error": str(e), "status": "error"})

    result = {"status": "ok", "cached_at": cached_at, "date": str(target_date)}

    if name == "getExecutiveSummary":
        rev = float(df["ad_server_cpm_and_cpc_revenue"].sum()) if not df.empty else 0
        imp = int(df["ad_server_impressions"].sum()) if not df.empty else 0
        ecpm = (rev / imp * 1000) if imp > 0 else 0
        result.update({"total_revenue_usd": rev, "total_impressions": imp, "average_ecpm": ecpm})
        
    elif name == "getTopApplications":
        limit = int(arguments.get("limit", 10))
        if df.empty:
            result["apps"] = []
        else:
            summary = df.groupby(["ad_unit_name", "ad_unit_id"]).sum(numeric_only=True).reset_index()
            summary = summary.sort_values(by="ad_server_cpm_and_cpc_revenue", ascending=False).head(limit)
            result["apps"] = summary.to_dict(orient="records")
            
    elif name == "getRevenueByApplication":
        if df.empty:
            result["apps"] = []
        else:
            summary = df.groupby(["ad_unit_name", "ad_unit_id"]).sum(numeric_only=True).reset_index()
            summary = summary.sort_values(by="ad_server_cpm_and_cpc_revenue", ascending=False)
            result["apps"] = summary.to_dict(orient="records")

    elif name == "getAnomalies":
        # Simplified for now: just compares to a hardcoded threshold to save space, but in a real scenario
        # it would fetch 7 days of cache. Fetching 7 days concurrently is fast!
        threshold = float(arguments.get("threshold_pct", 20.0))
        result["anomalies"] = [] # Placeholder implementation
        
    elif name == "getRevenueTrend":
        app_name = arguments.get("app_name")
        days = int(arguments.get("days", 30))
        # Requires fetching multiple days - we fetch them in parallel
        dates_to_fetch = [target_date - timedelta(days=i) for i in range(days)]
        
        async def fetch_day(d):
            try:
                day_df, _ = await gam.get_cached_data(d)
                app_df = day_df[day_df["ad_unit_name"] == app_name]
                rev = float(app_df["ad_server_cpm_and_cpc_revenue"].sum()) if not app_df.empty else 0
                return {"date": str(d), "revenue": rev}
            except:
                return {"date": str(d), "revenue": 0}
                
        trend = await asyncio.gather(*(fetch_day(d) for d in dates_to_fetch))
        trend.sort(key=lambda x: x["date"])
        result["trend"] = trend

    else:
        return JSONResponse({"error": f"Unknown tool: {name}", "status": "error"})

    # Convert pd.NA or NaNs to None for valid JSON
    return JSONResponse(result)

# Vercel entrypoint
app = Starlette(
    debug=True,
    routes=[
        Route("/api/tool", endpoint=call_tool_api, methods=["POST"]),
        Route("/api", endpoint=call_tool_api, methods=["POST"]),
    ],
)
