"""
mcp_server/services/query_engine.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Query Engine — Analytics-First Backend Layer

DESIGN PRINCIPLE
─────────────────
The LLM (Bedrock/Claude) must NEVER receive raw GAM datasets.
All analytics (max, min, ranking, aggregation, percentage, comparison)
are executed HERE in Python before the result reaches the LLM.

The LLM's sole job: generate a natural-language explanation of the
pre-computed, pre-summarized result payload.

TOKEN BUDGET
─────────────
Claude Haiku 4.5 context window: 200,000 tokens
System prompt budget:    ~15,000 tokens  (compressed)
Chat history budget:     ~5,000  tokens  (last 8 turns)
Tool result budget:      ~10,000 tokens  (this module enforces this)
Safety headroom:         ~20,000 tokens
───────────────────────────────────────
Hard limit per result:   10,000 tokens  (~40,000 chars)
Warn threshold:          8,000  tokens  (~32,000 chars)
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

log = logging.getLogger("query_engine")

# ─── Token Budget Constants ───────────────────────────────────────────────────

CHARS_PER_TOKEN       = 4       # conservative estimate for JSON/text
MAX_RESULT_TOKENS     = 10_000  # hard limit per tool result payload
WARN_RESULT_TOKENS    = 8_000   # warn at 80% of budget
MAX_ROWS_DEFAULT      = 15      # never send more than 15 rows to the LLM
MAX_ROWS_TOP_N        = 10      # for top/bottom N queries
MAX_ROWS_COMPARISON   = 8       # for compare queries
MAX_SYSTEM_PROMPT_CHARS = 20_000  # compress system prompt if it exceeds this

# ─── Metric → Relevant Columns Map ───────────────────────────────────────────
# For each requested metric, only these columns matter.
# All other columns are stripped from rows before sending to the LLM.

_METRIC_COLUMNS: dict[str, list[str]] = {
    "revenue": [
        "name", "revenue", "revenue_usd",
        "ad_server_cpm_and_cpc_revenue",
        "impressions", "ad_server_impressions",
        "fill_rate", "fill_rate_pct",
        "ecpm_usd", "ecpm",
    ],
    "impressions": [
        "name", "impressions", "ad_server_impressions",
        "revenue", "ad_server_cpm_and_cpc_revenue",
        "ad_requests", "ad_server_ad_requests",
        "fill_rate_pct",
    ],
    "clicks": [
        "name", "clicks", "ad_server_clicks",
        "ctr_pct", "impressions", "ad_server_impressions",
    ],
    "ad_requests": [
        "name", "ad_requests", "ad_server_ad_requests",
        "total_ad_requests", "canonical_ad_requests",
        "impressions", "ad_server_impressions",
        "fill_rate_pct",
    ],
    "total_ad_requests": [
        "name", "ad_requests", "total_ad_requests", "canonical_ad_requests",
        "impressions", "ad_server_impressions", "fill_rate_pct",
    ],
    "fill_rate": [
        "name", "fill_rate_pct", "fill_rate",
        "impressions", "ad_server_impressions",
        "ad_requests", "ad_server_ad_requests",
    ],
    "total_fill_rate": [
        "name", "fill_rate_pct", "total_fill_rate",
        "total_responses_served", "total_ad_requests",
    ],
    "ecpm": [
        "name", "ecpm_usd", "ecpm",
        "revenue", "ad_server_cpm_and_cpc_revenue",
        "impressions", "ad_server_impressions",
    ],
    "ctr": [
        "name", "ctr_pct", "ctr",
        "clicks", "ad_server_clicks",
        "impressions", "ad_server_impressions",
    ],
    "match_rate": [
        "name", "adx_match_rate_pct", "adx_match_rate",
        "adx_impressions", "ad_requests",
    ],
    "adx_impressions": [
        "name", "adx_impressions",
        "revenue", "ecpm_usd",
    ],
    "adx_revenue": [
        "name", "adx_revenue", "adx_revenue_usd",
        "adx_impressions", "adx_ecpm_usd",
    ],
    "adsense_revenue": [
        "name", "adsense_revenue", "adsense_revenue_usd",
        "adsense_impressions", "adsense_ecpm_usd",
    ],
    "adsense_impressions": [
        "name", "adsense_impressions",
        "adsense_revenue", "adsense_ctr_pct",
    ],
    "total_responses_served": [
        "name", "total_responses_served", "matched_requests",
        "ad_requests", "fill_rate_pct",
    ],
}

# Columns that must NEVER be sent to the LLM (raw GAM internals, IDs, etc.)
_STRIP_ALWAYS = {
    "ad_unit_id", "child_network_code", "date",
    "programmatic_match_rate",
    "total_line_item_level_cpm_and_cpc_revenue",
    "total_line_item_level_impressions",
    "total_line_item_level_clicks",
    "total_line_item_level_targeted_impressions",
    "total_line_item_level_targeted_clicks",
    "total_line_item_level_ctr",
    "total_line_item_level_without_cpd_average_ecpm",
    "total_line_item_level_with_cpd_average_ecpm",
    "total_inventory_level_unfilled_impressions",
    "adsense_line_item_level_impressions",
    "adsense_line_item_level_clicks",
    "adsense_line_item_level_revenue",
    "adsense_line_item_level_ctr",
    "adsense_line_item_level_average_ecpm",
    "ad_exchange_line_item_level_impressions",
    "ad_exchange_line_item_level_clicks",
    "ad_exchange_line_item_level_revenue",
    "ad_exchange_line_item_level_ctr",
    "ad_exchange_line_item_level_average_ecpm",
    "ad_server_begin_to_render_impressions",
    "dropoff_rate",
    "total_active_view_eligible_impressions",
    "total_active_view_measurable_impressions",
    "total_active_view_viewable_impressions",
    "total_active_view_measurable_impressions_rate",
    "total_active_view_viewable_impressions_rate",
    "total_active_view_average_viewable_time",
    "total_active_view_revenue",
    "programmatic_responses_served",
    "canonical_ad_requests",
    "matched_requests",
    "adx_match_rate",
    "total_code_served_count",
    "total_unmatched_ad_requests",
}


# ─── Token Estimation ─────────────────────────────────────────────────────────

def estimate_tokens(payload: Any) -> int:
    """Estimate the token count of a Python object when serialized to JSON."""
    try:
        chars = len(json.dumps(payload, default=str))
    except Exception:
        chars = len(str(payload))
    return chars // CHARS_PER_TOKEN


def estimate_tokens_str(text: str) -> int:
    """Estimate token count for a plain string."""
    return len(text) // CHARS_PER_TOKEN


# ─── Row Slimming ─────────────────────────────────────────────────────────────

def slim_rows(rows: list[dict], metric: str, *, max_rows: int = MAX_ROWS_DEFAULT) -> list[dict]:
    """
    Strip each row down to only the columns needed to answer a question
    about the requested metric. Also applies the strip-always list.

    Returns at most `max_rows` rows (sorted order from caller).

    Before: 50 rows x 40+ columns -> ~80,000 chars
    After:  15 rows x 5-6 columns -> ~3,000 chars
    """
    rows = rows[:max_rows]
    relevant = set(_METRIC_COLUMNS.get(metric, []))
    relevant.update(["name", "website", "app_name", "placement"])

    slimmed = []
    for row in rows:
        slim: dict = {}
        for k, v in row.items():
            if k in _STRIP_ALWAYS:
                continue
            if relevant and k not in relevant:
                if k not in ("ecpm_usd", "ctr_pct", "fill_rate_pct",
                             "adx_match_rate_pct", "matched_requests"):
                    continue
            # Drop zero numeric values to save tokens
            if k != "name" and v == 0 and isinstance(v, (int, float)):
                continue
            slim[k] = v
        if slim:
            slimmed.append(slim)
    return slimmed


def slim_website_rows(rows: list[dict], metric: str = "revenue",
                      *, max_rows: int = MAX_ROWS_DEFAULT) -> list[dict]:
    """Slim website-specific rows. Always keeps: name, status, + metric fields."""
    WEBSITE_KEEP = {"name", "domain", "status"}
    METRIC_EXTRAS = {
        "revenue":    {"revenue", "impressions", "fill_rate", "ecpm", "ctr"},
        "impressions":{"impressions", "revenue", "ad_requests", "fill_rate"},
        "fill_rate":  {"fill_rate", "ad_requests", "impressions"},
        "ecpm":       {"ecpm", "revenue", "impressions"},
        "ctr":        {"ctr", "clicks", "impressions"},
        "ad_requests":{"ad_requests", "matched_requests", "fill_rate"},
        "clicks":     {"clicks", "ctr", "impressions"},
    }
    keep = WEBSITE_KEEP | METRIC_EXTRAS.get(metric, {"revenue", "impressions", "fill_rate", "ecpm"})
    slimmed = []
    for row in rows[:max_rows]:
        slim = {k: v for k, v in row.items()
                if k in keep and not (k != "name" and v == 0 and isinstance(v, (int, float)))}
        if slim:
            slimmed.append(slim)
    return slimmed


# ─── Payload Size Guard ───────────────────────────────────────────────────────

def guard_payload_size(result: dict, metric: str = "revenue") -> dict:
    """
    Ensure the tool result payload doesn't exceed MAX_RESULT_TOKENS.
    If it does, progressively trim rows until it fits.
    """
    tokens = estimate_tokens(result)
    if tokens <= WARN_RESULT_TOKENS:
        log.info("[QueryEngine] Payload OK — %d tokens (%d rows)",
                 tokens, len(result.get("rows", [])))
        return result

    if tokens > MAX_RESULT_TOKENS:
        rows = result.get("rows", [])
        original_count = len(rows)
        while rows and estimate_tokens(result) > MAX_RESULT_TOKENS:
            rows = rows[:max(1, len(rows) // 2)]
            result = {**result, "rows": rows}
        log.warning(
            "[QueryEngine] Payload trimmed %d -> %d rows (%d tokens). metric=%s",
            original_count, len(rows), estimate_tokens(result), metric
        )
        result["_trimmed"] = True
    else:
        log.warning(
            "[QueryEngine] Payload at %d tokens (>80%% of budget). metric=%s",
            tokens, metric
        )
    return result


# ─── System Prompt Guard ──────────────────────────────────────────────────────

def compress_system_prompt(prompt: str) -> str:
    """
    If the system prompt exceeds the character budget, strip the verbose
    Website Intelligence Engine freeform-list sections. These are repeated
    question examples — not critical instructions.
    """
    if len(prompt) <= MAX_SYSTEM_PROMPT_CHARS:
        return prompt

    stripped = re.sub(
        r'={10,}\n(?:WEBSITE RANKING ENGINE|NATURAL LANGUAGE SUPPORT|'
        r'WEBSITE INVENTORY|SORTING|FILTERING|COMPARISON MODE|'
        r'SUPPORTED METRICS|REPORT GENERATION|LOW PERFORMANCE DETECTION|'
        r'WEBSITE HEALTH ANALYZER|WEBSITE ALERT ENGINE|QUICK RESPONSE MODE|'
        r'EXECUTIVE MODE|FINAL RULE)\n={10,}\n.*?(?=={10,}|\Z)',
        '',
        prompt,
        flags=re.DOTALL
    )

    log.info(
        "[QueryEngine] System prompt compressed: %d -> %d chars (%d tokens saved)",
        len(prompt), len(stripped), (len(prompt) - len(stripped)) // CHARS_PER_TOKEN
    )
    return stripped


# ─── Analytics Helpers ────────────────────────────────────────────────────────

def get_highest(rows: list[dict], metric_col: str) -> dict | None:
    """Return the single row with the highest value for metric_col."""
    valid = [r for r in rows if isinstance(r.get(metric_col), (int, float))]
    return max(valid, key=lambda r: r[metric_col]) if valid else None


def get_lowest(rows: list[dict], metric_col: str) -> dict | None:
    """Return the single row with the lowest non-zero value for metric_col."""
    valid = [r for r in rows if isinstance(r.get(metric_col), (int, float)) and r[metric_col] > 0]
    return min(valid, key=lambda r: r[metric_col]) if valid else None


def get_top_n(rows: list[dict], metric_col: str, n: int = 10) -> list[dict]:
    """Return the top N rows sorted descending by metric_col."""
    valid = [r for r in rows if isinstance(r.get(metric_col), (int, float))]
    return sorted(valid, key=lambda r: r[metric_col], reverse=True)[:n]


def get_bottom_n(rows: list[dict], metric_col: str, n: int = 10) -> list[dict]:
    """Return the bottom N rows (non-zero) sorted ascending by metric_col."""
    valid = [r for r in rows if isinstance(r.get(metric_col), (int, float)) and r[metric_col] > 0]
    return sorted(valid, key=lambda r: r[metric_col])[:n]


def log_payload_stats(label: str, result: dict, system_prompt: str = "") -> None:
    """Log token/size stats for a Bedrock payload component."""
    result_json = json.dumps(result, default=str)
    result_tokens = len(result_json) // CHARS_PER_TOKEN
    sys_tokens    = len(system_prompt) // CHARS_PER_TOKEN

    log.info(
        "[QueryEngine:%s] rows=%d result_tokens=%d sys_tokens=%d total_est=%d",
        label, len(result.get("rows", [])), result_tokens, sys_tokens,
        result_tokens + sys_tokens,
    )
    if result_tokens + sys_tokens > 150_000:
        log.error(
            "[QueryEngine:%s] CRITICAL: total estimated tokens %d approaching 200K limit!",
            label, result_tokens + sys_tokens,
        )
