"""
mcp_server/utils.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Safe metric formatting utilities for the GAM 360 Live Reporting Platform.

These helpers prevent the `Invalid format specifier '"unavailable"' for
object of type 'str'` crash that occurs when a metric value is None, the
string "unavailable", or any other non-numeric sentinel that leaks into an
f-string with a numeric format spec (e.g., `:.2f`, `:,`).

Design contract
───────────────
• All raw numeric fields (revenue, impressions, ecpm, ctr, fill_rate, …)
  MUST stay numeric-or-None throughout the data pipeline (Pandas DataFrames,
  GAM API dicts, tool-result dicts).
• Only convert to a human-readable string AT THE FINAL DISPLAY LAYER using
  the functions in this module.
• Never store a string like "unavailable" in a numeric column — that
  conflates type and presentation.

Usage
─────
    from mcp_server.utils import fmt_currency, fmt_number, fmt_percent

    # Before (crashes if revenue == "unavailable" or None):
    summary["revenue"] = f"${revenue:,.2f}"

    # After (never crashes):
    summary["revenue"] = fmt_currency(revenue)
"""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger("mcp_server.utils")

# ─── Internal coercion ────────────────────────────────────────────────────────

_MISSING_STRINGS = frozenset({
    "unavailable", "n/a", "na", "none", "null", "", "-", "--",
    "not available", "not applicable",
})


def safe_float(value: Any) -> float | None:
    """
    Coerce *value* to float, returning None if it is missing or invalid.

    Handles:
        • None / NaN (numpy or Python)
        • int / float  →  returned as float
        • str          →  stripped, currency/percent chars removed, then parsed
        • anything else → None (with a DEBUG log)
    """
    if value is None:
        return None

    # numpy NaN check (avoids importing numpy at module level)
    try:
        import math
        if isinstance(value, float) and math.isnan(value):
            return None
    except (TypeError, ValueError):
        pass

    if isinstance(value, (int, float)):
        try:
            f = float(value)
            import math
            return None if math.isnan(f) else f
        except (ValueError, OverflowError):
            return None

    if isinstance(value, str):
        cleaned = (
            value.strip()
            .replace(",", "")
            .replace("$", "")
            .replace("%", "")
            .replace(" ", "")
        )
        if cleaned.lower() in _MISSING_STRINGS:
            return None
        try:
            return float(cleaned)
        except ValueError:
            log.debug("safe_float: could not parse %r", value)
            return None

    log.debug("safe_float: unexpected type %s for value %r", type(value).__name__, value)
    return None


# ─── Public formatting helpers ────────────────────────────────────────────────

def fmt_currency(value: Any, decimals: int = 2, missing: str = "Unavailable") -> str:
    """
    Format *value* as a USD currency string.

    Examples
    --------
    >>> fmt_currency(1234.5)
    '$1,234.50'
    >>> fmt_currency("unavailable")
    'Unavailable'
    >>> fmt_currency(None)
    'Unavailable'
    """
    n = safe_float(value)
    if n is None:
        return missing
    return f"${n:,.{decimals}f}"


def fmt_number(value: Any, decimals: int = 0, missing: str = "Unavailable") -> str:
    """
    Format *value* as a comma-separated number.

    Examples
    --------
    >>> fmt_number(1234567)
    '1,234,567'
    >>> fmt_number(1234.5, decimals=1)
    '1,234.5'
    >>> fmt_number(None)
    'Unavailable'
    """
    n = safe_float(value)
    if n is None:
        return missing
    return f"{n:,.{decimals}f}"


def fmt_percent(value: Any, decimals: int = 2, missing: str = "Unavailable") -> str:
    """
    Format *value* as a percentage string.

    Examples
    --------
    >>> fmt_percent(12.345)
    '12.35%'
    >>> fmt_percent("unavailable")
    'Unavailable'
    """
    n = safe_float(value)
    if n is None:
        return missing
    return f"{n:.{decimals}f}%"


def coerce_numeric(value: Any, default: float = 0.0) -> float:
    """
    Return *value* as float, falling back to *default* (never None).
    Useful for arithmetic (sorting, thresholds) where None would crash.

    Examples
    --------
    >>> coerce_numeric("unavailable")
    0.0
    >>> coerce_numeric(None, default=0.0)
    0.0
    >>> coerce_numeric(42.5)
    42.5
    """
    n = safe_float(value)
    return n if n is not None else default
