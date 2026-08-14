import sys
import json
import asyncio
from unittest.mock import AsyncMock, MagicMock
import mcp_server.server as server_module
import pandas as pd
import builtins
import traceback

original_format = builtins.format
def catching_format(value, format_spec=""):
    if "unavailable" in str(format_spec):
        print(f"CAUGHT format_spec: {format_spec}")
        traceback.print_stack()
    return original_format(value, format_spec)
builtins.format = catching_format

async def run_test():
    server_module.gam = MagicMock()
    df = pd.DataFrame([{
        "ad_unit_name": "App1", "ad_unit_id": "1001",
        "ad_server_cpm_and_cpc_revenue": 300.5,
        "ad_server_impressions": 10000, "date": "2026-08-01",
        "canonical_ad_requests": 15000, "matched_requests": 10000,
        "ad_server_clicks": 100, "ad_server_ad_requests": 15000
    }])
    # Set matched_requests and canonical_ad_requests to 0 to trigger NaN fill_rate
    df.loc[0, "canonical_ad_requests"] = 0
    df.loc[0, "ad_server_ad_requests"] = 0
    
    server_module.gam.get_live_data_multi_day = AsyncMock(return_value=df)

    executor = server_module._make_tool_executor(None)
    input_dict = {"limit": 10}
    try:
        # tool_name gets routed to query_gam_data internally if we use getTopApplications directly?
        # NO, getTopApplications is NOT in _make_tool_executor's list of explicitly handled tools!
        # wait, let me just call execute_query_gam_data directly!
        res = await server_module.execute_query_gam_data({"tool_name": "getTopApplications", "limit": 10})
        
        # bedrock_service.py does:
        safe_result = json.loads(json.dumps(res, default=str))
        print("SAFE RESULT:", safe_result)
        
    except Exception as e:
        print("EXCEPTION:", repr(e))

asyncio.run(run_test())
