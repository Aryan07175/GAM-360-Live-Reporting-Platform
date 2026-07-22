import asyncio
import os
import sys
from datetime import date, timedelta
from mcp_server.gam_client import GAMClient

async def main():
    os.environ["GAM_CREDENTIALS_PATH"] = "/Users/aryan/Desktop/GAM-360-Live-Reporting-Platform/GAM-360-Live-Reporting-Platform/mcp_server/config/googleads.yaml"
    client = GAMClient()
    start = date(2026, 7, 21)
    end = date(2026, 7, 21)
    try:
        df = await client.get_live_data(start, end, force_refresh=True)
        print("Success! Got", len(df), "rows")
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    asyncio.run(main())
