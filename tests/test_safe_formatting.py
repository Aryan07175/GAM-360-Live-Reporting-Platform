"""
tests/test_safe_formatting.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Regression tests for mcp_server.utils safe formatting helpers.

These tests specifically guard against the class of bugs that produced:
    Invalid format specifier '"unavailable"' for object of type 'str'

Run with:
    cd /path/to/GAM-360-Live-Reporting-Platform
    python -m pytest tests/test_safe_formatting.py -v
"""

import math

import pytest

from mcp_server.utils import (
    coerce_numeric,
    fmt_currency,
    fmt_number,
    fmt_percent,
    safe_float,
)


# ─── safe_float ───────────────────────────────────────────────────────────────

class TestSafeFloat:
    def test_none_returns_none(self):
        assert safe_float(None) is None

    def test_nan_returns_none(self):
        assert safe_float(float("nan")) is None

    def test_int_converted(self):
        assert safe_float(42) == 42.0

    def test_float_passthrough(self):
        assert safe_float(3.14) == 3.14

    def test_string_unavailable(self):
        assert safe_float("unavailable") is None

    def test_string_with_quotes(self):
        # This is the exact value that triggered the production crash
        assert safe_float('"unavailable"') is None

    def test_string_n_a(self):
        assert safe_float("N/A") is None

    def test_empty_string(self):
        assert safe_float("") is None

    def test_numeric_string(self):
        assert safe_float("1234.5") == 1234.5

    def test_currency_string(self):
        assert safe_float("$1,234.50") == 1234.5

    def test_percent_string(self):
        assert safe_float("12.5%") == 12.5

    def test_comma_separated_string(self):
        assert safe_float("1,000,000") == 1_000_000.0

    def test_zero(self):
        assert safe_float(0) == 0.0

    def test_negative(self):
        assert safe_float(-5.5) == -5.5

    def test_unexpected_type_returns_none(self):
        assert safe_float([1, 2]) is None
        assert safe_float({"a": 1}) is None


# ─── fmt_currency ─────────────────────────────────────────────────────────────

class TestFmtCurrency:
    def test_normal_number(self):
        assert fmt_currency(1234.5) == "$1,234.50"

    def test_none(self):
        assert fmt_currency(None) == "Unavailable"

    def test_string_unavailable(self):
        # This EXACT value was causing the production crash
        assert fmt_currency("unavailable") == "Unavailable"

    def test_quoted_unavailable(self):
        assert fmt_currency('"unavailable"') == "Unavailable"

    def test_zero(self):
        assert fmt_currency(0) == "$0.00"

    def test_negative(self):
        assert fmt_currency(-100.0) == "$-100.00"

    def test_custom_missing(self):
        assert fmt_currency(None, missing="N/A") == "N/A"

    def test_custom_decimals(self):
        assert fmt_currency(1.5, decimals=4) == "$1.5000"

    def test_nan(self):
        assert fmt_currency(float("nan")) == "Unavailable"

    def test_large_number(self):
        assert fmt_currency(1_000_000.0) == "$1,000,000.00"


# ─── fmt_number ───────────────────────────────────────────────────────────────

class TestFmtNumber:
    def test_integer(self):
        assert fmt_number(1234567) == "1,234,567"

    def test_float_no_decimals(self):
        assert fmt_number(1234.9) == "1,235"  # rounds

    def test_float_with_decimals(self):
        assert fmt_number(1234.5, decimals=1) == "1,234.5"

    def test_none(self):
        assert fmt_number(None) == "Unavailable"

    def test_string_unavailable(self):
        assert fmt_number("unavailable") == "Unavailable"

    def test_zero(self):
        assert fmt_number(0) == "0"

    def test_nan(self):
        assert fmt_number(float("nan")) == "Unavailable"


# ─── fmt_percent ──────────────────────────────────────────────────────────────

class TestFmtPercent:
    def test_normal(self):
        assert fmt_percent(12.345) == "12.35%"

    def test_none(self):
        assert fmt_percent(None) == "Unavailable"

    def test_string_unavailable(self):
        assert fmt_percent("unavailable") == "Unavailable"

    def test_zero(self):
        assert fmt_percent(0) == "0.00%"

    def test_custom_decimals(self):
        assert fmt_percent(12.345, decimals=1) == "12.3%"  # note: rounds to 12.3 not 12.4

    def test_nan(self):
        assert fmt_percent(float("nan")) == "Unavailable"


# ─── coerce_numeric ───────────────────────────────────────────────────────────

class TestCoerceNumeric:
    def test_none_returns_default(self):
        assert coerce_numeric(None) == 0.0

    def test_string_unavailable_returns_default(self):
        assert coerce_numeric("unavailable") == 0.0

    def test_custom_default(self):
        assert coerce_numeric(None, default=-1.0) == -1.0

    def test_real_number_returned(self):
        assert coerce_numeric(42.5) == 42.5

    def test_numeric_string(self):
        assert coerce_numeric("100.5") == 100.5

    def test_zero_is_preserved(self):
        assert coerce_numeric(0) == 0.0


# ─── Crash reproduction: the exact production scenario ────────────────────────

class TestProductionCrashRepro:
    """
    Reproduce the exact conditions that caused:
        Invalid format specifier '"unavailable"' for object of type 'str'
    and confirm the safe helpers prevent it.
    """

    def test_email_service_app_revenue_pattern(self):
        """email_service.py L220: was ${a_rev:,.2f} where a_rev could be None."""
        a_rev = None  # as returned when GAM app dict has no revenue field
        # OLD pattern — would crash:
        # result = f"${a_rev:,.2f}"  # TypeError: unsupported format character
        # NEW pattern — safe:
        result = fmt_currency(a_rev)
        assert result == "Unavailable"

    def test_email_service_summary_fill_rate_pattern(self):
        """email_service.py L293: was {fill:,.1f}% where fill could be None."""
        fill = None  # as returned when average_fill_rate is None in summary dict
        result = fmt_percent(fill, decimals=1)
        assert result == "Unavailable"

    def test_anomaly_decomposition_nan_delta(self):
        """
        gam_client.py L4980: total_delta can be NaN if derived from NaN-containing
        Pandas values (e.g., total_current - total_prior where one side is NaN).
        safe_float(NaN) → None, preventing abs(NaN):,.2f from crashing.
        Also tests the None-total_delta_pct scenario (prior == 0 branch).
        """
        import math

        # NaN passed directly (e.g., result of NaN - NaN arithmetic in Pandas)
        nan_val = float("nan")
        safe = safe_float(nan_val)
        assert safe is None, f"Expected None for NaN, got {safe}"

        # None scenario: total_delta_pct = None when prior == 0
        total_delta_pct = None
        safe_pct = safe_float(total_delta_pct)
        assert safe_pct is None

        # Verify the narrative builder pattern works end-to-end
        _total_delta = safe_float(nan_val) or 0.0
        assert _total_delta == 0.0  # graceful fallback, no crash

    def test_network_analytics_ecpm_format(self):
        """network_analytics.py L682: was f"${ecpm:.2f}" in insight builder."""
        # Even with float() coercion, a string can slip through from a different
        # code path; fmt_currency handles all cases.
        ecpm_values = [0.0, None, "unavailable", 1.5, float("nan")]
        for v in ecpm_values:
            # Should never raise
            result = fmt_currency(v)
            assert isinstance(result, str)
