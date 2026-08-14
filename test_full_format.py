"""
Reproduce the exact production error:
  Invalid format specifier '"unavailable"' for object of type 'str'

Strategy: run all f-strings in server.py and email_service.py that have numeric format specifiers
and pass them "unavailable" as a value.
"""
import asyncio, os
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"

import mcp_server.server as server_module
import mcp_server.email_service as email_module
import pandas as pd
import numpy as np

# Simulate real "unavailable" appearing in fill_rate or other computed fields
# by constructing a DataFrame where `ad_server_fill_rate` is None (not numeric)
df = pd.DataFrame([
    {"ad_unit_name": "App1", "ad_unit_id": "1001", "ad_server_cpm_and_cpc_revenue": 300.5, 
     "ad_server_impressions": 10000, "date": "2026-08-01", 
     "canonical_ad_requests": 15000, "matched_requests": 10000, 
     "ad_server_clicks": 100, "ad_server_ad_requests": 15000},
])

# Test compute_alerts
try:
    alerts = server_module.compute_alerts(df)
    print("compute_alerts OK:", alerts[:2])
except Exception as e:
    print("compute_alerts FAILED:", repr(e))
    import traceback; traceback.print_exc()

# Test generate_recommendations
try:
    summary = server_module.compute_executive_summary(df, __import__('datetime').date(2026,8,1), __import__('datetime').date(2026,8,7))
    apps = server_module.compute_revenue_by_app(df)
    recs = server_module.generate_recommendations(summary, apps, [])
    print("generate_recommendations OK:", len(recs), "recs")
except Exception as e:
    print("generate_recommendations FAILED:", repr(e))
    import traceback; traceback.print_exc()

# Test generate_insights
try:
    insights = server_module.generate_insights(summary, apps, [])
    print("generate_insights OK:", len(insights), "insights")
except Exception as e:
    print("generate_insights FAILED:", repr(e))
    import traceback; traceback.print_exc()

# Test email with "unavailable" fill_rate values (simulate NaN/None)
apps_for_email = [
    {
        "ad_unit_name": "App1",
        "ad_server_cpm_and_cpc_revenue": 300.5,
        "ad_server_impressions": 10000,
        "ad_server_fill_rate": None,  # <- None / unavailable
        "ad_server_without_cpd_average_ecpm": 30.05,
        "ad_server_ctr": 1.0,
    }
]
try:
    # Call email report generation
    email_module.send_executive_report(
        apps=apps_for_email,
        summary={"total_revenue_usd": 300.5, "total_impressions": 10000, "average_ecpm": 30.05, 
                 "average_fill_rate": None, "period": "2026-08-01 to 2026-08-07"},
        anomalies=[],
        recommendations=[],
        period="2026-08-01 to 2026-08-07",
        to_emails=["test@test.com"]
    )
    print("email OK")
except Exception as e:
    print("email FAILED:", repr(e))
    import traceback; traceback.print_exc()
