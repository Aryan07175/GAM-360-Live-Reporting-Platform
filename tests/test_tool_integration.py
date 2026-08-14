"""
tests/test_tool_integration.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Integration tests that exercise the ACTUAL tool functions end-to-end with
edge-case data (missing metrics, zero-division, NaN) — exactly the
conditions that trigger the production crash.

The prior 48 unit tests only tested the safe formatters in isolation;
these tests prove the real tool code paths no longer crash.

Run with:
    cd /path/to/GAM-360-Live-Reporting-Platform
    python -m pytest tests/test_tool_integration.py -v
"""

import os
import sys
from datetime import date

import numpy as np
import pandas as pd
import pytest

# Ensure mcp_server is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def df_with_missing_metrics():
    """
    A DataFrame simulating real GAM data where one app has zero ad_requests
    (programmatic-only), causing fill_rate to be NaN/None, and another has
    zero impressions, causing eCPM and CTR to be NaN/inf.
    This is the exact data shape that triggers the production crash for
    "Which app has the highest revenue?" because compute_revenue_by_app +
    generate_insights + generate_recommendations all format these values.
    """
    return pd.DataFrame([
        # Normal app — all metrics present
        {
            "ad_unit_name": "App A - Banner",
            "ad_unit_id": "1001",
            "ad_server_cpm_and_cpc_revenue": 500.0,
            "ad_server_impressions": 100000,
            "ad_server_clicks": 500,
            "ad_server_ad_requests": 120000,
            "canonical_ad_requests": 120000,
            "matched_requests": 100000,
            "date": "2026-08-01",
        },
        # Programmatic-only app — zero ad_requests → fill_rate = NaN
        {
            "ad_unit_name": "App B - Rewarded",
            "ad_unit_id": "1002",
            "ad_server_cpm_and_cpc_revenue": 200.0,
            "ad_server_impressions": 50000,
            "ad_server_clicks": 100,
            "ad_server_ad_requests": 0,
            "canonical_ad_requests": 0,
            "matched_requests": 0,
            "date": "2026-08-01",
        },
        # Zero-impressions app — eCPM and CTR will be 0 (division by zero)
        {
            "ad_unit_name": "App C - Interstitial",
            "ad_unit_id": "1003",
            "ad_server_cpm_and_cpc_revenue": 0.0,
            "ad_server_impressions": 0,
            "ad_server_clicks": 0,
            "ad_server_ad_requests": 5000,
            "canonical_ad_requests": 5000,
            "matched_requests": 0,
            "date": "2026-08-01",
        },
    ])


@pytest.fixture
def df_previous_period():
    """Previous period data for anomaly detection — one app drops revenue."""
    return pd.DataFrame([
        {
            "ad_unit_name": "App A - Banner",
            "ad_unit_id": "1001",
            "ad_server_cpm_and_cpc_revenue": 800.0,  # much higher → will trigger anomaly
            "ad_server_impressions": 120000,
            "ad_server_clicks": 600,
            "ad_server_ad_requests": 130000,
            "canonical_ad_requests": 130000,
            "matched_requests": 120000,
            "date": "2026-07-31",
        },
        {
            "ad_unit_name": "App B - Rewarded",
            "ad_unit_id": "1002",
            "ad_server_cpm_and_cpc_revenue": 200.0,
            "ad_server_impressions": 50000,
            "ad_server_clicks": 100,
            "ad_server_ad_requests": 0,
            "canonical_ad_requests": 0,
            "matched_requests": 0,
            "date": "2026-07-31",
        },
    ])


# ─── Test: compute_revenue_by_app ─────────────────────────────────────────────

class TestComputeRevenueByApp:
    def test_returns_sorted_apps_with_nan_fill_rate(self, df_with_missing_metrics):
        """The function that answers 'which app has the highest revenue?'"""
        from mcp_server.server import compute_revenue_by_app
        apps = compute_revenue_by_app(df_with_missing_metrics)

        assert len(apps) == 3
        # Sorted by revenue descending
        assert apps[0]["ad_unit_name"] == "App A - Banner"
        assert apps[0]["ad_server_cpm_and_cpc_revenue"] == 500.0

        # App B has zero ad_requests → fill_rate should be None (not crash)
        app_b = next(a for a in apps if a["ad_unit_name"] == "App B - Rewarded")
        # fill_rate is None because canonical_ad_requests == 0
        assert app_b["ad_server_fill_rate"] is None or app_b["ad_server_fill_rate"] == 0

        # App C has zero impressions → eCPM should be 0, not NaN/crash
        app_c = next(a for a in apps if a["ad_unit_name"] == "App C - Interstitial")
        assert app_c["ad_server_without_cpd_average_ecpm"] == 0


# ─── Test: generate_insights (the exact crash path) ──────────────────────────

class TestGenerateInsights:
    def test_does_not_crash_with_none_metrics(self, df_with_missing_metrics):
        """
        generate_insights reads summary.get('average_ecpm') and formats it
        with :.4f — crashes if the value is None or a string.
        """
        from mcp_server.server import (
            compute_executive_summary,
            compute_revenue_by_app,
            compute_revenue_trend,
            generate_insights,
        )
        summary = compute_executive_summary(
            df_with_missing_metrics, date(2026, 8, 1), date(2026, 8, 7)
        )
        apps = compute_revenue_by_app(df_with_missing_metrics)
        trend = compute_revenue_trend(df_with_missing_metrics)

        # This line crashed in production before the fix
        insights = generate_insights(summary, apps, trend)

        assert isinstance(insights, list)
        assert len(insights) >= 1
        # Verify all descriptions are strings (not crashed)
        for ins in insights:
            assert isinstance(ins["description"], str)

    def test_with_empty_summary(self):
        """Edge case: empty DataFrame produces a zeroed summary."""
        from mcp_server.server import generate_insights
        summary = {
            "total_revenue_usd": 0, "total_impressions": 0,
            "average_ecpm": 0, "average_fill_rate": 0,
            "app_count": 0,
        }
        # Should not crash even with all zeros
        insights = generate_insights(summary, [], [])
        assert isinstance(insights, list)


# ─── Test: generate_recommendations ──────────────────────────────────────────

class TestGenerateRecommendations:
    def test_does_not_crash_with_none_fill_rate(self, df_with_missing_metrics):
        """
        generate_recommendations formats summary.get('average_fill_rate')
        with :.1f — crashes if None.
        """
        from mcp_server.server import (
            compute_executive_summary,
            compute_revenue_by_app,
            generate_recommendations,
        )
        summary = compute_executive_summary(
            df_with_missing_metrics, date(2026, 8, 1), date(2026, 8, 7)
        )
        apps = compute_revenue_by_app(df_with_missing_metrics)

        recs = generate_recommendations(summary, apps, [])
        assert isinstance(recs, list)
        for rec in recs:
            assert isinstance(rec["description"], str)

    def test_with_none_fill_rate_in_summary(self):
        """
        Directly tests the exact crash: summary['average_fill_rate'] = None
        which reaches the :.1f format spec.
        """
        from mcp_server.server import generate_recommendations
        summary = {
            "total_revenue_usd": 100.0,
            "total_impressions": 50000,
            "average_ecpm": 2.0,
            "average_fill_rate": None,  # <-- THIS IS THE CRASH VALUE
            "app_count": 3,
        }
        apps = [
            {"ad_unit_name": "App A", "ad_server_cpm_and_cpc_revenue": 80.0,
             "ad_server_fill_rate": 50.0, "ad_server_ad_requests": 200,
             "ad_server_ctr": 1.0},
            {"ad_unit_name": "App B", "ad_server_cpm_and_cpc_revenue": 20.0,
             "ad_server_fill_rate": None, "ad_server_ad_requests": 0,
             "ad_server_ctr": 0.5},
        ]

        # Before fix: crashes with ValueError: Unknown format code 'f' for object of type 'NoneType'
        recs = generate_recommendations(summary, apps, [])
        assert isinstance(recs, list)


# ─── Test: compute_anomalies ─────────────────────────────────────────────────

class TestComputeAnomalies:
    def test_anomaly_descriptions_format_safely(self, df_with_missing_metrics, df_previous_period):
        """
        compute_anomalies formats ${prev:.4f} → ${curr:.4f} in description.
        These values come from Pandas .sum() which can be NaN if the app
        is missing from one period.
        """
        from mcp_server.server import compute_anomalies
        anomalies = compute_anomalies(df_with_missing_metrics, df_previous_period)

        assert isinstance(anomalies, list)
        for a in anomalies:
            assert isinstance(a["description"], str)
            # Verify no raw Python format artifacts leaked in
            assert ":.1f" not in a["description"]
            assert ":.4f" not in a["description"]


# ─── Test: compute_alerts ─────────────────────────────────────────────────────

class TestComputeAlerts:
    def test_alerts_with_edge_case_metrics(self, df_with_missing_metrics):
        """
        compute_alerts iterates per-app and formats fill_rate, ctr, ecpm.
        App C has 0 impressions → ctr = 0/0, ecpm = 0/0 (guarded by conditionals
        but the format spec needs to be safe too).
        """
        from mcp_server.server import compute_alerts
        alerts = compute_alerts(df_with_missing_metrics)

        assert isinstance(alerts, list)
        for alert in alerts:
            assert isinstance(alert["title"], str)
            assert isinstance(alert["value"], str)
