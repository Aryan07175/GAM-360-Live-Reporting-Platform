import sys
import json
import asyncio
from datetime import date
from unittest.mock import AsyncMock, MagicMock

# Patch str formatting to catch the exact error
import builtins
original_format = builtins.format
def catching_format(value, format_spec=""):
    if "unavailable" in str(format_spec):
        import traceback
        print(f"CAUGHT format_spec: {format_spec}")
        traceback.print_stack()
    return original_format(value, format_spec)
builtins.format = catching_format

# Start the server and simulate the chat request
import mcp_server.server as server_module

async def run_test():
    # Mock the GAM client
    server_module.gam = MagicMock()
    server_module.gam.get_live_data_multi_day = AsyncMock(return_value=server_module.pd.DataFrame())

    # Mock the tool executor
    executor = server_module._make_tool_executor(None)
    
    # Simulate a query that returns unavailable
    input_dict = {
        "start_date": "2026-08-01",
        "end_date": "2026-08-07",
        "dimension": "app",
        "metric": "revenue"
    }
    
    # Try query_gam_data directly
    try:
        res = await executor("query_gam_data", input_dict)
        print("query_gam_data result keys:", res.keys() if isinstance(res, dict) else type(res))
    except Exception as e:
        print("Error in query_gam_data:", e)

    # Try getAudienceGeography
    input_dict2 = {
        "start_date": "2026-08-01",
        "end_date": "2026-08-07",
    }
    server_module.gam.get_audience_geography = MagicMock(return_value=[
        {"_live_data_status": "unavailable", "_message": "Test"}
    ])
    try:
        res2 = await executor("getAudienceGeography", input_dict2)
        print("getAudienceGeography result:", str(res2)[:100])
    except Exception as e:
        print("Error in getAudienceGeography:", type(e).__name__, e)

asyncio.run(run_test())
