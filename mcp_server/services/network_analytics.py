"""
mcp_server/services/network_analytics.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Network Analytics Engine (ADDITIVE — new features only)

Provides backend pre-computation for:
  - Network Code Intelligence (Feature 1)
  - Match Rate Analytics       (Feature 3)
  - Child Network Analytics    (Feature 4)
  - Network Comparison         (Feature 5)
  - Network Health Scoring     (Feature 6)
  - Automatic Insights         (Feature 7)
  - Anomaly Detection          (Feature 8)

All analytics are computed HERE in Python before any result
reaches the LLM. The LLM only receives summarized, structured
payloads and generates natural-language explanations.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import pandas as pd

log = logging.getLogger("network_analytics")


# ─── Health Score Thresholds ──────────────────────────────────────────────────

_HEALTH_EXCELLENT  = {"fill_rate": 90, "match_rate": 70, "ecpm_min": 0.50}
_HEALTH_HEALTHY    = {"fill_rate": 70, "match_rate": 50, "ecpm_min": 0.10}
_HEALTH_WARNING    = {"fill_rate": 40, "match_rate": 30, "ecpm_min": 0.01}
_HEALTH_CRITICAL   = {"fill_rate": 10, "match_rate": 10}


# ─── Helper: safe division ────────────────────────────────────────────────────

def _pct(numerator: float, denominator: float, cap: float = 100.0) -> float:
    if denominator <= 0:
        return 0.0
    return round(min(numerator / denominator * 100, cap), 2)


def _ecpm(revenue: float, impressions: float) -> float:
    if impressions <= 0:
        return 0.0
    return round(revenue / impressions * 1000, 4)


def _ctr(clicks: float, impressions: float) -> float:
    return _pct(clicks, impressions)


# ─── Network Health Score ─────────────────────────────────────────────────────

def compute_network_health(metrics: dict) -> dict:
    """
    Evaluate a network/entity's health using fill rate, match rate, and eCPM.

    Returns:
        {
            "health_status": "Excellent" | "Healthy" | "Warning" | "Critical" | "Offline",
            "health_score": 0-100 (integer),
            "health_reasons": [...],
        }
    """
    fill_rate  = float(metrics.get("fill_rate", 0) or 0)
    match_rate = float(metrics.get("match_rate", 0) or 0)
    revenue    = float(metrics.get("revenue", 0) or 0)
    impressions = float(metrics.get("impressions", 0) or 0)
    ad_requests = float(metrics.get("ad_requests", 0) or 0)
    ecpm_val   = _ecpm(revenue, impressions)

    reasons: list[str] = []

    # Offline: zero activity
    if impressions == 0 and ad_requests == 0:
        return {
            "health_status": "Offline",
            "health_score": 0,
            "health_reasons": ["No ad requests or impressions detected."],
        }

    # Build score (0-100)
    score = 50  # neutral baseline

    # Fill rate component (max ±30)
    if fill_rate >= _HEALTH_EXCELLENT["fill_rate"]:
        score += 30
    elif fill_rate >= _HEALTH_HEALTHY["fill_rate"]:
        score += 20
    elif fill_rate >= _HEALTH_WARNING["fill_rate"]:
        score += 5
    elif fill_rate >= _HEALTH_CRITICAL["fill_rate"]:
        score -= 10
        reasons.append(f"Fill rate critically low at {fill_rate:.1f}%.")
    else:
        score -= 25
        reasons.append(f"Fill rate at {fill_rate:.1f}% — near zero.")

    # Match rate component (max ±15)
    if match_rate > 0:
        if match_rate >= _HEALTH_EXCELLENT["match_rate"]:
            score += 15
        elif match_rate >= _HEALTH_HEALTHY["match_rate"]:
            score += 8
        elif match_rate >= _HEALTH_WARNING["match_rate"]:
            score += 2
        else:
            score -= 8
            reasons.append(f"Match rate low at {match_rate:.1f}%.")

    # Revenue / eCPM component (max ±5)
    if revenue > 0 and ecpm_val >= _HEALTH_EXCELLENT["ecpm_min"]:
        score += 5
    elif revenue == 0 and impressions > 0:
        score -= 5
        reasons.append("Serving impressions but generating zero revenue.")

    # Clamp score
    score = max(0, min(100, score))

    # Classify
    if score >= 85:
        status = "Excellent"
    elif score >= 65:
        status = "Healthy"
    elif score >= 40:
        status = "Warning"
    elif score >= 15:
        status = "Critical"
    else:
        status = "Offline"

    if not reasons:
        reasons = [f"Fill rate: {fill_rate:.1f}%, Match rate: {match_rate:.1f}%, eCPM: ${ecpm_val:.4f}"]

    return {
        "health_status": status,
        "health_score": score,
        "health_reasons": reasons,
    }


# ─── Network Summary ──────────────────────────────────────────────────────────

def compute_network_summary(
    df: pd.DataFrame,
    network_code: str,
    start: date,
    end: date,
) -> dict:
    """
    Compute a comprehensive network-level summary from live GAM data.
    Returns a compact dict safe to send to the LLM.
    """
    if df.empty:
        return {
            "network_code": network_code,
            "period": f"{start} to {end}",
            "error": "No data returned from Google Ad Manager for this period.",
        }

    rev    = float(df["ad_server_cpm_and_cpc_revenue"].sum())
    imp    = int(df["ad_server_impressions"].sum())
    clicks = int(df["ad_server_clicks"].sum())

    # Ad requests — prefer canonical > total > ad_server
    req = 0
    for col in ["canonical_ad_requests", "total_ad_requests", "ad_server_ad_requests"]:
        if col in df.columns:
            v = int(df[col].sum())
            if v > 0:
                req = v
                break

    # Matched requests
    matched = 0
    for col in ["matched_requests", "total_responses_served"]:
        if col in df.columns:
            v = int(df[col].sum())
            if v > 0:
                matched = v
                break

    fill_rate_val  = _pct(imp, req)
    match_rate_val = _pct(matched, req)
    ecpm_val       = _ecpm(rev, imp)
    ctr_val        = _ctr(clicks, imp)

    # Active entities
    active_apps = 0
    active_websites = 0
    if "ad_unit_name" in df.columns:
        ad_units = df["ad_unit_name"].unique()
        active_apps = len(ad_units)
        # Rough heuristic: if name contains a dot it's likely a website domain
        active_websites = sum(
            1 for u in ad_units
            if isinstance(u, str) and "." in u and not u.startswith("com.")
        )

    health = compute_network_health({
        "fill_rate": fill_rate_val,
        "match_rate": match_rate_val,
        "revenue": rev,
        "impressions": imp,
        "ad_requests": req,
    })

    return {
        "network_code": network_code,
        "period": f"{start} to {end}",
        "revenue_usd": round(rev, 2),
        "impressions": imp,
        "clicks": clicks,
        "ad_requests": req,
        "matched_requests": matched,
        "fill_rate_pct": fill_rate_val,
        "match_rate_pct": match_rate_val,
        "ecpm_usd": ecpm_val,
        "ctr_pct": ctr_val,
        "active_ad_units": active_apps,
        "health_status": health["health_status"],
        "health_score": health["health_score"],
        "health_reasons": health["health_reasons"],
    }


# ─── Child Network Analytics ──────────────────────────────────────────────────

def compute_child_network_analytics(
    df: pd.DataFrame,
    start: date,
    end: date,
    metric: str = "revenue",
    limit: int = 15,
    filter_network: str = "",
) -> dict:
    """
    Compute per-child-network analytics from a DataFrame that has
    CHILD_NETWORK_CODE as a dimension column.

    Returns a compact, LLM-safe payload.
    """
    if df.empty:
        return {
            "period": f"{start} to {end}",
            "error": (
                "No child network data returned. This account may not be an MCM "
                "parent, or no child networks are registered."
            ),
        }

    # The child network code column name after our normalization
    cn_col = next(
        (c for c in ["child_network_code", "network_code"] if c in df.columns),
        None,
    )
    if cn_col is None:
        return {
            "period": f"{start} to {end}",
            "error": "Child network dimension not present in report. "
                     "Use dimension='child_network' in query_gam_data.",
        }

    agg_cols = {}
    for col in [
        "ad_server_cpm_and_cpc_revenue", "ad_server_impressions",
        "ad_server_clicks", "ad_server_ad_requests",
        "canonical_ad_requests", "total_ad_requests",
        "matched_requests", "total_responses_served",
    ]:
        if col in df.columns:
            agg_cols[col] = "sum"

    if not agg_cols:
        return {"period": f"{start} to {end}", "error": "No metric columns in DataFrame."}

    grouped = df.groupby(cn_col).agg(agg_cols).reset_index()

    # Optional filter
    if filter_network:
        mask = grouped[cn_col].astype(str).str.contains(filter_network, case=False, na=False)
        if mask.any():
            grouped = grouped[mask]

    networks = []
    for _, row in grouped.iterrows():
        code = str(row[cn_col])
        rev  = float(row.get("ad_server_cpm_and_cpc_revenue", 0))
        imp  = int(row.get("ad_server_impressions", 0))
        clk  = int(row.get("ad_server_clicks", 0))

        # Ad requests
        req = 0
        for c in ["canonical_ad_requests", "total_ad_requests", "ad_server_ad_requests"]:
            if c in row.index:
                v = int(row.get(c, 0))
                if v > 0:
                    req = v
                    break

        # Matched requests
        matched = 0
        for c in ["matched_requests", "total_responses_served"]:
            if c in row.index:
                v = int(row.get(c, 0))
                if v > 0:
                    matched = v
                    break

        fill_r  = _pct(imp, req)
        match_r = _pct(matched, req)
        ecpm_v  = _ecpm(rev, imp)
        ctr_v   = _ctr(clk, imp)

        health = compute_network_health({
            "fill_rate": fill_r,
            "match_rate": match_r,
            "revenue": rev,
            "impressions": imp,
            "ad_requests": req,
        })

        networks.append({
            "child_network_code": code,
            "revenue_usd": round(rev, 2),
            "impressions": imp,
            "clicks": clk,
            "ad_requests": req,
            "matched_requests": matched,
            "fill_rate_pct": fill_r,
            "match_rate_pct": match_r,
            "ecpm_usd": ecpm_v,
            "ctr_pct": ctr_v,
            "health_status": health["health_status"],
            "health_score": health["health_score"],
        })

    # Sort by requested metric
    sort_key_map = {
        "revenue":    "revenue_usd",
        "impressions":"impressions",
        "fill_rate":  "fill_rate_pct",
        "match_rate": "match_rate_pct",
        "ecpm":       "ecpm_usd",
        "ctr":        "ctr_pct",
        "ad_requests":"ad_requests",
        "clicks":     "clicks",
    }
    sort_key = sort_key_map.get(metric, "revenue_usd")
    networks.sort(key=lambda x: x.get(sort_key, 0), reverse=True)

    total_networks = len(networks)
    top_n = networks[:limit]

    # Compute anomalies across all child networks
    anomalies = []
    for n in networks:
        anomalies.extend(_detect_entity_anomalies(n, label=f"Child network {n['child_network_code']}"))

    result = {
        "period": f"{start} to {end}",
        "total_child_networks": total_networks,
        "metric_sorted_by": sort_key,
        "child_networks": top_n,
    }
    if anomalies:
        result["anomalies"] = anomalies[:10]  # cap at 10 for token budget

    return result


# ─── Match Rate Analytics ─────────────────────────────────────────────────────

def compute_match_rate_analytics(
    df: pd.DataFrame,
    dimension: str,
    start: date,
    end: date,
    filter_name: str = "",
    limit: int = 15,
) -> dict:
    """
    Compute match rate breakdown by any dimension.
    Match Rate = Matched Requests / Total Ad Requests * 100
    """
    if df.empty:
        return {
            "period": f"{start} to {end}",
            "dimension": dimension,
            "error": "No data returned from Google Ad Manager.",
        }

    # Determine grouping column
    if dimension in ("app", "ad_unit"):
        group_col = "ad_unit_name"
    elif dimension == "website":
        if "ad_unit_name" in df.columns:
            df = df.copy()
            import re as _re
            def _dom(s):
                if not isinstance(s, str):
                    return str(s)
                s = s.split(" - ")[0].split(" (")[0]
                parts = s.split("/")
                return parts[-1].strip() if len(parts) > 1 else s.strip()
            df["_website"] = df["ad_unit_name"].apply(_dom)
            group_col = "_website"
        else:
            return {"period": f"{start} to {end}", "error": "ad_unit_name column missing."}
    elif dimension == "child_network":
        group_col = next(
            (c for c in ["child_network_code", "network_code"] if c in df.columns), None
        )
        if group_col is None:
            return {"period": f"{start} to {end}", "error": "child_network_code column missing."}
    else:
        group_col = "ad_unit_name"

    if group_col not in df.columns:
        return {"period": f"{start} to {end}", "error": f"Column '{group_col}' not in data."}

    # Aggregate
    agg = {}
    for c in ["ad_server_impressions", "ad_server_cpm_and_cpc_revenue",
              "ad_server_ad_requests", "canonical_ad_requests",
              "total_ad_requests", "matched_requests", "total_responses_served",
              "adx_impressions"]:
        if c in df.columns:
            agg[c] = "sum"

    grouped = df.groupby(group_col).agg(agg).reset_index()

    if filter_name:
        mask = grouped[group_col].astype(str).str.lower().str.contains(
            filter_name.lower(), na=False
        )
        if mask.any():
            grouped = grouped[mask]

    rows = []
    for _, row in grouped.iterrows():
        name = str(row[group_col])
        imp  = int(row.get("ad_server_impressions", 0))
        rev  = float(row.get("ad_server_cpm_and_cpc_revenue", 0))

        req = 0
        for c in ["canonical_ad_requests", "total_ad_requests", "ad_server_ad_requests"]:
            if c in row.index:
                v = int(row.get(c, 0))
                if v > 0:
                    req = v
                    break

        matched = 0
        for c in ["matched_requests", "total_responses_served", "adx_impressions"]:
            if c in row.index:
                v = int(row.get(c, 0))
                if v > 0:
                    matched = v
                    break

        match_r = _pct(matched, req)
        fill_r  = _pct(imp, req)

        rows.append({
            "name": name,
            "match_rate_pct": match_r,
            "fill_rate_pct": fill_r,
            "ad_requests": req,
            "matched_requests": matched,
            "impressions": imp,
            "revenue_usd": round(rev, 2),
        })

    rows.sort(key=lambda x: x["match_rate_pct"], reverse=True)

    top_rows    = rows[:limit]
    bottom_rows = sorted(
        [r for r in rows if r["ad_requests"] > 0],
        key=lambda x: x["match_rate_pct"]
    )[:5]

    network_total_req     = sum(r["ad_requests"] for r in rows)
    network_total_matched = sum(r["matched_requests"] for r in rows)
    network_match_rate    = _pct(network_total_matched, network_total_req)

    return {
        "period": f"{start} to {end}",
        "dimension": dimension,
        "network_match_rate_pct": network_match_rate,
        "total_entities": len(rows),
        "top_match_rate": top_rows,
        "lowest_match_rate": bottom_rows,
    }


# ─── Anomaly Detection ────────────────────────────────────────────────────────

def _detect_entity_anomalies(metrics: dict, label: str = "") -> list[dict]:
    """
    Detect anomalies for a single entity (network, child network, app, website).
    Returns a list of anomaly dicts.
    """
    anomalies = []
    rev    = float(metrics.get("revenue_usd", metrics.get("revenue", 0)) or 0)
    imp    = float(metrics.get("impressions", 0) or 0)
    req    = float(metrics.get("ad_requests", 0) or 0)
    fr     = float(metrics.get("fill_rate_pct", metrics.get("fill_rate", 0)) or 0)
    mr     = float(metrics.get("match_rate_pct", metrics.get("match_rate", 0)) or 0)
    ctr    = float(metrics.get("ctr_pct", metrics.get("ctr", 0)) or 0)

    prefix = f"{label}: " if label else ""

    if req > 1000 and imp == 0:
        anomalies.append({
            "type": "zero_fill",
            "severity": "critical",
            "message": f"{prefix}Ad requests ({int(req):,}) received but zero impressions served.",
        })
    if rev == 0 and imp > 500:
        anomalies.append({
            "type": "zero_revenue",
            "severity": "critical",
            "message": f"{prefix}Generating impressions ({int(imp):,}) but zero revenue.",
        })
    if 0 < fr < 20 and req > 1000:
        anomalies.append({
            "type": "low_fill_rate",
            "severity": "warning",
            "message": f"{prefix}Fill rate critically low at {fr:.1f}%.",
        })
    if 0 < mr < 20 and req > 1000:
        anomalies.append({
            "type": "low_match_rate",
            "severity": "warning",
            "message": f"{prefix}Match rate very low at {mr:.1f}%.",
        })
    if ctr > 15 and imp > 1000:
        anomalies.append({
            "type": "ctr_spike",
            "severity": "warning",
            "message": f"{prefix}CTR spike detected at {ctr:.1f}% — investigate for invalid traffic.",
        })

    return anomalies


def compute_anomalies_from_df(df: pd.DataFrame) -> list[dict]:
    """
    Detect anomalies across all ad units in the DataFrame.
    Returns a list of anomaly dicts (capped at 20).
    """
    if df.empty:
        return []

    if "ad_unit_name" not in df.columns:
        return []

    agg = df.groupby("ad_unit_name").agg({
        "ad_server_cpm_and_cpc_revenue": "sum",
        "ad_server_impressions": "sum",
        "ad_server_clicks": "sum",
        "ad_server_ad_requests": "sum",
    }).reset_index()

    anomalies = []
    for _, row in agg.iterrows():
        name = str(row["ad_unit_name"])
        imp  = float(row["ad_server_impressions"])
        rev  = float(row["ad_server_cpm_and_cpc_revenue"])
        req  = float(row["ad_server_ad_requests"])
        clk  = float(row["ad_server_clicks"])

        fr  = _pct(imp, req)
        ctr = _ctr(clk, imp)

        metrics = {
            "revenue": rev,
            "impressions": imp,
            "ad_requests": req,
            "fill_rate": fr,
            "match_rate": 0,
            "ctr": ctr,
        }
        anomalies.extend(_detect_entity_anomalies(metrics, label=name))

    return anomalies[:20]


# ─── Automatic Insights ───────────────────────────────────────────────────────

def compute_automatic_insights(
    summary: dict,
    child_networks: list[dict] = None,
) -> dict:
    """
    Generate structured insights from aggregated network metrics.
    These are pre-computed by the backend — not hallucinated by the LLM.

    Returns:
        {
            "strengths": [...],
            "weaknesses": [...],
            "risk_areas": [...],
            "optimization_opportunities": [...],
            "revenue_opportunities": [...],
        }
    """
    strengths: list[str] = []
    weaknesses: list[str] = []
    risk_areas: list[str] = []
    optimizations: list[str] = []
    revenue_opps: list[str] = []

    fill_rate  = float(summary.get("fill_rate_pct", 0) or 0)
    match_rate = float(summary.get("match_rate_pct", 0) or 0)
    ecpm       = float(summary.get("ecpm_usd", 0) or 0)
    ctr        = float(summary.get("ctr_pct", 0) or 0)
    revenue    = float(summary.get("revenue_usd", 0) or 0)
    impressions = float(summary.get("impressions", 0) or 0)
    health     = summary.get("health_status", "Unknown")

    # Strengths
    if fill_rate >= 90:
        strengths.append(f"Excellent fill rate of {fill_rate:.1f}% — inventory is well-utilized.")
    if match_rate >= 70:
        strengths.append(f"Strong match rate of {match_rate:.1f}% — programmatic demand is healthy.")
    if ecpm >= 1.0:
        strengths.append(f"eCPM of ${ecpm:.2f} indicates premium inventory pricing.")
    if health in ("Excellent", "Healthy"):
        strengths.append(f"Overall network health is {health}.")

    # Weaknesses
    if 0 < fill_rate < 60:
        weaknesses.append(
            f"Fill rate at {fill_rate:.1f}% — significant inventory going unfilled. "
            "Consider adding demand partners."
        )
    if 0 < match_rate < 40:
        weaknesses.append(
            f"Match rate at {match_rate:.1f}% — programmatic demand is underperforming. "
            "Review bid floor settings."
        )
    if 0 < ecpm < 0.10 and impressions > 10000:
        weaknesses.append(
            f"eCPM at ${ecpm:.4f} is extremely low for the traffic volume. "
            "Monetization is inefficient."
        )

    # Risk Areas
    if revenue == 0 and impressions > 0:
        risk_areas.append("Serving impressions with zero revenue — demand configuration issue suspected.")
    if fill_rate == 0 and impressions > 0:
        risk_areas.append("Fill rate is 0% despite active traffic — ad server configuration may be broken.")
    if health in ("Critical", "Offline"):
        risk_areas.append(f"Network health is {health} — immediate investigation required.")

    # Child network specific risks
    if child_networks:
        offline = [n for n in child_networks if n.get("health_status") == "Offline"]
        critical = [n for n in child_networks if n.get("health_status") == "Critical"]
        if offline:
            risk_areas.append(
                f"{len(offline)} child network(s) are Offline: "
                + ", ".join(n["child_network_code"] for n in offline[:3])
            )
        if critical:
            risk_areas.append(
                f"{len(critical)} child network(s) are Critical: "
                + ", ".join(n["child_network_code"] for n in critical[:3])
            )

    # Optimization Opportunities
    if fill_rate < 80:
        optimizations.append("Enable Open Bidding to increase demand competition and fill rate.")
    if match_rate < 60:
        optimizations.append("Lower bid floors on low-traffic placements to improve match rate.")
    if ctr < 0.5 and impressions > 50000:
        optimizations.append("CTR below 0.5% — review ad placement, creative formats, and viewability.")
    if ecpm > 0 and fill_rate < 70:
        optimizations.append("Unfilled inventory represents a direct revenue loss — prioritize demand expansion.")

    # Revenue Opportunities
    unfilled_estimate = 0.0
    if fill_rate > 0 and fill_rate < 100 and ecpm > 0:
        req = float(summary.get("ad_requests", 0) or 0)
        unfilled_req = req * (1 - fill_rate / 100)
        unfilled_estimate = (unfilled_req * ecpm) / 1000
        if unfilled_estimate > 1:
            revenue_opps.append(
                f"Estimated revenue from unfilled inventory: ${unfilled_estimate:,.2f} "
                f"(assuming current eCPM of ${ecpm:.2f})."
            )

    if match_rate < 80 and match_rate > 0:
        revenue_opps.append(
            "Improving match rate to industry standard (80%+) could significantly increase programmatic revenue."
        )

    return {
        "strengths": strengths or ["Insufficient data for strength analysis."],
        "weaknesses": weaknesses or ["No significant weaknesses detected."],
        "risk_areas": risk_areas or ["No critical risk areas identified."],
        "optimization_opportunities": optimizations or ["No immediate optimizations flagged."],
        "revenue_opportunities": revenue_opps or ["No revenue gap identified from current metrics."],
    }


# ─── Network Comparison ───────────────────────────────────────────────────────

def compare_entities(
    rows: list[dict],
    metric: str = "revenue",
    entity_type: str = "child_network",
) -> dict:
    """
    Generate a comparison summary across a list of entities
    (child networks, apps, websites).

    Returns a compact comparison table + winner/loser highlights.
    """
    if not rows:
        return {"error": "No entities to compare."}

    metric_key_map = {
        "revenue":    "revenue_usd",
        "impressions":"impressions",
        "fill_rate":  "fill_rate_pct",
        "match_rate": "match_rate_pct",
        "ecpm":       "ecpm_usd",
        "ctr":        "ctr_pct",
        "ad_requests":"ad_requests",
        "clicks":     "clicks",
    }
    key = metric_key_map.get(metric, "revenue_usd")

    valid = [r for r in rows if isinstance(r.get(key), (int, float))]
    if not valid:
        return {"error": f"Metric '{metric}' not available in results."}

    sorted_asc  = sorted(valid, key=lambda x: x[key])
    sorted_desc = sorted(valid, key=lambda x: x[key], reverse=True)

    return {
        "metric": metric,
        "entity_type": entity_type,
        "winner": sorted_desc[0],
        "runner_up": sorted_desc[1] if len(sorted_desc) > 1 else None,
        "lowest": sorted_asc[0],
        "average": round(sum(r[key] for r in valid) / len(valid), 4),
        "all_ranked": sorted_desc,
    }
