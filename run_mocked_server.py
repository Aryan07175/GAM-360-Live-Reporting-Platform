import asyncio
from unittest.mock import patch, MagicMock
import json
import os
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"
os.environ["AWS_REGION"] = "us-east-1"

import mcp_server.server as server_module
import mcp_server.services.bedrock_service as bedrock_service

async def mock_call_bedrock(payload):
    return {
        "output": {
            "message": {
                "content": [
                    {
                        "toolUse": {
                            "toolUseId": "tooluse_123",
                            "name": "query_gam_data",
                            "input": {
                                "metric": "revenue",
                                "dimension": "app",
                                "start_date": "2026-08-01",
                                "end_date": "2026-08-07"
                            }
                        }
                    }
                ]
            }
        }
    }

call_count = 0
def mock_call_bedrock_multi(payload):
    global call_count
    call_count += 1
    if call_count == 1:
        return {
            "output": {
                "message": {
                    "content": [
                        {
                            "toolUse": {
                                "toolUseId": "tooluse_123",
                                "name": "query_gam_data",
                                "input": {
                                    "metric": "revenue",
                                    "dimension": "app",
                                    "start_date": "2026-08-01",
                                    "end_date": "2026-08-07"
                                }
                            }
                        }
                    ]
                }
            }
        }
    else:
        return {
            "output": {
                "message": {
                    "content": [{"text": "Here is the data."}]
                }
            }
        }

bedrock_service._call_bedrock = mock_call_bedrock_multi

async def mock_get_live_data(*args, **kwargs):
    return server_module.pd.DataFrame([
        {"ad_unit_name": "app1", "ad_server_cpm_and_cpc_revenue": 100, "ad_server_impressions": 1000, "date": "2026-08-01", "canonical_ad_requests": 1500, "matched_requests": 1000, "ad_server_clicks": 10, "ad_server_ad_requests": 1000},
        {"ad_unit_name": "app2", "ad_server_cpm_and_cpc_revenue": 200, "ad_server_impressions": 2000, "date": "2026-08-01", "canonical_ad_requests": 2500, "matched_requests": 2000, "ad_server_clicks": 20, "ad_server_ad_requests": 2000},
        {"ad_unit_name": "unavailable", "ad_server_cpm_and_cpc_revenue": 0, "ad_server_impressions": 0, "date": "2026-08-01", "canonical_ad_requests": 0, "matched_requests": 0, "ad_server_clicks": 0, "ad_server_ad_requests": 0}
    ])
server_module.gam.get_live_data_multi_day = mock_get_live_data

async def test_chat():
    req = MagicMock()
    req.method = "POST"
    
    async def mock_json():
        return {"message": "Which app has the highest revenue?", "history": []}
        
    req.json = mock_json
    
    try:
        resp = await server_module.handle_chat(req)
        # resp is StreamingResponse or JSONResponse
        if hasattr(resp, "body_iterator"):
            async for chunk in resp.body_iterator:
                print(chunk)
        else:
            print("Response:", resp.body)
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_chat())
