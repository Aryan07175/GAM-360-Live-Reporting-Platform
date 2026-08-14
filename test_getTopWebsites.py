import asyncio, os
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"
os.environ["AWS_REGION"] = "us-east-1"

import mcp_server.server as server_module
import pandas as pd
import numpy as np

async def mock_get_live_data(*args, **kwargs):
    return pd.DataFrame([
        {"ad_unit_name": "App1", "ad_unit_id": "1001", "ad_server_cpm_and_cpc_revenue": 300.5, "ad_server_impressions": 10000, "date": "2026-08-01", "canonical_ad_requests": 15000, "matched_requests": 10000, "ad_server_clicks": 100, "ad_server_ad_requests": 15000},
        {"ad_unit_name": "App2", "ad_unit_id": "1002", "ad_server_cpm_and_cpc_revenue": 200.0, "ad_server_impressions": 8000, "date": "2026-08-01", "canonical_ad_requests": 12000, "matched_requests": 8000, "ad_server_clicks": 80, "ad_server_ad_requests": 12000},
    ])
server_module.gam.get_live_data_multi_day = mock_get_live_data

async def test():
    input_dict = {
        "metric": "revenue",
        "dimension": "app",
        "start_date": "2026-08-01",
        "end_date": "2026-08-07"
    }
    try:
        result = await server_module.execute_query_gam_data(input_dict)
        print("OK:", list(result.keys()))
        import json
        print("rows:", json.dumps(result.get("rows", []), indent=2))
    except Exception as e:
        import traceback
        traceback.print_exc()

asyncio.run(test())
