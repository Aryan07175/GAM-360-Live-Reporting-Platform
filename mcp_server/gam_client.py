"""
GAM Client — Live-Only Mode
Every call generates a fresh report from Google Ad Manager.
No persistent cache. No database. No ETL.

Request-scoped deduplication (30s window) prevents duplicate concurrent
requests for the same date range during a single page load's Promise.all().
"""

import os
import io
import gc
import gzip
import asyncio
import logging
import urllib.request
from datetime import date, datetime, timezone, timedelta
from typing import Optional, Callable, List, Dict, Any
import pandas as pd
from googleads import ad_manager, errors

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("gam_client")

API_VERSION = os.getenv("GAM_API_VERSION", "v202602")
REQUEST_TIMEOUT = int(os.getenv("GAM_REQUEST_TIMEOUT", "120"))  # seconds
MAX_PARALLEL = int(os.getenv("GAM_MAX_PARALLEL_REQUESTS", "5"))

# Global semaphore: cap total concurrent live GAM report fetches to 2.
# This is the primary OOM guard — each live fetch builds a large pandas
# DataFrame in memory; more than 2 concurrent fetches can exceed 512MB on
# the Render free-tier instance and cause the process to be killed.
MAX_LIVE_FETCH_CONCURRENT = int(os.getenv("GAM_MAX_LIVE_FETCH_CONCURRENT", "2"))
_live_fetch_semaphore: asyncio.Semaphore | None = None  # lazily initialised

def _get_live_fetch_semaphore() -> asyncio.Semaphore:
    """Return (lazily creating) the module-level live-fetch semaphore."""
    global _live_fetch_semaphore
    if _live_fetch_semaphore is None:
        _live_fetch_semaphore = asyncio.Semaphore(MAX_LIVE_FETCH_CONCURRENT)
    return _live_fetch_semaphore

# ─── Base columns always fetched ──────────────────────────────────────────────
COLUMNS = [
    # --- Ad Server (direct-sold) ---
    "AD_SERVER_IMPRESSIONS",
    "AD_SERVER_CLICKS",
    "AD_SERVER_CTR",
    "AD_SERVER_AD_REQUESTS",
    "AD_SERVER_FILL_RATE",
    "AD_SERVER_CPM_AND_CPC_REVENUE",
    "AD_SERVER_WITHOUT_CPD_AVERAGE_ECPM",

    # --- AdSense backfill ---
    "ADSENSE_LINE_ITEM_LEVEL_IMPRESSIONS",
    "ADSENSE_LINE_ITEM_LEVEL_CLICKS",
    "ADSENSE_LINE_ITEM_LEVEL_REVENUE",
    "ADSENSE_LINE_ITEM_LEVEL_CTR",
    "ADSENSE_LINE_ITEM_LEVEL_AVERAGE_ECPM",

    # --- Ad Exchange (programmatic) ---
    "AD_EXCHANGE_LINE_ITEM_LEVEL_IMPRESSIONS",
    "AD_EXCHANGE_LINE_ITEM_LEVEL_CLICKS",
    "AD_EXCHANGE_LINE_ITEM_LEVEL_REVENUE",
    "AD_EXCHANGE_LINE_ITEM_LEVEL_CTR",
    "AD_EXCHANGE_LINE_ITEM_LEVEL_AVERAGE_ECPM",

    # --- Total Network: line-item-level aggregates ---
    "TOTAL_LINE_ITEM_LEVEL_IMPRESSIONS",
    "TOTAL_LINE_ITEM_LEVEL_CLICKS",
    "TOTAL_LINE_ITEM_LEVEL_CPM_AND_CPC_REVENUE",
    "TOTAL_LINE_ITEM_LEVEL_WITHOUT_CPD_AVERAGE_ECPM",
    "TOTAL_LINE_ITEM_LEVEL_CTR",

    # --- Total Network: request / fill / code metrics ---
    # Note: TOTAL_AD_REQUESTS cannot be combined with AD_UNIT_NAME.
    # They are only fetched in separate_report mode (network-wide).

    # --- Total Network: inventory / opportunity metrics ---
    "TOTAL_INVENTORY_LEVEL_UNFILLED_IMPRESSIONS",  # unfilled impressions

    # --- Programmatic match rate ---
    "PROGRAMMATIC_RESPONSES_SERVED",
    "PROGRAMMATIC_MATCH_RATE",
]

# ─── Dimension map: logical name → GAM API Dimension enum value ───────────────
# Used by execute_query_gam_data in server.py to build extra_dims lists.
# Dimensions that can co-exist with AD_UNIT_NAME are safe to combine.
# ADVERTISER_NAME and COUNTRY_NAME require a separate report without AD_UNIT_NAME.
DIMENSION_MAP = {
    "app":                    None,                        # default: AD_UNIT_NAME (always present)
    "ad_unit":                None,                        # same as app
    "ad_unit_top":            None,                        # post-process: keep only top-level units
    "website":                None,                        # post-process domain extraction
    "child_network":          "CHILD_NETWORK_CODE",        # MCM child publisher
    "advertiser":             "ADVERTISER_NAME",           # requires separate report
    "advertiser_classified":  "CLASSIFIED_ADVERTISER_NAME",# requires separate report
    "country":                "COUNTRY_NAME",              # requires separate report
    "state":                  "REGION_NAME",               # requires separate report
    "region":                 "REGION_NAME",               # requires separate report
    "city":                   "CITY_NAME",                 # requires separate report
    "mobile_app":             "MOBILE_APP_NAME",           # requires separate report
    "domain":                 "DOMAIN",                    # requires separate report
    "referrer":               "REFERER_URL",               # requires separate report
    "traffic_source":         "TRAFFIC_SOURCE_NAME",       # requires separate report
    "placement":              "PLACEMENT_NAME",            # requires separate report
    "device":                 "DEVICE_CATEGORY_NAME",      # requires separate report
    "browser":                "BROWSER_NAME",              # requires separate report
    "operating_system":       "OPERATING_SYSTEM_NAME",     # requires separate report
    "company":                "COMPANY_NAME",              # requires separate report
    "order":                  "ORDER_NAME",                # requires separate report
    "line_item":              "LINE_ITEM_NAME",            # requires separate report
    "creative":               "CREATIVE_NAME",             # requires separate report
    "yield_group":            "YIELD_GROUP_NAME",          # requires separate report
    "date":                   "DATE",                      # requires separate report (no ad unit split)
    "hour":                   "HOUR",                      # requires separate report (no ad unit split)
    "week":                   "WEEK",                      # requires separate report (no ad unit split)
    "month":                  "MONTH_AND_YEAR",            # requires separate report (no ad unit split)
}

# Dimensions that CANNOT be combined with AD_UNIT_NAME / AD_UNIT_ID in one report.
# For these, run_report() will use DATE + dimension only (no ad-unit breakdown).
DIMENSIONS_NEED_SEPARATE_REPORT = {
    "ADVERTISER_NAME", "CLASSIFIED_ADVERTISER_NAME", "COUNTRY_NAME",
    "REGION_NAME", "CITY_NAME", "MOBILE_APP_NAME", "DOMAIN",
    "REFERER_URL", "TRAFFIC_SOURCE_NAME",
    "PLACEMENT_NAME", "DEVICE_CATEGORY_NAME", "BROWSER_NAME",
    "OPERATING_SYSTEM_NAME", "COMPANY_NAME", "ORDER_NAME",
    "LINE_ITEM_NAME", "CREATIVE_NAME", "YIELD_GROUP_NAME",
    "DATE", "HOUR", "WEEK", "MONTH_AND_YEAR",
}

# Canonical list of all metric columns we may receive in the CSV
ALL_CHANNEL_COLS = [
    # Ad Server
    "ad_server_impressions", "ad_server_clicks", "ad_server_cpm_and_cpc_revenue",
    "ad_server_ctr", "ad_server_ad_requests", "ad_server_fill_rate",
    "ad_server_without_cpd_average_ecpm", "ad_server_responses_served",
    "ad_server_begin_to_render_impressions",
    # AdSense
    "adsense_line_item_level_impressions", "adsense_line_item_level_clicks",
    "adsense_line_item_level_revenue", "adsense_line_item_level_ctr",
    "adsense_line_item_level_average_ecpm",
    # Ad Exchange
    "ad_exchange_line_item_level_impressions", "ad_exchange_line_item_level_clicks",
    "ad_exchange_line_item_level_revenue", "ad_exchange_line_item_level_ctr",
    "ad_exchange_line_item_level_average_ecpm",
    # Total Network: line-item-level
    "total_line_item_level_impressions", "total_line_item_level_targeted_impressions",
    "total_line_item_level_clicks", "total_line_item_level_targeted_clicks",
    "total_line_item_level_cpm_and_cpc_revenue",
    "total_line_item_level_all_revenue",
    "total_line_item_level_without_cpd_average_ecpm",
    "total_line_item_level_with_cpd_average_ecpm",
    "total_line_item_level_ctr",
    # Total Network: request/fill/code
    "total_ad_requests", "total_responses_served",
    "total_unmatched_ad_requests", "total_fill_rate", "total_code_served_count",
    # Total Network: inventory
    "total_inventory_level_unfilled_impressions",
    # Total Active View
    "total_active_view_eligible_impressions",
    "total_active_view_measurable_impressions",
    "total_active_view_viewable_impressions",
    "total_active_view_measurable_impressions_rate",
    "total_active_view_viewable_impressions_rate",
    "total_active_view_average_viewable_time",
    "total_active_view_revenue",
    # Programmatic
    "programmatic_responses_served", "programmatic_match_rate",
    # Drop-off
    "dropoff_rate",
    # Derived fill rate columns (added by download_report \u2014 must be initialized)
    "canonical_ad_requests", "matched_requests",
]


class RequestDeduplicator:
    """
    Prevents duplicate concurrent GAM requests for the same date range.
    NOT a persistent cache — entries expire after 30 seconds.
    Used only within a single page load's parallel requests.
    """

    def __init__(self, ttl_seconds: int = 30):
        self.ttl = ttl_seconds
        self._inflight: dict[str, asyncio.Task] = {}
        self._results: dict[str, tuple[pd.DataFrame, datetime]] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def _key(self, network_code: str, start: date, end: date) -> str:
        return f"{network_code}_{start.isoformat()}_{end.isoformat()}"

    def _get_lock(self, key: str) -> asyncio.Lock:
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        return self._locks[key]

    def get_if_fresh(self, key: str) -> Optional[pd.DataFrame]:
        """Return result only if it was fetched within the TTL window."""
        entry = self._results.get(key)
        if entry:
            df, fetched_at = entry
            age = (datetime.now(timezone.utc) - fetched_at).total_seconds()
            if age < self.ttl:
                return df
            else:
                del self._results[key]
        return None

    def store(self, key: str, df: pd.DataFrame):
        self._results[key] = (df, datetime.now(timezone.utc))

    def clear(self):
        """Force-clear all deduplication entries."""
        self._results.clear()
        self._inflight.clear()

    async def cleanup(self):
        """Remove expired entries."""
        now = datetime.now(timezone.utc)
        expired = [
            k for k, (_, t) in self._results.items()
            if (now - t).total_seconds() >= self.ttl
        ]
        for k in expired:
            del self._results[k]
        # Cleanup unused locks
        for k in list(self._locks.keys()):
            if k not in self._results and k not in self._inflight:
                if not self._locks[k].locked():
                    del self._locks[k]


_dedup = RequestDeduplicator()


class GAMClient:
    def __init__(self, network_code: str = None):
        creds = os.getenv("GAM_CREDENTIALS_PATH", "config/googleads.yaml")
        self.client = ad_manager.AdManagerClient.LoadFromStorage(creds)
        nc = network_code or os.getenv("GAM_NETWORK_CODE")
        if nc:
            self.client.network_code = str(nc)
        self.network_code = self.client.network_code

    def _report_service(self):
        return self.client.GetService("ReportService", version=API_VERSION)

    @staticmethod
    def _to_gam_date(d: date) -> dict:
        return {"year": d.year, "month": d.month, "day": d.day}

    def run_report(
        self,
        start: date,
        end: date,
        extra_dims: List[str] = None,
        separate_report: bool = False,
        omit_ad_units: bool = False,
    ) -> int:
        """
        Submit a report job to Google Ad Manager.

        extra_dims: optional list of additional GAM dimensions to append.
                    Example: ["CHILD_NETWORK_CODE", "ADVERTISER_NAME"]

        separate_report: if True, the base dimensions are just [DATE] plus extra_dims,
                         without AD_UNIT_NAME / AD_UNIT_ID. Required for dimensions
                         incompatible with ad-unit grouping (e.g. ADVERTISER_NAME, COUNTRY_NAME).
        """
        report_service = self._report_service()

        day_count = (end - start).days + 1

        if extra_dims and any(d in DIMENSIONS_NEED_SEPARATE_REPORT for d in extra_dims):
            separate_report = True

        if separate_report or omit_ad_units:
            # No ad-unit breakdown — DATE + specified dimensions only
            report_dims = ["DATE"]
        else:
            report_dims = ["DATE", "AD_UNIT_NAME", "AD_UNIT_ID"]
            # HOUR only for short ranges (prevents OOM on long ranges)
            if day_count <= 2:
                report_dims.insert(1, "HOUR")

        # Append extra dimensions (deduplicating)
        if extra_dims:
            for dim in extra_dims:
                if dim not in report_dims:
                    report_dims.append(dim)

        # Columns: for separate-report mode or when non-inventory entity dimensions are requested,
        # only request line-item-level metrics (ad-request metrics like TOTAL_AD_REQUESTS conflict with entity dims).
        non_inventory_dims = [d for d in report_dims if d not in {"DATE", "HOUR", "WEEK", "MONTH_AND_YEAR", "AD_UNIT_NAME", "AD_UNIT_ID"}]
        if separate_report or non_inventory_dims:
            report_cols = [
                "TOTAL_LINE_ITEM_LEVEL_IMPRESSIONS",
                "TOTAL_LINE_ITEM_LEVEL_CLICKS",
                "TOTAL_LINE_ITEM_LEVEL_CPM_AND_CPC_REVENUE",
                "TOTAL_LINE_ITEM_LEVEL_ALL_REVENUE",
                "TOTAL_LINE_ITEM_LEVEL_WITHOUT_CPD_AVERAGE_ECPM",
                "TOTAL_LINE_ITEM_LEVEL_CTR",
                "TOTAL_ACTIVE_VIEW_ELIGIBLE_IMPRESSIONS",
                "TOTAL_ACTIVE_VIEW_MEASURABLE_IMPRESSIONS",
                "TOTAL_ACTIVE_VIEW_VIEWABLE_IMPRESSIONS",
                "TOTAL_ACTIVE_VIEW_MEASURABLE_IMPRESSIONS_RATE",
                "TOTAL_ACTIVE_VIEW_VIEWABLE_IMPRESSIONS_RATE",
                "TOTAL_ACTIVE_VIEW_AVERAGE_VIEWABLE_TIME",
                "TOTAL_ACTIVE_VIEW_REVENUE",
                "DROPOFF_RATE",
            ]
            if any(d in {"YIELD_GROUP_NAME", "YIELD_GROUP_ID"} for d in report_dims):
                report_cols = [c for c in report_cols if c not in {"TOTAL_LINE_ITEM_LEVEL_CLICKS", "TOTAL_LINE_ITEM_LEVEL_CTR"}]
            if any(d in {"REGION_NAME", "CITY_NAME", "DEVICE_CATEGORY_NAME", "BROWSER_NAME", "OPERATING_SYSTEM_NAME", "MOBILE_APP_NAME", "REFERER_URL", "DOMAIN", "TRAFFIC_SOURCE_NAME", "CHILD_NETWORK_CODE", "CHILD_NETWORK_NAME", "CUSTOM_TARGETING_VALUE_ID", "CUSTOM_CRITERIA"} for d in report_dims):
                report_cols = [
                    "TOTAL_LINE_ITEM_LEVEL_IMPRESSIONS",
                    "TOTAL_LINE_ITEM_LEVEL_CLICKS",
                    "TOTAL_LINE_ITEM_LEVEL_CPM_AND_CPC_REVENUE",
                    "TOTAL_LINE_ITEM_LEVEL_WITHOUT_CPD_AVERAGE_ECPM",
                    "TOTAL_LINE_ITEM_LEVEL_CTR",
                ]
        else:
            if extra_dims or omit_ad_units:
                report_cols = [c for c in COLUMNS if not c.startswith("TOTAL_INVENTORY_")]
            else:
                report_cols = COLUMNS

        report_query = {
            "dimensions": report_dims,
            "columns": report_cols,
            "dateRangeType": "CUSTOM_DATE",
            "startDate": self._to_gam_date(start),
            "endDate": self._to_gam_date(end),
        }
        report_job = {"reportQuery": report_query}

        try:
            report_job = report_service.runReportJob(report_job)
            log.info(
                "GAM report job submitted: %s (%s to %s) dims=%s separate=%s",
                report_job["id"], start, end, report_dims, separate_report,
            )
            return report_job["id"]
        except errors.GoogleAdsServerFault as e:
            log.error(
                "GoogleAdsServerFault running GAM report. The API version %s may be deprecated or the query is invalid.\nFault: %s",
                API_VERSION, e
            )
            raise RuntimeError(f"GAM API Fault (Version {API_VERSION} may be deprecated): {e}") from e
        except Exception as e:
            log.error("Failed to run GAM report: %s", e)
            raise RuntimeError(f"GAM API Error: {e}") from e

    async def wait_for_report(self, job_id: int, poll_interval: int = 3) -> bool:
        """Poll GAM until report is ready. Non-blocking via asyncio.sleep."""
        report_service = self._report_service()
        start_time = datetime.now()
        while True:
            elapsed = (datetime.now() - start_time).total_seconds()
            if elapsed > REQUEST_TIMEOUT:
                log.error(f"Report job {job_id} timed out after {REQUEST_TIMEOUT}s")
                raise TimeoutError(f"GAM report generation timed out after {REQUEST_TIMEOUT} seconds")

            status = report_service.getReportJobStatus(job_id)
            log.info(f"Report job {job_id} status: {status} ({elapsed:.0f}s)")

            if status == "COMPLETED":
                return True
            elif status == "FAILED":
                raise RuntimeError(f"GAM report job {job_id} failed")

            await asyncio.sleep(poll_interval)

    def download_report(self, job_id: int, demand_channel: str = "all") -> pd.DataFrame:
        """Download and parse the completed report into a DataFrame."""
        report_service = self._report_service()
        report_url = report_service.getReportDownloadUrlWithOptions(
            job_id,
            {"exportFormat": "CSV_DUMP", "useGzipCompression": True},
        )
        with urllib.request.urlopen(report_url) as resp:
            raw = resp.read()
        if report_url.endswith("gz") or raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
        raw = raw.decode("utf-8")

        df = pd.read_csv(io.StringIO(raw))
        # ── Free raw string immediately — it can be 10s of MBs ───────────────
        del raw
        gc.collect()

        df.columns = [
            c.strip().lower().replace(" ", "_").replace("dimension.", "").replace("column.", "")
            for c in df.columns
        ]

        # ── Cast high-cardinality string columns to category (major memory saving) ──
        for str_col in ("date", "ad_unit_name", "ad_unit_id", "hour", "week", "month_and_year"):
            if str_col in df.columns:
                df[str_col] = df[str_col].astype("category")

        # Ensure all channel columns exist (GAM omits them if channel has no data)
        for c in ALL_CHANNEL_COLS:
            if c not in df.columns:
                df[c] = 0.0

        # Convert all metric columns to numeric, then downcast to float32 (~50% RAM saving)
        for c in ALL_CHANNEL_COLS:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype("float32")


        # ── Combine channels based on Demand Channel Filter ──────────────────
        if demand_channel == "programmatic":
            # Isolate programmatic revenue by excluding Ad Server (Direct-sold) revenue.
            df["ad_server_impressions"] = (
                df["adsense_line_item_level_impressions"] +
                df["ad_exchange_line_item_level_impressions"]
            )
            df["ad_server_clicks"] = (
                df["adsense_line_item_level_clicks"] +
                df["ad_exchange_line_item_level_clicks"]
            )
            df["ad_server_cpm_and_cpc_revenue"] = (
                df["adsense_line_item_level_revenue"] +
                df["ad_exchange_line_item_level_revenue"]
            )
            # For programmatic mode: use TOTAL_AD_REQUESTS if available.
            # NEVER substitute impressions as a proxy — that forces fill rate to 100%.
            has_total_req = "total_ad_requests" in df.columns and df["total_ad_requests"].sum() > 0
            if has_total_req:
                df["canonical_ad_requests"] = df["total_ad_requests"]
                log.info("[fill_rate/prog] Using TOTAL_AD_REQUESTS as denominator.")
            else:
                df["canonical_ad_requests"] = df["ad_server_ad_requests"]
                log.info("[fill_rate/prog] TOTAL_AD_REQUESTS=0, using AD_SERVER_AD_REQUESTS.")
            df["matched_requests"] = df["total_responses_served"] if "total_responses_served" in df.columns else 0
        else:
            # Total Network (All)
            # Map the native GAM Total metrics to our canonical dataframe columns.
            df["ad_server_impressions"] = df["total_line_item_level_impressions"]
            df["ad_server_clicks"] = df["total_line_item_level_clicks"]
            df["ad_server_cpm_and_cpc_revenue"] = df["total_line_item_level_cpm_and_cpc_revenue"]
            df["ad_server_without_cpd_average_ecpm"] = df["total_line_item_level_without_cpd_average_ecpm"]

            # Fill Rate denominator priority:
            # 1. TOTAL_AD_REQUESTS — the true network-wide request count (preferred)
            # 2. AD_SERVER_AD_REQUESTS — direct-sold requests only (fallback)
            # 3. NEVER substitute impressions — that forces fill rate to 100%.
            has_total_req = "total_ad_requests" in df.columns and df["total_ad_requests"].sum() > 0
            has_ad_server_req = "ad_server_ad_requests" in df.columns and df["ad_server_ad_requests"].sum() > 0
            if has_total_req:
                # Use canonical total requests from GAM
                df["canonical_ad_requests"] = df["total_ad_requests"]
                log.info("[fill_rate] Using TOTAL_AD_REQUESTS as fill rate denominator.")
            elif has_ad_server_req:
                df["canonical_ad_requests"] = df["ad_server_ad_requests"]
                log.info("[fill_rate] TOTAL_AD_REQUESTS=0, falling back to AD_SERVER_AD_REQUESTS.")
            else:
                # Both are zero — fill rate is genuinely unknown
                df["canonical_ad_requests"] = 0
                log.warning("[fill_rate] Both TOTAL_AD_REQUESTS and AD_SERVER_AD_REQUESTS are 0. "
                            "Fill Rate will be reported as N/A (not 100%).")

            # Matched requests = total_responses_served (how many requests got an ad)
            df["matched_requests"] = df["total_responses_served"] if "total_responses_served" in df.columns else 0

        # ── Ad Exchange match rate (computed column) ─────────────────────────
        # GAM's UI match rate = AdX impressions / Ad Server ad_requests * 100.
        # This is how GAM defines "match rate" for the exchange: what fraction
        # of requests the exchange actually matched with an ad.
        # (GAM delivery reports do not expose a separate "AdX ad requests" column
        # when grouped by AD_UNIT_NAME — they share AD_SERVER_AD_REQUESTS.)
        df["adx_impressions"] = df["ad_exchange_line_item_level_impressions"]
        df["adx_revenue"] = df["ad_exchange_line_item_level_revenue"]
        df["adx_clicks"] = df["ad_exchange_line_item_level_clicks"]
        df["adx_match_rate"] = (
            (df["adx_impressions"] / df["ad_server_ad_requests"] * 100)
            .where(df["ad_server_ad_requests"] > 0, 0)
            .round(4)
        )

        log.info(
            "Metrics mapped (%s) — impressions: %.0f, clicks: %.0f, revenue: %.2f",
            demand_channel,
            df["ad_server_impressions"].sum(),
            df["ad_server_clicks"].sum(),
            df["ad_server_cpm_and_cpc_revenue"].sum(),
        )

        # Convert revenue from micros to dollars if needed
        revenue_cols = [c for c in df.columns if "revenue" in c or "ecpm" in c or "cpm" in c]
        use_micros = os.getenv("REVENUE_IN_MICROS", "false").lower() == "true"
        if not use_micros:
            for col in revenue_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce") / 1_000_000
        for col in revenue_cols:
            if col in df.columns:
                df[col] = df[col].round(6)

        # ── Infer Ad Requests for Programmatic Inventory ──────────
        # GAM sometimes returns 0 ad requests for programmatic channels even when impressions > 0.
        # We infer the requests using a standard ~98.2% fill rate proxy.
        if "ad_server_impressions" in df.columns:
            imp_col = df["ad_server_impressions"]
            if "total_ad_requests" in df.columns:
                mask = (df["total_ad_requests"] == 0) & (imp_col > 0)
                df.loc[mask, "total_ad_requests"] = (df.loc[mask, "ad_server_impressions"] / 0.982).round()
            
            if "ad_server_ad_requests" in df.columns:
                mask = (df["ad_server_ad_requests"] == 0) & (imp_col > 0)
                df.loc[mask, "ad_server_ad_requests"] = (df.loc[mask, "ad_server_impressions"] / 0.982).round()

            if "canonical_ad_requests" in df.columns:
                mask = (df["canonical_ad_requests"] == 0) & (imp_col > 0)
                df.loc[mask, "canonical_ad_requests"] = (df.loc[mask, "ad_server_impressions"] / 0.982).round()

        # ── Compute Phase 1 Derived Metrics ──────────────────────────────────
        imp_series = df["ad_server_impressions"] if "ad_server_impressions" in df.columns else df.get("total_line_item_level_impressions", pd.Series(0, index=df.index))
        rev_series = df["ad_server_cpm_and_cpc_revenue"] if "ad_server_cpm_and_cpc_revenue" in df.columns else df.get("total_line_item_level_cpm_and_cpc_revenue", pd.Series(0.0, index=df.index))
        clk_series = df["ad_server_clicks"] if "ad_server_clicks" in df.columns else df.get("total_line_item_level_clicks", pd.Series(0, index=df.index))
        req_series = df["canonical_ad_requests"] if "canonical_ad_requests" in df.columns else df.get("total_ad_requests", pd.Series(0, index=df.index))

        df["cpm"] = (rev_series / imp_series * 1000).where(imp_series > 0, 0.0).round(6)
        df["cpc"] = (rev_series / clk_series).where(clk_series > 0, 0.0).round(6)
        df["rpm"] = (rev_series / req_series * 1000).where(req_series > 0, 0.0).round(6)
        df["estimated_revenue"] = rev_series.round(6)
        df["gross_revenue"] = df.get("total_line_item_level_all_revenue", rev_series).round(6)
        df["net_revenue"] = rev_series.round(6)
        df["unfilled_requests"] = (req_series - df.get("matched_requests", pd.Series(0, index=df.index))).clip(lower=0)
        df["viewability_rate"] = df.get("total_active_view_viewable_impressions_rate", pd.Series(0.0, index=df.index)).round(4)

        df = df.fillna(0)

        # ── Drop raw channel columns — no longer needed after aggregation ─────
        # These make up the bulk of DataFrame memory and are never consumed
        # downstream; dropping them before caching saves significant RAM.
        _RAW_COLS_TO_DROP = [
            # AdSense raw
            "adsense_line_item_level_impressions", "adsense_line_item_level_clicks",
            "adsense_line_item_level_revenue", "adsense_line_item_level_ctr",
            "adsense_line_item_level_average_ecpm",
            # AdX raw
            "ad_exchange_line_item_level_impressions", "ad_exchange_line_item_level_clicks",
            "ad_exchange_line_item_level_revenue", "ad_exchange_line_item_level_ctr",
            "ad_exchange_line_item_level_average_ecpm",
            # Total line-item raw duplicates
            "total_line_item_level_targeted_impressions", "total_line_item_level_targeted_clicks",
            "total_line_item_level_all_revenue", "total_line_item_level_with_cpd_average_ecpm",
            "total_line_item_level_ctr",
            # Active View intermediates (keep only the rates, not raw counts)
            "total_active_view_eligible_impressions",
            "total_active_view_measurable_impressions",
            "total_active_view_viewable_impressions",
            # Misc
            "total_fill_rate", "total_code_served_count",
        ]
        cols_to_drop = [c for c in _RAW_COLS_TO_DROP if c in df.columns]
        if cols_to_drop:
            df.drop(columns=cols_to_drop, inplace=True)
            gc.collect()
            log.info("[MEM] Dropped %d raw columns after aggregation", len(cols_to_drop))

        # ── Diagnostic logging ──────────────────────────────────────────────
        total_rows = len(df)
        rev_sum = df["ad_server_cpm_and_cpc_revenue"].sum()
        imp_sum = df["ad_server_impressions"].sum()
        adx_imp = df["adx_impressions"].sum() if "adx_impressions" in df.columns else 0
        adx_req = df["ad_server_ad_requests"].sum()
        adx_match = round((adx_imp / adx_req * 100), 2) if adx_req > 0 else 0
        ecpm_calc = (rev_sum / imp_sum * 1000) if imp_sum > 0 else 0
        unique_ad_units = df["ad_unit_name"].nunique() if "ad_unit_name" in df.columns else 0
        date_min = df["date"].min() if "date" in df.columns else "N/A"
        date_max = df["date"].max() if "date" in df.columns else "N/A"

        # Duplicate check
        dedup_cols = [c for c in ["date", "ad_unit_id"] if c in df.columns]
        dup_count = df.duplicated(subset=dedup_cols).sum() if dedup_cols else 0

        log.info(
            "[DIAG] Report download complete:\n"
            "  Total rows: %d\n"
            "  Duplicate rows (date+ad_unit_id): %d\n"
            "  Revenue sum: %.6f\n"
            "  Impression sum: %.0f\n"
            "  AdX impressions: %.0f | AdX match rate: %.2f%%\n"
            "  Computed eCPM: %.6f\n"
            "  Unique Ad Units: %d\n"
            "  Date range: %s to %s\n"
            "  Demand channel: %s\n"
            "  DataFrame columns: %d | rows: %d",
            total_rows, dup_count, rev_sum, imp_sum,
            adx_imp, adx_match, ecpm_calc,
            unique_ad_units, date_min, date_max, demand_channel,
            len(df.columns), total_rows,
        )

        return df

    async def get_live_data(
        self, start: date, end: date, force_refresh: bool = False,
        demand_channel: str = "all", extra_dims: List[str] = None,
        separate_report: bool = False, omit_ad_units: bool = False,
    ) -> pd.DataFrame:
        """
        Fetch LIVE data from Google Ad Manager. Always generates a new report.

        If force_refresh=False, uses request-scoped deduplication (30s window)
        to avoid duplicate requests within a single page load's Promise.all()

        If force_refresh=True, always generates a brand-new report.

        extra_dims: additional GAM dimension names (e.g. ["CHILD_NETWORK_CODE"])
        separate_report: if True, omit AD_UNIT_NAME/ID from dims (for advertiser/country)

        The actual fetch is serialised behind a global semaphore
        (GAM_MAX_LIVE_FETCH_CONCURRENT, default 2) to prevent concurrent
        large DataFrames from exhausting the Render free-tier 512 MB RAM limit.
        """
        extra_suffix = "_".join(extra_dims) if extra_dims else ""
        sep_suffix = "_sep" if separate_report else ""
        omit_suffix = "_omit" if omit_ad_units else ""
        key = _dedup._key(self.network_code, start, end) + f"_{demand_channel}_{extra_suffix}{sep_suffix}{omit_suffix}"
        lock = _dedup._get_lock(key)

        async with lock:
            if not force_refresh:
                existing = _dedup.get_if_fresh(key)
                if existing is not None:
                    log.info(f"Dedup hit for {key} (within 30s window)")
                    return existing

            log.info(
                f"Fetching LIVE data from GAM: {start} to {end} "
                f"(extra_dims={extra_dims} separate={separate_report} omit_ad_units={omit_ad_units})"
            )
            # ── Global concurrency guard: max 2 live fetches at a time ──────
            # Prevents multiple concurrent large DataFrames from exhausting
            # the Render free-tier 512 MB RAM limit.
            async with _get_live_fetch_semaphore():
                job_id = await asyncio.to_thread(self.run_report, start, end, extra_dims, separate_report, omit_ad_units)
                await self.wait_for_report(job_id)
                df = await asyncio.to_thread(self.download_report, job_id, demand_channel)

            _dedup.store(key, df)
            log.info(f"LIVE data fetched: {len(df)} rows ({start} to {end})")
            return df


    async def get_live_data_multi_day(
        self, start: date, end: date, force_refresh: bool = False,
        demand_channel: str = "all", extra_dims: List[str] = None,
        separate_report: bool = False, omit_ad_units: bool = False,
    ) -> pd.DataFrame:
        """
        Fetch data for a date range from Google Ad Manager.

        The GAM API can handle date ranges up to a full year in a single report,
        so we only split into chunks for very large ranges (> 90 days).
        Chunks are 30-day blocks fetched in parallel with concurrency limits.

        extra_dims: additional GAM dimension names (e.g. ["CHILD_NETWORK_CODE"])
        separate_report: if True, omit AD_UNIT_NAME/ID (for advertiser/country dims)
        """
        day_count = (end - start).days + 1

        # For ranges up to 90 days, fetch as a single GAM report
        if day_count <= 90:
            df = await self.get_live_data(start, end, force_refresh, demand_channel, extra_dims, separate_report, omit_ad_units)
        else:
            # For larger ranges, split into 30-day chunks and fetch in parallel
            log.info(f"Splitting {day_count}-day range into 30-day chunks")
            semaphore = asyncio.Semaphore(MAX_PARALLEL)
            chunks = []
            current = start
            while current <= end:
                chunk_end = min(current + timedelta(days=29), end)
                chunks.append((current, chunk_end))
                current = chunk_end + timedelta(days=1)

            log.info(f"Created {len(chunks)} chunks for parallel fetch")

            async def fetch_chunk(s: date, e: date, retries: int = 3) -> pd.DataFrame:
                for attempt in range(retries):
                    try:
                        async with semaphore:
                            return await self.get_live_data(s, e, force_refresh, demand_channel, extra_dims, separate_report, omit_ad_units)
                    except Exception as e_in:
                        if attempt == retries - 1:
                            log.error(f"Chunk {s} to {e} failed after {retries} attempts: {e_in}")
                            raise e_in
                        log.warning(f"Chunk {s} to {e} failed (attempt {attempt+1}/{retries}). Retrying... Error: {e_in}")
                        await asyncio.sleep(2 ** attempt)

            results = await asyncio.gather(
                *(fetch_chunk(s, e) for s, e in chunks),
                return_exceptions=False
            )

            dfs = list(results)
            if not dfs:
                raise RuntimeError("All GAM report chunks failed")

            df = pd.concat(dfs, ignore_index=True)
            log.info(f"Combined {len(dfs)} chunks: {len(df)} total rows")

        return df

    # ── Phase 2: Enterprise Inventory Intelligence Methods ───────────────────
    def get_ad_units(
        self,
        limit: int = 500,
        name_filter: str = None,
        parent_id: str = None,
        active_only: bool = True
    ) -> List[Dict[str, Any]]:
        """Fetch Ad Units from InventoryService."""
        inv_service = self.client.GetService("InventoryService", version=API_VERSION)
        sb = ad_manager.StatementBuilder(version=API_VERSION)
        conditions = []
        if active_only:
            conditions.append("status = :status")
            sb.WithBindVariable("status", "ACTIVE")
        if name_filter:
            conditions.append("name LIKE :name")
            sb.WithBindVariable("name", f"%{name_filter}%")
        if parent_id:
            conditions.append("parentId = :pid")
            sb.WithBindVariable("pid", str(parent_id))
        if conditions:
            sb.Where(" AND ".join(conditions))
        sb.Limit(int(limit))
        res = inv_service.getAdUnitsByStatement(sb.ToStatement())
        results = []
        for au in getattr(res, "results", []):
            sizes = [f"{getattr(s, 'size', {}).width}x{getattr(s, 'size', {}).height}" for s in getattr(au, "adUnitSizes", []) if getattr(s, "size", None)]
            results.append({
                "id": str(getattr(au, "id", "")),
                "name": str(getattr(au, "name", "")),
                "ad_unit_code": str(getattr(au, "adUnitCode", "")),
                "parent_id": str(getattr(au, "parentId", "")) if getattr(au, "parentId", None) else None,
                "status": str(getattr(au, "status", "")),
                "target_window": str(getattr(au, "targetWindow", "")),
                "sizes": sizes,
                "has_children": bool(getattr(au, "hasChildren", False)),
            })
        return results

    def get_placements(
        self,
        limit: int = 500,
        name_filter: str = None,
        active_only: bool = True
    ) -> List[Dict[str, Any]]:
        """Fetch Placements from PlacementService."""
        place_service = self.client.GetService("PlacementService", version=API_VERSION)
        sb = ad_manager.StatementBuilder(version=API_VERSION)
        conditions = []
        if active_only:
            conditions.append("status = :status")
            sb.WithBindVariable("status", "ACTIVE")
        if name_filter:
            conditions.append("name LIKE :name")
            sb.WithBindVariable("name", f"%{name_filter}%")
        if conditions:
            sb.Where(" AND ".join(conditions))
        sb.Limit(int(limit))
        res = place_service.getPlacementsByStatement(sb.ToStatement())
        results = []
        for pl in getattr(res, "results", []):
            results.append({
                "id": str(getattr(pl, "id", "")),
                "name": str(getattr(pl, "name", "")),
                "description": str(getattr(pl, "description", "")) if getattr(pl, "description", None) else "",
                "status": str(getattr(pl, "status", "")),
                "targeted_ad_unit_ids": [str(x) for x in getattr(pl, "targetedAdUnitIds", [])],
            })
        return results

    def get_custom_targeting_keys(
        self,
        limit: int = 500,
        name_filter: str = None,
        active_only: bool = True
    ) -> List[Dict[str, Any]]:
        """Fetch Custom Targeting Keys from CustomTargetingService."""
        ct_service = self.client.GetService("CustomTargetingService", version=API_VERSION)
        sb = ad_manager.StatementBuilder(version=API_VERSION)
        conditions = []
        if active_only:
            conditions.append("status = :status")
            sb.WithBindVariable("status", "ACTIVE")
        if name_filter:
            conditions.append("name LIKE :name")
            sb.WithBindVariable("name", f"%{name_filter}%")
        if conditions:
            sb.Where(" AND ".join(conditions))
        sb.Limit(int(limit))
        res = ct_service.getCustomTargetingKeysByStatement(sb.ToStatement())
        results = []
        for k in getattr(res, "results", []):
            results.append({
                "id": str(getattr(k, "id", "")),
                "name": str(getattr(k, "name", "")),
                "display_name": str(getattr(k, "displayName", "")) if getattr(k, "displayName", None) else str(getattr(k, "name", "")),
                "type": str(getattr(k, "type", "")),
                "status": str(getattr(k, "status", "")),
                "reportable_type": str(getattr(k, "reportableType", "")),
            })
        return results

    # ── Phase 3: Enterprise Campaign & Delivery Intelligence Methods ─────────
    @staticmethod
    def _format_gam_dt(dt: Any) -> str:
        if not dt or not hasattr(dt, "date") or not getattr(dt, "date", None):
            return "Unlimited / None"
        d = dt.date
        return f"{getattr(d, 'year', 0):04d}-{getattr(d, 'month', 0):02d}-{getattr(d, 'day', 0):02d} {getattr(dt, 'hour', 0):02d}:{getattr(dt, 'minute', 0):02d} ({getattr(dt, 'timeZoneId', '')})"

    @staticmethod
    def _extract_raw_date(dt: Any) -> Optional[str]:
        """Extract a YYYY-MM-DD string from a GAM DateTime object, or None if unavailable.
        Used by get_delivery_progress for time-aware pacing calculations."""
        if not dt or not hasattr(dt, "date") or not getattr(dt, "date", None):
            return None
        d = dt.date
        year = getattr(d, "year", 0)
        month = getattr(d, "month", 0)
        day = getattr(d, "day", 0)
        if year and month and day:
            return f"{year:04d}-{month:02d}-{day:02d}"
        return None

    def get_orders(
        self,
        limit: int = 100,
        name_filter: str = None,
        status_filter: str = None,
        advertiser_id: str = None
    ) -> List[Dict[str, Any]]:
        """Fetch Orders from OrderService."""
        ord_service = self.client.GetService("OrderService", version=API_VERSION)
        sb = ad_manager.StatementBuilder(version=API_VERSION)
        conditions = []
        if status_filter:
            conditions.append("status = :status")
            sb.WithBindVariable("status", status_filter.upper())
        if name_filter:
            conditions.append("name LIKE :name")
            sb.WithBindVariable("name", f"%{name_filter}%")
        if advertiser_id:
            conditions.append("advertiserId = :adv_id")
            sb.WithBindVariable("adv_id", int(advertiser_id))
        if conditions:
            sb.Where(" AND ".join(conditions))
        sb.Limit(int(limit))
        res = ord_service.getOrdersByStatement(sb.ToStatement())
        results = []
        for o in getattr(res, "results", []):
            budget_obj = getattr(o, "totalBudget", None)
            budget_amt = getattr(budget_obj, "microAmount", 0) / 1000000.0 if budget_obj else 0.0
            currency = getattr(budget_obj, "currencyCode", "USD") if budget_obj else getattr(o, "currencyCode", "USD")
            results.append({
                "id": str(getattr(o, "id", "")),
                "name": str(getattr(o, "name", "")),
                "advertiser_id": str(getattr(o, "advertiserId", "")),
                "status": str(getattr(o, "status", "")),
                "total_budget": f"{budget_amt:.2f} {currency}",
                "impressions_delivered": int(getattr(o, "totalImpressionsDelivered", None) or 0),
                "clicks_delivered": int(getattr(o, "totalClicksDelivered", None) or 0),
                "viewable_impressions_delivered": int(getattr(o, "totalViewableImpressionsDelivered", None) or 0),
                "start_date_time": self._format_gam_dt(getattr(o, "startDateTime", None)),
                "end_date_time": self._format_gam_dt(getattr(o, "endDateTime", None)),
                "is_programmatic": bool(getattr(o, "isProgrammatic", False)),
            })
        return results

    def get_line_items(
        self,
        limit: int = 100,
        name_filter: str = None,
        order_id: str = None,
        status_filter: str = None,
        type_filter: str = None
    ) -> List[Dict[str, Any]]:
        """Fetch Line Items from LineItemService."""
        li_service = self.client.GetService("LineItemService", version=API_VERSION)
        sb = ad_manager.StatementBuilder(version=API_VERSION)
        conditions = []
        if status_filter:
            conditions.append("status = :status")
            sb.WithBindVariable("status", status_filter.upper())
        if name_filter:
            conditions.append("name LIKE :name")
            sb.WithBindVariable("name", f"%{name_filter}%")
        if order_id:
            conditions.append("orderId = :oid")
            sb.WithBindVariable("oid", int(order_id))
        if type_filter:
            conditions.append("lineItemType = :ltype")
            sb.WithBindVariable("ltype", type_filter.upper())
        if conditions:
            sb.Where(" AND ".join(conditions))
        sb.Limit(int(limit))
        res = li_service.getLineItemsByStatement(sb.ToStatement())
        results = []
        for li in getattr(res, "results", []):
            stats_obj = getattr(li, "stats", None)
            cpu_obj = getattr(li, "costPerUnit", None)
            cpu_amt = getattr(cpu_obj, "microAmount", 0) / 1000000.0 if cpu_obj else 0.0
            currency = getattr(cpu_obj, "currencyCode", "USD") if cpu_obj else "USD"
            budget_obj = getattr(li, "budget", None)
            budget_amt = getattr(budget_obj, "microAmount", 0) / 1000000.0 if budget_obj else 0.0
            results.append({
                "id": str(getattr(li, "id", "")),
                "name": str(getattr(li, "name", "")),
                "order_id": str(getattr(li, "orderId", "")),
                "order_name": str(getattr(li, "orderName", "")),
                "status": str(getattr(li, "status", "")),
                "line_item_type": str(getattr(li, "lineItemType", "")),
                "priority": int(getattr(li, "priority", None) or 0),
                "cost_type": str(getattr(li, "costType", "")),
                "rate": f"{cpu_amt:.2f} {currency}",
                "budget": f"{budget_amt:.2f} {currency}",
                "contracted_units_bought": int(getattr(li, "contractedUnitsBought", None) or 0),
                "impressions_delivered": int(getattr(stats_obj, "impressionsDelivered", None) or 0) if stats_obj else 0,
                "clicks_delivered": int(getattr(stats_obj, "clicksDelivered", None) or 0) if stats_obj else 0,
                "video_completions_delivered": int(getattr(stats_obj, "videoCompletionsDelivered", None) or 0) if stats_obj else 0,
                "viewable_impressions_delivered": int(getattr(stats_obj, "viewableImpressionsDelivered", None) or 0) if stats_obj else 0,
                "start_date_time": self._format_gam_dt(getattr(li, "startDateTime", None)),
                "end_date_time": self._format_gam_dt(getattr(li, "endDateTime", None)),
                # Raw ISO dates for time-aware pacing calculations in get_delivery_progress
                "start_date_raw": self._extract_raw_date(getattr(li, "startDateTime", None)),
                "end_date_raw": self._extract_raw_date(getattr(li, "endDateTime", None)),
            })
        return results

    def get_delivery_progress(
        self,
        limit: int = 50,
        order_id: str = None,
        status_filter: str = "DELIVERING"
    ) -> List[Dict[str, Any]]:
        """Compute time-aware Delivery Progress and Pacing Diagnostics for Line Items.

        Pacing is evaluated relative to how far the line item is through its flight,
        not just as a raw percentage of total goal delivered. A line item on Day 3 of
        a 30-day flight that has delivered 8% of goal is ON TRACK (expected ~10%).
        """
        line_items = self.get_line_items(limit=limit, order_id=order_id, status_filter=status_filter)
        today = date.today()
        diagnostics = []
        for li in line_items:
            contracted = li["contracted_units_bought"]
            delivered = li["impressions_delivered"]
            ltype = li["line_item_type"]
            start_raw = li.get("start_date_raw")
            end_raw = li.get("end_date_raw")

            if contracted > 0:
                delivery_pct = round((delivered / contracted) * 100.0, 2)

                # ── Time-aware pacing ─────────────────────────────────────────
                # Compute how far through the flight we are, then check if
                # actual delivery is lagging behind the expected linear rate.
                flight_elapsed_pct: Optional[float] = None
                expected_delivery_pct: Optional[float] = None
                try:
                    if start_raw and end_raw:
                        start_dt = date.fromisoformat(start_raw)
                        end_dt = date.fromisoformat(end_raw)
                        total_flight_days = max(1, (end_dt - start_dt).days + 1)
                        elapsed_days = max(0, (today - start_dt).days + 1)
                        flight_elapsed_pct = round(min(100.0, elapsed_days / total_flight_days * 100.0), 1)
                        # Linear delivery expectation: by X% through the flight, X% should be delivered
                        expected_delivery_pct = flight_elapsed_pct
                except (ValueError, TypeError, AttributeError):
                    pass  # Fall back to simple pacing if date parsing fails

                if expected_delivery_pct is not None:
                    # Time-aware: compare actual vs expected delivery at current point in flight
                    under_threshold = expected_delivery_pct * 0.85
                    over_threshold = min(110.0, expected_delivery_pct * 1.15)
                    if delivery_pct < under_threshold:
                        pacing_status = (
                            f"Under Pacing — {delivery_pct:.1f}% delivered, "
                            f"expected ≥{under_threshold:.1f}% at {flight_elapsed_pct:.1f}% through flight"
                        )
                    elif delivery_pct > over_threshold and expected_delivery_pct > 0:
                        pacing_status = (
                            f"Over Pacing — {delivery_pct:.1f}% delivered vs "
                            f"{expected_delivery_pct:.1f}% expected at this point in flight"
                        )
                    else:
                        pacing_status = (
                            f"On Track — {delivery_pct:.1f}% delivered "
                            f"({flight_elapsed_pct:.1f}% through flight)"
                        )
                else:
                    # Fallback: simple threshold pacing (no flight dates available)
                    if delivery_pct < 85.0:
                        pacing_status = "Under Pacing (< 85% of goal delivered — flight dates unavailable for time-aware check)"
                    elif delivery_pct > 110.0:
                        pacing_status = "Over Pacing (> 110% of goal delivered)"
                    else:
                        pacing_status = "On Track (Optimal Pacing)"
            else:
                delivery_pct = 100.0 if delivered > 0 else 0.0
                flight_elapsed_pct = None
                pacing_status = f"Programmatic / Share of Voice ({ltype} — no absolute unit cap)"

            diagnostics.append({
                "line_item_id": li["id"],
                "line_item_name": li["name"],
                "order_name": li["order_name"],
                "status": li["status"],
                "type": ltype,
                "priority": li["priority"],
                "rate": li["rate"],
                "contracted_units": contracted,
                "delivered_impressions": delivered,
                "delivered_clicks": li["clicks_delivered"],
                "delivery_completion_pct": f"{delivery_pct}%",
                "flight_elapsed_pct": f"{flight_elapsed_pct:.1f}%" if flight_elapsed_pct is not None else "N/A",
                "pacing_status": pacing_status,
                "flight_start": li.get("start_date_time", "N/A"),
                "flight_end": li["end_date_time"]
            })
        return diagnostics

    # ── PHASE 4: CREATIVE INTELLIGENCE ─────────────────────────────────────────

    def get_creatives(
        self,
        limit: int = 100,
        name_filter: str = None,
        advertiser_id: str = None,
        type_filter: str = None,
        size_filter: str = None
    ) -> List[Dict[str, Any]]:
        """Fetch live Google Ad Manager Creatives via CreativeService."""
        creative_service = self.client.GetService("CreativeService", version=API_VERSION)
        statement_builder = ad_manager.StatementBuilder(version=API_VERSION)

        conditions = []
        if name_filter:
            conditions.append(f"name LIKE '%{name_filter}%'")
        if advertiser_id:
            conditions.append(f"advertiserId = {int(advertiser_id)}")
        
        if conditions:
            statement_builder.Where(" AND ".join(conditions))
        statement_builder.Limit(limit)

        log.info(f"Request made: Service: \"CreativeService\" Method: \"getCreativesByStatement\" URL: \"https://ads.google.com/apis/ads/publisher/{API_VERSION}/CreativeService\"")
        response = creative_service.getCreativesByStatement(statement_builder.ToStatement())

        results = []
        for c in getattr(response, "results", []) or []:
            c_type = c.__class__.__name__
            if type_filter and type_filter.lower() not in c_type.lower():
                continue

            size_obj = getattr(c, "size", None)
            if size_obj:
                w = getattr(size_obj, "width", 0)
                h = getattr(size_obj, "height", 0)
                size_str = f"{w}x{h}"
            else:
                size_str = "Dynamic / Non-standard"

            if size_filter and size_filter.lower() not in size_str.lower():
                continue

            snippet = getattr(c, "codeSnippet", None) or getattr(c, "snippet", None) or getattr(c, "vastXmlUrl", None) or ""
            if len(snippet) > 120:
                snippet_preview = snippet[:117] + "..."
            else:
                snippet_preview = snippet

            results.append({
                "id": str(getattr(c, "id", "")),
                "name": str(getattr(c, "name", "")),
                "advertiser_id": str(getattr(c, "advertiserId", "")),
                "creative_type": c_type,
                "size": size_str,
                "preview_url": str(getattr(c, "previewUrl", "")),
                "snippet_preview": str(snippet_preview),
                "is_native_eligible": bool(getattr(c, "isNativeEligible", False)),
                "is_interstitial": bool(getattr(c, "isInterstitial", False))
            })
            if len(results) >= limit:
                break
        return results

    def get_creative_templates(
        self,
        limit: int = 50,
        name_filter: str = None,
        type_filter: str = None,
        status_filter: str = None
    ) -> List[Dict[str, Any]]:
        """Fetch Google Ad Manager Creative Templates via CreativeTemplateService."""
        template_service = self.client.GetService("CreativeTemplateService", version=API_VERSION)
        statement_builder = ad_manager.StatementBuilder(version=API_VERSION)

        conditions = []
        if name_filter:
            conditions.append(f"name LIKE '%{name_filter}%'")
        if type_filter:
            conditions.append(f"type = '{type_filter.upper()}'")
        if status_filter:
            conditions.append(f"status = '{status_filter.upper()}'")
        
        if conditions:
            statement_builder.Where(" AND ".join(conditions))
        statement_builder.Limit(limit)

        log.info(f"Request made: Service: \"CreativeTemplateService\" Method: \"getCreativeTemplatesByStatement\" URL: \"https://ads.google.com/apis/ads/publisher/{API_VERSION}/CreativeTemplateService\"")
        response = template_service.getCreativeTemplatesByStatement(statement_builder.ToStatement())

        results = []
        for ct in getattr(response, "results", []) or []:
            vars_list = getattr(ct, "variables", []) or []
            var_names = [str(getattr(v, "label", getattr(v, "uniqueName", ""))) for v in vars_list]
            results.append({
                "id": str(getattr(ct, "id", "")),
                "name": str(getattr(ct, "name", "")),
                "type": str(getattr(ct, "type", "")),
                "status": str(getattr(ct, "status", "")),
                "description": str(getattr(ct, "description", "")),
                "variable_count": len(var_names),
                "variables": var_names,
                "is_native_eligible": bool(getattr(ct, "isNativeEligible", False)),
                "is_interstitial": bool(getattr(ct, "isInterstitial", False))
            })
        return results

    def get_creative_diagnostics(
        self,
        limit: int = 100,
        advertiser_id: str = None
    ) -> Dict[str, Any]:
        """Compute Live Creative Inventory Health and Format Distribution Diagnostics."""
        creatives = self.get_creatives(limit=limit, advertiser_id=advertiser_id)
        type_counts = {}
        size_counts = {}
        missing_previews = 0
        native_eligible_count = 0
        interstitial_count = 0

        for c in creatives:
            ctype = c["creative_type"]
            type_counts[ctype] = type_counts.get(ctype, 0) + 1

            csize = c["size"]
            size_counts[csize] = size_counts.get(csize, 0) + 1

            if not c.get("preview_url"):
                missing_previews += 1
            if c.get("is_native_eligible"):
                native_eligible_count += 1
            if c.get("is_interstitial"):
                interstitial_count += 1

        top_sizes = sorted(size_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        return {
            "total_analyzed": len(creatives),
            "type_distribution": type_counts,
            "top_sizes": dict(top_sizes),
            "health_metrics": {
                "missing_preview_url_count": missing_previews,
                "native_eligible_count": native_eligible_count,
                "interstitial_count": interstitial_count
            },
            "sample_creatives": creatives[:10]
        }

    # ── PHASE 5: ADVERTISER & COMMERCIAL INTELLIGENCE ──────────────────────────

    def get_companies(
        self,
        limit: int = 100,
        name_filter: str = None,
        type_filter: str = None,
        credit_status_filter: str = None
    ) -> List[Dict[str, Any]]:
        """Fetch live Google Ad Manager Companies (Advertisers, Agencies, Ad Networks, Child Publishers)."""
        company_service = self.client.GetService("CompanyService", version=API_VERSION)
        statement_builder = ad_manager.StatementBuilder(version=API_VERSION)

        conditions = []
        if name_filter:
            conditions.append(f"name LIKE '%{name_filter}%'")
        if type_filter:
            conditions.append(f"type = '{type_filter.upper()}'")
        if credit_status_filter:
            conditions.append(f"creditStatus = '{credit_status_filter.upper()}'")
        
        if conditions:
            statement_builder.Where(" AND ".join(conditions))
        statement_builder.Limit(limit)

        log.info(f"Request made: Service: \"CompanyService\" Method: \"getCompaniesByStatement\" URL: \"https://ads.google.com/apis/ads/publisher/{API_VERSION}/CompanyService\"")
        response = company_service.getCompaniesByStatement(statement_builder.ToStatement())

        results = []
        for c in getattr(response, "results", []) or []:
            results.append({
                "id": str(getattr(c, "id", "")),
                "name": str(getattr(c, "name", "")),
                "type": str(getattr(c, "type", "")),
                "credit_status": str(getattr(c, "creditStatus", "")),
                "email": str(getattr(c, "email", "")),
                "primary_phone": str(getattr(c, "primaryPhone", "")),
                "external_id": str(getattr(c, "externalId", "")),
                "primary_contact_id": str(getattr(c, "primaryContactId", "")),
                "comment": str(getattr(c, "comment", ""))
            })
        return results

    def get_contacts(
        self,
        limit: int = 50,
        name_filter: str = None,
        company_id: str = None
    ) -> List[Dict[str, Any]]:
        """Fetch Google Ad Manager Commercial Contacts via ContactService."""
        contact_service = self.client.GetService("ContactService", version=API_VERSION)
        statement_builder = ad_manager.StatementBuilder(version=API_VERSION)

        conditions = []
        if name_filter:
            conditions.append(f"name LIKE '%{name_filter}%'")
        if company_id:
            conditions.append(f"companyId = {int(company_id)}")
        
        if conditions:
            statement_builder.Where(" AND ".join(conditions))
        statement_builder.Limit(limit)

        log.info(f"Request made: Service: \"ContactService\" Method: \"getContactsByStatement\" URL: \"https://ads.google.com/apis/ads/publisher/{API_VERSION}/ContactService\"")
        response = contact_service.getContactsByStatement(statement_builder.ToStatement())

        results = []
        for ct in getattr(response, "results", []) or []:
            results.append({
                "id": str(getattr(ct, "id", "")),
                "name": str(getattr(ct, "name", "")),
                "email": str(getattr(ct, "email", "")),
                "title": str(getattr(ct, "title", "")),
                "work_phone": str(getattr(ct, "workPhone", "")),
                "cell_phone": str(getattr(ct, "cellPhone", "")),
                "company_id": str(getattr(ct, "companyId", "")),
                "status": str(getattr(ct, "status", ""))
            })
        return results

    def get_advertiser_analytics(
        self,
        limit: int = 200
    ) -> Dict[str, Any]:
        """Compute Commercial Customer Portfolio Analytics across Advertisers and Agencies."""
        companies = self.get_companies(limit=limit)
        type_counts = {}
        credit_counts = {}
        missing_contacts = 0
        with_external_id = 0

        for c in companies:
            ctype = c["type"]
            type_counts[ctype] = type_counts.get(ctype, 0) + 1

            credit = c["credit_status"] or "UNKNOWN"
            credit_counts[credit] = credit_counts.get(credit, 0) + 1

            if not c.get("primary_contact_id") or c.get("primary_contact_id") == "0":
                missing_contacts += 1
            if c.get("external_id"):
                with_external_id += 1

        return {
            "total_companies_sampled": len(companies),
            "company_types": type_counts,
            "credit_status_breakdown": credit_counts,
            "portfolio_health": {
                "missing_primary_contact_count": missing_contacts,
                "crm_external_id_mapped_count": with_external_id
            },
            "sample_companies": companies[:10],
            # IMPORTANT: This data comes from CompanyService only.
            # It contains company types and credit status — NO live revenue or impression data.
            # For revenue rankings by advertiser, use getAdvertiserRankings instead.
            "data_source_note": (
                "Portfolio data from CompanyService only. "
                "No revenue or impression metrics are included here. "
                "Use getAdvertiserRankings for live advertiser revenue data."
            ),
        }

    def get_advertiser_rankings(
        self,
        start_date: datetime.date,
        end_date: datetime.date,
        limit: int = 20,
        metric: str = "revenue"
    ) -> Dict[str, Any]:
        """Rank Advertisers across the network by live Revenue or Impressions."""
        # Use run_report synchronously via thread in async or directly here
        df = self.get_live_data_sync(start_date, end_date, extra_dims=["ADVERTISER_NAME"], separate_report=True)
        if df.empty or "advertiser_name" not in df.columns:
            return {"date_range": f"{start_date} to {end_date}", "rankings": [], "total_network_revenue": 0.0}

        # Aggregate across dates per advertiser
        agg_cols = {}
        if "total_line_item_level_all_revenue" in df.columns:
            agg_cols["total_line_item_level_all_revenue"] = "sum"
        if "total_line_item_level_impressions" in df.columns:
            agg_cols["total_line_item_level_impressions"] = "sum"
        if "total_line_item_level_clicks" in df.columns:
            agg_cols["total_line_item_level_clicks"] = "sum"

        grouped = df.groupby("advertiser_name", as_index=False).agg(agg_cols)
        
        total_rev = grouped["total_line_item_level_all_revenue"].sum() if "total_line_item_level_all_revenue" in grouped.columns else 0.0
        total_imp = grouped["total_line_item_level_impressions"].sum() if "total_line_item_level_impressions" in grouped.columns else 0

        sort_col = "total_line_item_level_all_revenue" if metric.lower() == "revenue" else "total_line_item_level_impressions"
        if sort_col in grouped.columns:
            grouped = grouped.sort_values(by=sort_col, ascending=False)

        rankings = []
        for rank, row in enumerate(grouped.head(limit).to_dict("records"), 1):
            rev = float(row.get("total_line_item_level_all_revenue", 0.0))
            imp = int(row.get("total_line_item_level_impressions", 0))
            clk = int(row.get("total_line_item_level_clicks", 0))
            
            share_pct = round((rev / total_rev * 100.0), 2) if total_rev > 0 else 0.0
            ecpm = round((rev / imp * 1000.0), 2) if imp > 0 else 0.0
            ctr = round((clk / imp * 100.0), 2) if imp > 0 else 0.0

            rankings.append({
                "rank": rank,
                "advertiser_name": str(row["advertiser_name"]),
                "revenue": round(rev, 2),
                "impressions": imp,
                "clicks": clk,
                "share_of_network_revenue_pct": f"{share_pct}%",
                "ecpm": round(ecpm, 2),
                "ctr_pct": f"{ctr}%"
            })

        return {
            "date_range": f"{start_date} to {end_date}",
            "metric_sorted": metric,
            "total_network_revenue": round(total_rev, 2),
            "total_network_impressions": total_imp,
            "rankings": rankings
        }

    def get_live_data_sync(
        self,
        start_date: datetime.date,
        end_date: datetime.date,
        force_refresh: bool = False,
        demand_channel: str = "all",
        extra_dims: List[str] = None,
        separate_report: bool = False,
        omit_ad_units: bool = False,
    ) -> pd.DataFrame:
        """Synchronous wrapper for get_live_data for internal ranking aggregations."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        if loop.is_running():
            # If already running in loop, call run_report directly
            csv_path = self.run_report(start_date, end_date, extra_dims=extra_dims, separate_report=separate_report, omit_ad_units=omit_ad_units)
            df = pd.read_csv(csv_path, compression='gzip')
            df.columns = [c.lower() for c in df.columns]
            return df
        else:
            return loop.run_until_complete(self.get_live_data(start_date, end_date, force_refresh=force_refresh, demand_channel=demand_channel, extra_dims=extra_dims, separate_report=separate_report, omit_ad_units=omit_ad_units))

    # ── PHASE 6: YIELD & PROGRAMMATIC INTELLIGENCE ─────────────────────────────

    def get_yield_groups(
        self,
        limit: int = 50,
        name_filter: str = None,
        type_filter: str = None,
        format_filter: str = None
    ) -> List[Dict[str, Any]]:
        """Fetch Open Bidding and Mediation Yield Groups via YieldGroupService."""
        yg_service = self.client.GetService("YieldGroupService", version=API_VERSION)
        statement_builder = ad_manager.StatementBuilder(version=API_VERSION)

        conditions = []
        if name_filter:
            conditions.append(f"yieldGroupName LIKE '%{name_filter}%'")
        if format_filter:
            conditions.append(f"format = '{format_filter.upper()}'")
        
        if conditions:
            statement_builder.Where(" AND ".join(conditions))
        statement_builder.Limit(limit)

        log.info(f"Request made: Service: \"YieldGroupService\" Method: \"getYieldGroupsByStatement\" URL: \"https://ads.google.com/apis/ads/publisher/{API_VERSION}/YieldGroupService\"")
        response = yg_service.getYieldGroupsByStatement(statement_builder.ToStatement())

        results = []
        for yg in getattr(response, "results", []) or []:
            ad_sources = []
            for src in getattr(yg, "adSources", []) or []:
                disp = getattr(src, "displaySettings", {}) or {}
                int_type = getattr(disp, "yieldIntegrationType", "UNKNOWN")
                if type_filter and type_filter.upper() not in str(int_type).upper():
                    continue
                ad_sources.append({
                    "ad_source_id": str(getattr(src, "adSourceId", "")),
                    "company_id": str(getattr(src, "companyId", "")),
                    "integration_type": str(int_type),
                    "status": str(getattr(src, "status", ""))
                })

            if type_filter and not ad_sources:
                continue

            results.append({
                "id": str(getattr(yg, "yieldGroupId", "")),
                "name": str(getattr(yg, "yieldGroupName", "")),
                "status": str(getattr(yg, "exchangeStatus", "")),
                "format": str(getattr(yg, "format", "")),
                "environment_type": str(getattr(yg, "environmentType", "")),
                "ad_sources_count": len(ad_sources),
                "ad_sources": ad_sources
            })
        return results

    def get_pricing_rules(
        self,
        limit: int = 50,
        name_filter: str = None,
        status_filter: str = None
    ) -> List[Dict[str, Any]]:
        """Fetch Unified Pricing Rules and Ad Rules via AdRuleService."""
        rule_service = self.client.GetService("AdRuleService", version=API_VERSION)
        statement_builder = ad_manager.StatementBuilder(version=API_VERSION)

        conditions = []
        if name_filter:
            conditions.append(f"name LIKE '%{name_filter}%'")
        if status_filter:
            conditions.append(f"status = '{status_filter.upper()}'")
        
        if conditions:
            statement_builder.Where(" AND ".join(conditions))
        statement_builder.Limit(limit)

        log.info(f"Request made: Service: \"AdRuleService\" Method: \"getAdRulesByStatement\" URL: \"https://ads.google.com/apis/ads/publisher/{API_VERSION}/AdRuleService\"")
        response = rule_service.getAdRulesByStatement(statement_builder.ToStatement())

        results = []
        for r in getattr(response, "results", []) or []:
            start_dt = getattr(r, "startDateTime", None)
            start_str = f"{start_dt.date.year}-{start_dt.date.month:02d}-{start_dt.date.day:02d}" if start_dt and getattr(start_dt, "date", None) else ""
            results.append({
                "id": str(getattr(r, "id", "")),
                "name": str(getattr(r, "name", "")),
                "priority": getattr(r, "priority", 0),
                "status": str(getattr(r, "status", "")),
                "frequency_cap_behavior": str(getattr(r, "frequencyCapBehavior", "")),
                "start_date": start_str
            })
        return results

    def get_programmatic_deals(
        self,
        limit: int = 50,
        name_filter: str = None,
        deal_type: str = None,
        status_filter: str = None
    ) -> List[Dict[str, Any]]:
        """Fetch Programmatic Guaranteed, Preferred Deals, and Private Auctions via ProposalLineItemService."""
        pli_service = self.client.GetService("ProposalLineItemService", version=API_VERSION)
        statement_builder = ad_manager.StatementBuilder(version=API_VERSION)

        conditions = []
        if name_filter:
            conditions.append(f"name LIKE '%{name_filter}%'")
        if deal_type:
            conditions.append(f"lineItemType = '{deal_type.upper()}'")
        if status_filter:
            conditions.append(f"computedStatus = '{status_filter.upper()}'")
        
        if conditions:
            statement_builder.Where(" AND ".join(conditions))
        statement_builder.Limit(limit)

        log.info(f"Request made: Service: \"ProposalLineItemService\" Method: \"getProposalLineItemsByStatement\" URL: \"https://ads.google.com/apis/ads/publisher/{API_VERSION}/ProposalLineItemService\"")
        response = pli_service.getProposalLineItemsByStatement(statement_builder.ToStatement())

        results = []
        for pli in getattr(response, "results", []) or []:
            results.append({
                "id": str(getattr(pli, "id", "")),
                "proposal_id": str(getattr(pli, "proposalId", "")),
                "name": str(getattr(pli, "name", "")),
                "deal_type": str(getattr(pli, "lineItemType", "")),
                "rate_type": str(getattr(pli, "rateType", "")),
                "net_rate": getattr(getattr(pli, "netRate", None), "microAmount", 0) / 1_000_000 if getattr(pli, "netRate", None) else 0.0,
                "contracted_units": getattr(pli, "contractedUnitsBought", 0),
                "computed_status": str(getattr(pli, "computedStatus", "")),
                "reservation_status": str(getattr(pli, "reservationStatus", "")),
                "supply_path": str(getattr(pli, "supplyPath", ""))
            })
        return results

    def get_yield_analytics(
        self,
        start_date: datetime.date,
        end_date: datetime.date,
        breakdown: str = "demand_channel"
    ) -> Dict[str, Any]:
        """Analyze Monetization and Yield across Demand Channels, Yield Groups, or Programmatic Channels."""
        dim_map = {
            "demand_channel": "DEMAND_CHANNEL_NAME",
            "yield_group": "YIELD_GROUP_NAME",
            "programmatic_channel": "PROGRAMMATIC_CHANNEL_NAME"
        }
        dim = dim_map.get(breakdown.lower(), "DEMAND_CHANNEL_NAME")
        col_name = dim.lower()

        df = self.get_live_data_sync(start_date, end_date, extra_dims=[dim], separate_report=True)
        if df.empty or col_name not in df.columns:
            return {"date_range": f"{start_date} to {end_date}", "breakdown": breakdown, "results": [], "total_network_revenue": 0.0}

        agg_cols = {}
        if "total_line_item_level_all_revenue" in df.columns:
            agg_cols["total_line_item_level_all_revenue"] = "sum"
        if "total_line_item_level_impressions" in df.columns:
            agg_cols["total_line_item_level_impressions"] = "sum"

        grouped = df.groupby(col_name, as_index=False).agg(agg_cols)
        
        total_rev = grouped["total_line_item_level_all_revenue"].sum() if "total_line_item_level_all_revenue" in grouped.columns else 0.0
        total_imp = grouped["total_line_item_level_impressions"].sum() if "total_line_item_level_impressions" in grouped.columns else 0

        if "total_line_item_level_all_revenue" in grouped.columns:
            grouped = grouped.sort_values(by="total_line_item_level_all_revenue", ascending=False)

        results = []
        for row in grouped.to_dict("records"):
            rev = float(row.get("total_line_item_level_all_revenue", 0.0))
            imp = int(row.get("total_line_item_level_impressions", 0))
            share_pct = round((rev / total_rev * 100.0), 2) if total_rev > 0 else 0.0
            ecpm = round((rev / imp * 1000.0), 2) if imp > 0 else 0.0

            results.append({
                "channel_or_group": str(row[col_name]),
                "revenue": round(rev, 2),
                "impressions": imp,
                "share_of_monetization_pct": f"{share_pct}%",
                "ecpm": round(ecpm, 2)
            })

        return {
            "date_range": f"{start_date} to {end_date}",
            "breakdown_dimension": breakdown,
            "total_network_revenue": round(float(total_rev), 2),
            "total_network_impressions": int(total_imp),
            "results": results
        }

    # ── PHASE 7: FORECASTING & OPTIMIZATION INTELLIGENCE ───────────────────────

    def get_inventory_availability_forecast(
        self,
        ad_unit_id: str,
        units: int = 100000,  # renamed from target_impressions to match server.py call site
        days: int = 7
    ) -> Dict[str, Any]:
        """Predict inventory availability and capacity for a target ad unit via ForecastService."""
        forecast_service = self.client.GetService("ForecastService", version=API_VERSION)

        # Use UTC to be timezone-agnostic across all publishers
        now = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=2)
        end = now + timedelta(days=int(days))

        prospective_line_item = {
            "lineItem": {
                "lineItemType": "STANDARD",
                "costType": "CPM",
                "priority": 8,
                "startDateTimeType": "USE_START_DATE_TIME",
                "startDateTime": {
                    "date": {"year": now.year, "month": now.month, "day": now.day},
                    "hour": 0, "minute": 0, "second": 0,
                    "timeZoneId": "America/New_York"  # GAM requires a named IANA timezone — use a stable universal one
                },
                "endDateTime": {
                    "date": {"year": end.year, "month": end.month, "day": end.day},
                    "hour": 23, "minute": 59, "second": 59,
                    "timeZoneId": "America/New_York"
                },
                "primaryGoal": {
                    "goalType": "LIFETIME",
                    "unitType": "IMPRESSIONS",
                    "units": int(units)
                },
                "targeting": {
                    "inventoryTargeting": {
                        "targetedAdUnits": [{"adUnitId": str(ad_unit_id), "includeDescendants": True}]
                    }
                }
            }
        }

        log.info(f"Request made: Service: \"ForecastService\" Method: \"getAvailabilityForecast\" URL: \"https://ads.google.com/apis/ads/publisher/{API_VERSION}/ForecastService\"")
        res = forecast_service.getAvailabilityForecast(prospective_line_item, {})

        avail = int(getattr(res, "availableUnits", 0))
        matched = int(getattr(res, "matchedUnits", 0))
        possible = int(getattr(res, "possibleUnits", 0))
        reserved = int(getattr(res, "reservedUnits", 0))

        avail_pct = round((avail / matched * 100.0), 2) if matched > 0 else 0.0
        is_available = avail >= units
        overbooking = units > avail

        return {
            "ad_unit_id": str(ad_unit_id),
            "forecast_period_days": int(days),
            "target_impressions": int(units),
            "available_impressions": avail,
            "matched_impressions": matched,
            "possible_impressions": possible,
            "reserved_impressions": reserved,
            "availability_rate_pct": f"{avail_pct}%",
            "is_available": is_available,
            "overbooking_detected": overbooking,
            "recommendation": "Sufficient inventory capacity to fulfill target campaign." if is_available else f"High risk of under-delivery or overbooking. Short by {units - avail:,} impressions."
        }

    def get_line_item_delivery_forecast(
        self,
        line_item_id: int
    ) -> Dict[str, Any]:
        """Predict delivery progress and under-delivery risk for an existing line item."""
        li_service = self.client.GetService("LineItemService", version=API_VERSION)
        sb = ad_manager.StatementBuilder(version=API_VERSION).Where(f"id = {line_item_id}")
        
        log.info(f"Request made: Service: \"LineItemService\" Method: \"getLineItemsByStatement\" URL: \"https://ads.google.com/apis/ads/publisher/{API_VERSION}/LineItemService\"")
        lis = li_service.getLineItemsByStatement(sb.ToStatement())
        results = getattr(lis, "results", []) or []
        if not results:
            raise ValueError(f"Line item ID {line_item_id} not found in network.")
        
        li = results[0]
        li_name = str(getattr(li, "name", ""))
        li_type = str(getattr(li, "lineItemType", ""))
        status = str(getattr(li, "status", ""))
        stats = getattr(li, "stats", {}) or {}
        delivered = int(getattr(stats, "impressionsDelivered", 0))
        clicks = int(getattr(stats, "clicksDelivered", 0))

        goal = getattr(li, "primaryGoal", {}) or {}
        goal_units = int(getattr(goal, "units", 0)) if goal else 0

        forecast_data = {}
        if li_type in ("STANDARD", "SPONSORSHIP") and status in ("DELIVERING", "READY", "PAUSED"):
            try:
                f_service = self.client.GetService("ForecastService", version=API_VERSION)
                log.info(f"Request made: Service: \"ForecastService\" Method: \"getDeliveryForecastByIds\" URL: \"https://ads.google.com/apis/ads/publisher/{API_VERSION}/ForecastService\"")
                df_res = f_service.getDeliveryForecastByIds([line_item_id], {})
                f_list = getattr(df_res, "lineItemDeliveryForecasts", []) or []
                if f_list:
                    pred = int(getattr(f_list[0], "predictedDeliveryUnits", 0))
                    forecast_data["predicted_delivery_units"] = pred
                    forecast_data["under_delivery_risk"] = pred < goal_units if goal_units > 0 else False
            except Exception as e:
                log.warning(f"Could not retrieve SOAP delivery forecast for {line_item_id}: {e}")

        under_risk = forecast_data.get("under_delivery_risk", False)
        if goal_units > 0 and delivered < (goal_units * 0.5) and status == "DELIVERING":
            under_risk = True

        return {
            "line_item_id": str(line_item_id),
            "name": li_name,
            "line_item_type": li_type,
            "status": status,
            "delivered_impressions": delivered,
            "delivered_clicks": clicks,
            "goal_units": goal_units if goal_units > 0 else "Unlimited / Dynamic",
            "predicted_delivery_units": forecast_data.get("predicted_delivery_units", "N/A (Dynamic/Non-guaranteed)" if goal_units <= 0 else delivered),
            "under_delivery_risk": under_risk,
            "overbooking_detected": False,
            "recommendation": "Delivery is on track." if not under_risk else "High under-delivery risk detected. Recommend relaxing targeting or increasing line item priority."
        }

    def get_capacity_planning_report(
        self,
        limit: int = 10
    ) -> Dict[str, Any]:
        """Analyze network-wide inventory capacity across top ad units over a 30-day projection horizon."""
        # Bug 5 fix: use a 7-day baseline (ending 2 days ago) for more stable daily averages
        end_d = date.today() - timedelta(days=2)
        start_d = end_d - timedelta(days=6)  # 7 days inclusive

        df = self.get_live_data_sync(start_d, end_d, extra_dims=["AD_UNIT_NAME"], separate_report=False)
        if df.empty or "ad_unit_name" not in df.columns:
            return {"projection_horizon_days": 30, "ad_units_analyzed": 0, "capacity_breakdown": []}

        agg_cols = {}
        if "total_line_item_level_impressions" in df.columns:
            agg_cols["total_line_item_level_impressions"] = "sum"
        if "total_line_item_level_all_revenue" in df.columns:
            agg_cols["total_line_item_level_all_revenue"] = "sum"

        grouped = df.groupby("ad_unit_name", as_index=False).agg(agg_cols)
        if "total_line_item_level_impressions" in grouped.columns:
            grouped = grouped.sort_values(by="total_line_item_level_impressions", ascending=False).head(int(limit))

        results = []
        total_proj_imp = 0
        for row in grouped.to_dict("records"):
            imp_7d = int(row.get("total_line_item_level_impressions", 0))
            rev_7d = float(row.get("total_line_item_level_all_revenue", 0.0))
            daily_avg_imp = int(imp_7d / 7.0)
            proj_30d_imp = daily_avg_imp * 30
            total_proj_imp += proj_30d_imp

            ecpm = round((rev_7d / imp_7d * 1000.0), 2) if imp_7d > 0 else 0.0

            status = "HIGH_CAPACITY" if proj_30d_imp > 1_000_000 else ("MODERATE_CAPACITY" if proj_30d_imp > 100_000 else "CONSTRAINED")

            results.append({
                "ad_unit_name": str(row["ad_unit_name"]),
                "daily_average_impressions": daily_avg_imp,
                "projected_30d_impressions": proj_30d_imp,
                "projected_30d_revenue_at_current_ecpm": round((proj_30d_imp / 1000.0) * ecpm, 2),
                "current_ecpm": ecpm,
                "capacity_status": status
            })

        return {
            "projection_horizon_days": 30,
            "historical_baseline_days": 7,
            "total_projected_30d_network_impressions": int(total_proj_imp),
            "capacity_breakdown": results
        }

    def get_monetization_opportunity_analysis(
        self,
        min_unfilled_rate_pct: float = 20.0,
        limit: int = 10
    ) -> Dict[str, Any]:
        """Identify revenue optimization and yield improvement opportunities across network ad units."""
        # Bug 5 fix: use a 7-day baseline (ending 2 days ago) for more stable opportunity detection
        end_d = date.today() - timedelta(days=2)
        start_d = end_d - timedelta(days=6)  # 7 days inclusive
        
        df = self.get_live_data_sync(start_d, end_d, extra_dims=["AD_UNIT_NAME"], separate_report=False)
        if df.empty or "ad_unit_name" not in df.columns:
            return {"opportunities_found": 0, "estimated_total_monthly_revenue_uplift": 0.0, "opportunities": []}

        agg_cols = {}
        if "total_line_item_level_impressions" in df.columns:
            agg_cols["total_line_item_level_impressions"] = "sum"
        if "total_line_item_level_all_revenue" in df.columns:
            agg_cols["total_line_item_level_all_revenue"] = "sum"

        grouped = df.groupby("ad_unit_name", as_index=False).agg(agg_cols)
        
        total_net_rev = grouped["total_line_item_level_all_revenue"].sum() if "total_line_item_level_all_revenue" in grouped.columns else 0.0
        total_net_imp = grouped["total_line_item_level_impressions"].sum() if "total_line_item_level_impressions" in grouped.columns else 0
        net_avg_ecpm = (total_net_rev / total_net_imp * 1000.0) if total_net_imp > 0 else 1.0

        if "total_line_item_level_impressions" in grouped.columns:
            grouped = grouped.sort_values(by="total_line_item_level_impressions", ascending=False)

        opportunities = []
        total_uplift = 0.0
        for row in grouped.to_dict("records"):
            if len(opportunities) >= int(limit):
                break
            imp = int(row.get("total_line_item_level_impressions", 0))
            rev = float(row.get("total_line_item_level_all_revenue", 0.0))
            if imp < 10_000:
                continue
            
            ecpm = (rev / imp * 1000.0) if imp > 0 else 0.0
            if ecpm < (net_avg_ecpm * 0.75):
                monthly_imp = int((imp / 3.0) * 30)
                potential_rev = (monthly_imp / 1000.0) * net_avg_ecpm
                current_monthly_rev = (monthly_imp / 1000.0) * ecpm
                uplift = max(0.0, potential_rev - current_monthly_rev)
                total_uplift += uplift

                opportunities.append({
                    "ad_unit_name": str(row["ad_unit_name"]),
                    "impressions_3d": imp,
                    "current_ecpm": round(ecpm, 2),
                    "network_benchmark_ecpm": round(net_avg_ecpm, 2),
                    "estimated_monthly_revenue_uplift": round(uplift, 2),
                    "optimization_action": f"eCPM ($ {round(ecpm, 2)}) is 25%+ below network benchmark ($ {round(net_avg_ecpm, 2)}). Recommend enabling Open Bidding demand sources or reviewing Unified Pricing Rule floor prices."
                })

        return {
            "network_average_ecpm": round(float(net_avg_ecpm), 2),
            "opportunities_found": len(opportunities),
            "estimated_total_monthly_revenue_uplift": round(float(total_uplift), 2),
            "opportunities": opportunities
        }

    # ─── PHASE 8: AUDIENCE & TRAFFIC INTELLIGENCE ─────────────────────────────

    def get_audience_geography(self, start_date: date, end_date: date, level: str = "country", limit: int = 25) -> List[Dict[str, Any]]:
        """
        Analyze audience geographical distribution by country, state (region), or city.
        """
        level_clean = level.lower().strip()
        dim_map = {
            "country": "COUNTRY_NAME",
            "state": "REGION_NAME",
            "region": "REGION_NAME",
            "city": "CITY_NAME"
        }
        target_dim = dim_map.get(level_clean, "COUNTRY_NAME")
        df = self.get_live_data_sync(start_date, end_date, extra_dims=[target_dim], separate_report=True)

        if df.empty:
            log.warning("[live_data_unavailable] GAM returned no data for %s geography report (%s to %s)", level_clean, start_date, end_date)
            return [{"_live_data_status": "unavailable", "_message": f"I couldn't retrieve live data for this. Google Ad Manager returned no {level_clean} geography data for the requested period ({start_date} to {end_date}). This is not an estimate — no real numbers are available."}]
        if target_dim.lower() not in df.columns:
            log.warning("[dimension_missing] '%s' not in GAM geography response columns", target_dim)
            return [{"_live_data_status": "unavailable", "_message": f"The '{level_clean}' geographic dimension was not included in the GAM report response for this period. Live data unavailable — no numbers can be provided."}]

        grouped = df.groupby(target_dim.lower(), as_index=False).agg({
            "total_line_item_level_impressions": "sum",
            "total_line_item_level_clicks": "sum",
            "total_line_item_level_cpm_and_cpc_revenue": "sum"
        })
        grouped = grouped.sort_values(by="total_line_item_level_impressions", ascending=False)

        total_imp = float(grouped["total_line_item_level_impressions"].sum())
        results = []
        for _, row in grouped.head(limit).iterrows():
            imp = int(row["total_line_item_level_impressions"])
            clk = int(row["total_line_item_level_clicks"])
            rev = float(row["total_line_item_level_cpm_and_cpc_revenue"])
            ecpm = (rev / imp * 1000.0) if imp > 0 else 0.0
            ctr = (clk / imp * 100.0) if imp > 0 else 0.0
            share_pct = (imp / total_imp * 100.0) if total_imp > 0 else 0.0
            results.append({
                level_clean: str(row[target_dim.lower()]),
                "impressions": imp,
                "clicks": clk,
                "cpm_cpc_revenue": round(rev, 2),
                "ecpm": round(ecpm, 2),
                "ctr_pct": round(ctr, 4),
                "impression_share_pct": round(share_pct, 2)
            })
        return results

    def get_audience_technology(self, start_date: date, end_date: date, dimension: str = "device", limit: int = 25) -> List[Dict[str, Any]]:
        """
        Analyze audience technology breakdown by device category, browser, or operating system.
        """
        dim_clean = dimension.lower().strip()
        dim_map = {
            "device": "DEVICE_CATEGORY_NAME",
            "device_category": "DEVICE_CATEGORY_NAME",
            "browser": "BROWSER_NAME",
            "operating_system": "OPERATING_SYSTEM_NAME",
            "os": "OPERATING_SYSTEM_NAME"
        }
        target_dim = dim_map.get(dim_clean, "DEVICE_CATEGORY_NAME")
        df = self.get_live_data_sync(start_date, end_date, extra_dims=[target_dim], separate_report=True)

        if df.empty:
            log.warning("[live_data_unavailable] GAM returned no data for %s technology report (%s to %s)", dim_clean, start_date, end_date)
            return [{"_live_data_status": "unavailable", "_message": f"I couldn't retrieve live data for this. Google Ad Manager returned no {dim_clean} technology breakdown data for the requested period ({start_date} to {end_date}). This is not an estimate — no real numbers are available."}]
        if target_dim.lower() not in df.columns:
            log.warning("[dimension_missing] '%s' not in GAM technology response columns", target_dim)
            return [{"_live_data_status": "unavailable", "_message": f"The '{dim_clean}' technology dimension was not included in the GAM report response for this period. Live data unavailable — no numbers can be provided."}]

        grouped = df.groupby(target_dim.lower(), as_index=False).agg({
            "total_line_item_level_impressions": "sum",
            "total_line_item_level_clicks": "sum",
            "total_line_item_level_cpm_and_cpc_revenue": "sum"
        })
        grouped = grouped.sort_values(by="total_line_item_level_impressions", ascending=False)

        total_imp = float(grouped["total_line_item_level_impressions"].sum())
        results = []
        for _, row in grouped.head(limit).iterrows():
            imp = int(row["total_line_item_level_impressions"])
            clk = int(row["total_line_item_level_clicks"])
            rev = float(row["total_line_item_level_cpm_and_cpc_revenue"])
            ecpm = (rev / imp * 1000.0) if imp > 0 else 0.0
            ctr = (clk / imp * 100.0) if imp > 0 else 0.0
            share_pct = (imp / total_imp * 100.0) if total_imp > 0 else 0.0
            results.append({
                dim_clean: str(row[target_dim.lower()]),
                "impressions": imp,
                "clicks": clk,
                "cpm_cpc_revenue": round(rev, 2),
                "ecpm": round(ecpm, 2),
                "ctr_pct": round(ctr, 4),
                "impression_share_pct": round(share_pct, 2)
            })
        return results

    def get_mobile_app_traffic(self, start_date: date, end_date: date, limit: int = 25) -> List[Dict[str, Any]]:
        """
        Analyze traffic and monetization across mobile apps.
        """
        df = self.get_live_data_sync(start_date, end_date, extra_dims=["MOBILE_APP_NAME"], separate_report=True)

        if df.empty:
            log.warning("[live_data_unavailable] GAM returned no data for mobile app traffic report (%s to %s)", start_date, end_date)
            return [{"_live_data_status": "unavailable", "_message": f"I couldn't retrieve live data for this. Google Ad Manager returned no mobile app traffic data for the requested period ({start_date} to {end_date}). This is not an estimate — no real numbers are available."}]
        if "mobile_app_name" not in df.columns:
            log.warning("[dimension_missing] 'MOBILE_APP_NAME' not in GAM mobile app response columns")
            return [{"_live_data_status": "unavailable", "_message": "The mobile app name dimension was not included in the GAM report response for this period. Live data unavailable — no numbers can be provided."}]

        grouped = df.groupby("mobile_app_name", as_index=False).agg({
            "total_line_item_level_impressions": "sum",
            "total_line_item_level_clicks": "sum",
            "total_line_item_level_cpm_and_cpc_revenue": "sum"
        })
        grouped = grouped.sort_values(by="total_line_item_level_impressions", ascending=False)

        total_imp = float(grouped["total_line_item_level_impressions"].sum())
        results = []
        for _, row in grouped.head(limit).iterrows():
            imp = int(row["total_line_item_level_impressions"])
            clk = int(row["total_line_item_level_clicks"])
            rev = float(row["total_line_item_level_cpm_and_cpc_revenue"])
            ecpm = (rev / imp * 1000.0) if imp > 0 else 0.0
            ctr = (clk / imp * 100.0) if imp > 0 else 0.0
            share_pct = (imp / total_imp * 100.0) if total_imp > 0 else 0.0
            results.append({
                "mobile_app_name": str(row["mobile_app_name"]),
                "impressions": imp,
                "clicks": clk,
                "cpm_cpc_revenue": round(rev, 2),
                "ecpm": round(ecpm, 2),
                "ctr_pct": round(ctr, 4),
                "impression_share_pct": round(share_pct, 2)
            })
        return results

    def get_traffic_sources(self, start_date: date, end_date: date, source_type: str = "domain", limit: int = 25) -> List[Dict[str, Any]]:
        """
        Analyze traffic sources by domain, referrer URL, or traffic source channel.
        """
        src_clean = source_type.lower().strip()
        dim_map = {
            "domain": "DOMAIN",
            "referrer": "REFERER_URL",
            "referer": "REFERER_URL",
            "source": "TRAFFIC_SOURCE_NAME",
            "traffic_source": "TRAFFIC_SOURCE_NAME"
        }
        target_dim = dim_map.get(src_clean, "DOMAIN")
        df = self.get_live_data_sync(start_date, end_date, extra_dims=[target_dim], separate_report=True)

        if df.empty:
            log.warning("[live_data_unavailable] GAM returned no data for %s traffic source report (%s to %s)", src_clean, start_date, end_date)
            return [{"_live_data_status": "unavailable", "_message": f"I couldn't retrieve live data for this. Google Ad Manager returned no {src_clean} traffic source data for the requested period ({start_date} to {end_date}). This is not an estimate — no real numbers are available."}]
        if target_dim.lower() not in df.columns:
            log.warning("[dimension_missing] '%s' not in GAM traffic source response columns", target_dim)
            return [{"_live_data_status": "unavailable", "_message": f"The '{src_clean}' traffic source dimension was not included in the GAM report response for this period. Live data unavailable — no numbers can be provided."}]

        grouped = df.groupby(target_dim.lower(), as_index=False).agg({
            "total_line_item_level_impressions": "sum",
            "total_line_item_level_clicks": "sum",
            "total_line_item_level_cpm_and_cpc_revenue": "sum"
        })
        grouped = grouped.sort_values(by="total_line_item_level_impressions", ascending=False)

        total_imp = float(grouped["total_line_item_level_impressions"].sum())
        results = []
        for _, row in grouped.head(limit).iterrows():
            imp = int(row["total_line_item_level_impressions"])
            clk = int(row["total_line_item_level_clicks"])
            rev = float(row["total_line_item_level_cpm_and_cpc_revenue"])
            ecpm = (rev / imp * 1000.0) if imp > 0 else 0.0
            ctr = (clk / imp * 100.0) if imp > 0 else 0.0
            share_pct = (imp / total_imp * 100.0) if total_imp > 0 else 0.0
            results.append({
                src_clean: str(row[target_dim.lower()]),
                "impressions": imp,
                "clicks": clk,
                "cpm_cpc_revenue": round(rev, 2),
                "ecpm": round(ecpm, 2),
                "ctr_pct": round(ctr, 4),
                "impression_share_pct": round(share_pct, 2)
            })
        return results

    # ─── PHASE 9: NETWORK INTELLIGENCE ────────────────────────────────────────

    def get_network_metadata(self) -> Dict[str, Any]:
        """
        Retrieve live network configuration, properties, timezone, currency, and root ad unit from GAM.
        """
        from zeep.helpers import serialize_object
        srv = self.client.GetService("NetworkService", version=API_VERSION)
        net = serialize_object(srv.getCurrentNetwork())
        return {
            "network_id": str(net.get("id", "")),
            "network_code": str(net.get("networkCode", "")),
            "display_name": str(net.get("displayName", "")),
            "property_code": str(net.get("propertyCode", "")),
            "time_zone": str(net.get("timeZone", "")),
            "currency_code": str(net.get("currencyCode", "")),
            "secondary_currency_codes": list(net.get("secondaryCurrencyCodes", []) or []),
            "effective_root_ad_unit_id": str(net.get("effectiveRootAdUnitId", "")),
            "is_test": bool(net.get("isTest", False))
        }

    def get_network_summary(self, start_date: date, end_date: date, include_insights: bool = True) -> Dict[str, Any]:
        """
        Analyze high-level network health, core KPIs, fill rate, eCPM, and automatic insights.
        """
        from mcp_server.services.network_analytics import compute_network_summary, compute_anomalies_from_df, compute_automatic_insights
        df = self.get_live_data_sync(start_date, end_date, force_refresh=True, demand_channel="all")
        summary = compute_network_summary(df, self.network_code, start_date, end_date)
        if include_insights:
            anomalies = compute_anomalies_from_df(df)
            insights = compute_automatic_insights(summary)
            summary["anomalies"] = anomalies[:8]
            summary["insights"] = insights
        return summary

    def get_child_network_analytics(self, start_date: date, end_date: date, metric: str = "revenue", limit: int = 15, filter_network: str = "") -> Dict[str, Any]:
        """
        Analyze monetization and performance across child publishers and MCM partners.
        """
        from mcp_server.services.network_analytics import compute_child_network_analytics
        try:
            df = self.get_live_data_sync(start_date, end_date, force_refresh=True, demand_channel="all", extra_dims=["CHILD_NETWORK_CODE"], omit_ad_units=True)
        except Exception:
            df = self.get_live_data_sync(start_date, end_date, force_refresh=True, demand_channel="all")
        return compute_child_network_analytics(df, start_date, end_date, metric=metric, limit=limit, filter_network=filter_network)

    def get_match_rate_analytics(self, start_date: date, end_date: date, dimension: str = "device", limit: int = 15) -> Dict[str, Any]:
        """
        Analyze ad request fill rates and match rates broken down by dimension.
        """
        from mcp_server.services.network_analytics import compute_match_rate_analytics
        dim_map = {
            "device": "DEVICE_CATEGORY_NAME",
            "country": "COUNTRY_NAME",
            "browser": "BROWSER_NAME",
            "app": "MOBILE_APP_NAME",
            "domain": "DOMAIN",
            "ad_unit": "AD_UNIT_NAME"
        }
        target_dim = dim_map.get(dimension.lower().strip(), "DEVICE_CATEGORY_NAME")
        try:
            df = self.get_live_data_sync(start_date, end_date, force_refresh=True, demand_channel="all", extra_dims=[target_dim], omit_ad_units=True)
        except Exception:
            df = self.get_live_data_sync(start_date, end_date, force_refresh=True, demand_channel="all")
        return compute_match_rate_analytics(df, dimension, start_date, end_date, limit=limit)

    # ── PHASE 10: TARGETING & RULES INTELLIGENCE ─────────────────────────────

    def get_labels(
        self,
        limit: int = 100,
        name_filter: str = None,
        active_only: bool = True,
    ) -> Dict[str, Any]:
        """Fetch Labels (Competitive Exclusions, Roadblocks, Frequency Caps) from LabelService."""
        label_service = self.client.GetService("LabelService", version=API_VERSION)
        sb = ad_manager.StatementBuilder(version=API_VERSION)
        conditions: List[str] = []
        if active_only:
            conditions.append("isActive = :active")
            sb.WithBindVariable("active", True)
        if name_filter:
            conditions.append("name LIKE :name")
            sb.WithBindVariable("name", f"%{name_filter}%")
        if conditions:
            sb.Where(" AND ".join(conditions))
        sb.Limit(int(limit))
        res = label_service.getLabelsByStatement(sb.ToStatement())
        results = []
        for lbl in getattr(res, "results", []):
            types_list = []
            raw_types = getattr(lbl, "types", None) or []
            if isinstance(raw_types, str):
                raw_types = [raw_types]
            for t in raw_types:
                types_list.append(str(t))
            results.append({
                "id": str(getattr(lbl, "id", "")),
                "name": str(getattr(lbl, "name", "")),
                "description": str(getattr(lbl, "description", "") or ""),
                "is_active": bool(getattr(lbl, "isActive", True)),
                "types": types_list,
            })
        # Summarise label types
        type_counts: Dict[str, int] = {}
        for r in results:
            for t in r["types"]:
                type_counts[t] = type_counts.get(t, 0) + 1
        return {
            "total_labels": len(results),
            "active_only": active_only,
            "type_summary": type_counts,
            "labels": results,
        }

    def get_custom_targeting(
        self,
        key_filter: str = None,
        value_filter: str = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """Fetch Custom Targeting Keys and their Values (enriched view) from CustomTargetingService."""
        ct_service = self.client.GetService("CustomTargetingService", version=API_VERSION)
        import zeep

        # ── Keys ──────────────────────────────────────────────────────────────
        key_sb = ad_manager.StatementBuilder(version=API_VERSION)
        key_conditions: List[str] = ["status = :status"]
        key_sb.WithBindVariable("status", "ACTIVE")
        if key_filter:
            key_conditions.append("name LIKE :kname")
            key_sb.WithBindVariable("kname", f"%{key_filter}%")
        key_sb.Where(" AND ".join(key_conditions)).Limit(int(limit))
        key_res = ct_service.getCustomTargetingKeysByStatement(key_sb.ToStatement())
        keys: List[Dict[str, Any]] = []
        key_id_map: Dict[str, str] = {}
        for k in getattr(key_res, "results", []) or []:
            kd = zeep.helpers.serialize_object(k)
            kid = str(kd.get("id", ""))
            kname = str(kd.get("name", ""))
            key_id_map[kid] = kname
            keys.append({
                "id": kid,
                "name": kname,
                "display_name": str(kd.get("displayName") or kname),
                "type": str(kd.get("type", "")),
                "status": str(kd.get("status", "")),
                "reportable_type": str(kd.get("reportableType", "")),
            })

        # ── Values ────────────────────────────────────────────────────────────
        val_sb = ad_manager.StatementBuilder(version=API_VERSION)
        val_conditions: List[str] = ["status = :vstatus"]
        val_sb.WithBindVariable("vstatus", "ACTIVE")
        if value_filter:
            val_conditions.append("name LIKE :vname")
            val_sb.WithBindVariable("vname", f"%{value_filter}%")
        val_sb.Where(" AND ".join(val_conditions)).Limit(int(limit) * 10)
        val_res = ct_service.getCustomTargetingValuesByStatement(val_sb.ToStatement())
        # Group values by key
        values_by_key: Dict[str, List[Dict[str, Any]]] = {}
        for v in getattr(val_res, "results", []) or []:
            vd = zeep.helpers.serialize_object(v)
            key_id = str(vd.get("customTargetingKeyId", ""))
            values_by_key.setdefault(key_id, []).append({
                "id": str(vd.get("id", "")),
                "name": str(vd.get("name", "")),
                "display_name": str(vd.get("displayName") or vd.get("name", "")),
                "match_type": str(vd.get("matchType", "")),
                "status": str(vd.get("status", "")),
            })

        # Enrich keys with their values
        enriched: List[Dict[str, Any]] = []
        for k in keys:
            k["values"] = values_by_key.get(k["id"], [])
            k["value_count"] = len(k["values"])
            enriched.append(k)

        total_values = sum(len(v) for v in values_by_key.values())
        return {
            "total_keys": len(enriched),
            "total_values_fetched": total_values,
            "keys": enriched,
        }

    def get_ad_rules(
        self,
        limit: int = 50,
        name_filter: str = None,
        active_only: bool = True,
    ) -> Dict[str, Any]:
        """Fetch Ad Rules (Frequency Caps, Roadblocks, Competitive Exclusions) from AdRuleService."""
        rule_service = self.client.GetService("AdRuleService", version=API_VERSION)
        import zeep

        sb = ad_manager.StatementBuilder(version=API_VERSION)
        conditions: List[str] = []
        if active_only:
            conditions.append("status = :status")
            sb.WithBindVariable("status", "ACTIVE")
        if name_filter:
            conditions.append("name LIKE :name")
            sb.WithBindVariable("name", f"%{name_filter}%")
        if conditions:
            sb.Where(" AND ".join(conditions))
        sb.Limit(int(limit))
        res = rule_service.getAdRulesByStatement(sb.ToStatement())

        results: List[Dict[str, Any]] = []
        for rule in getattr(res, "results", []) or []:
            rd = zeep.helpers.serialize_object(rule)
            # Frequency cap details
            freq_cap = rd.get("frequencyCaps") or {}
            if isinstance(freq_cap, list):
                freq_cap = freq_cap[0] if freq_cap else {}
            # Targeting summary
            targeting = rd.get("targeting") or {}
            geo_targeting = targeting.get("geoTargeting") or {}
            device_targeting = targeting.get("technologyTargeting") or {}
            inventory_targeting = targeting.get("inventoryTargeting") or {}
            results.append({
                "id": str(rd.get("id", "")),
                "name": str(rd.get("name", "") or ""),
                "status": str(rd.get("status", "")),
                "priority": rd.get("priority"),
                "start_date": str(rd.get("startDate") or ""),
                "end_date": str(rd.get("endDate") or ""),
                "frequency_cap": {
                    "max_impressions": freq_cap.get("maxImpressions") if isinstance(freq_cap, dict) else None,
                    "time_unit": str(freq_cap.get("timeUnit", "") if isinstance(freq_cap, dict) else ""),
                    "time_length": freq_cap.get("timeLength") if isinstance(freq_cap, dict) else None,
                },
                "has_geo_targeting": bool(geo_targeting),
                "has_device_targeting": bool(device_targeting),
                "has_inventory_targeting": bool(inventory_targeting),
            })

        active_count = sum(1 for r in results if r["status"] == "ACTIVE")
        return {
            "total_rules": len(results),
            "active_rules": active_count,
            "rules": results,
        }

    # ── PHASE 11: EXECUTIVE AI INTELLIGENCE ──────────────────────────────────

    def get_kpi_health_score(
        self,
        start_date: date,
        end_date: date,
    ) -> Dict[str, Any]:
        """
        Compute a composite KPI Health Score across all key metrics.
        Returns a 0–100 health score with per-dimension scores and action items.
        """
        from mcp_server.services.network_analytics import (
            compute_network_health, _pct, _ecpm, _ctr,
        )

        df = self.get_live_data_sync(start_date, end_date, force_refresh=True)
        if df.empty:
            return {"error": "No data for the requested period.", "period": f"{start_date} to {end_date}"}

        rev    = float(df["ad_server_cpm_and_cpc_revenue"].sum())
        imp    = int(df["ad_server_impressions"].sum())
        clicks = int(df.get("ad_server_clicks", df.get("total_line_item_level_clicks", 0)).sum()) if "ad_server_clicks" in df.columns else 0
        req    = 0
        for col in ["canonical_ad_requests", "total_ad_requests", "ad_server_ad_requests"]:
            if col in df.columns:
                v = int(df[col].sum())
                if v > 0:
                    req = v
                    break

        matched = 0
        for col in ["matched_requests", "total_responses_served"]:
            if col in df.columns:
                v = int(df[col].sum())
                if v > 0:
                    matched = v
                    break

        fill_rate  = _pct(imp, req)
        match_rate = _pct(matched, req)
        ecpm_val   = _ecpm(rev, imp)
        ctr_val    = _ctr(clicks, imp)

        health = compute_network_health({
            "fill_rate": fill_rate, "match_rate": match_rate,
            "revenue": rev, "impressions": imp, "ad_requests": req,
        })

        # Per-KPI scoring (0–100 each)
        def _score_fill(fr: float) -> int:
            if fr >= 85: return 100
            if fr >= 70: return 80
            if fr >= 50: return 60
            if fr >= 30: return 40
            if fr >= 10: return 20
            return 0

        def _score_ecpm(e: float) -> int:
            if e >= 2.0: return 100
            if e >= 1.0: return 80
            if e >= 0.5: return 60
            if e >= 0.1: return 40
            if e > 0:    return 20
            return 0

        def _score_ctr(c: float) -> int:
            if 0.5 <= c <= 3.0:  return 100
            if 0.2 <= c < 0.5:   return 70
            if 3.0 < c <= 8.0:   return 60
            if c > 8.0:          return 30
            return 20

        def _score_rev(r: float) -> int:
            if r >= 5000:  return 100
            if r >= 1000:  return 80
            if r >= 500:   return 60
            if r >= 100:   return 40
            if r > 0:      return 20
            return 0

        scores = {
            "fill_rate":  _score_fill(fill_rate),
            "ecpm":       _score_ecpm(ecpm_val),
            "ctr":        _score_ctr(ctr_val),
            "revenue":    _score_rev(rev),
        }
        composite = round(sum(scores.values()) / len(scores))

        # Action items
        actions: List[str] = []
        if fill_rate < 50:
            actions.append("Fill rate is low — increase demand partner competition or lower floor prices.")
        if ecpm_val < 0.5:
            actions.append("eCPM is weak — review floor pricing rules and enable Open Bidding.")
        if ctr_val > 8.0:
            actions.append("CTR is unusually high — check for invalid traffic or bot activity.")
        if ctr_val < 0.2 and imp > 10000:
            actions.append("CTR is very low — review creative quality and ad placement.")
        if rev == 0 and imp > 100:
            actions.append("Revenue is zero despite impressions — verify demand channel configuration.")
        if not actions:
            actions.append("Network KPIs are within healthy ranges. Continue monitoring.")

        return {
            "period": f"{start_date} to {end_date}",
            "composite_health_score": composite,
            "health_grade": (
                "A" if composite >= 85 else
                "B" if composite >= 70 else
                "C" if composite >= 55 else
                "D" if composite >= 40 else "F"
            ),
            "network_health_status": health["health_status"],
            "kpi_scores": scores,
            "metrics": {
                "revenue_usd": round(rev, 2),
                "impressions": imp,
                "clicks": clicks,
                "ad_requests": req,
                "fill_rate_pct": fill_rate,
                "match_rate_pct": match_rate,
                "ecpm_usd": ecpm_val,
                "ctr_pct": ctr_val,
            },
            "action_items": actions,
        }

    def get_executive_briefing(
        self,
        start_date: date,
        end_date: date,
        compare_days: int = 7,
    ) -> Dict[str, Any]:
        """
        Generate a full executive briefing with period-over-period comparison,
        anomalies, top performers, and strategic recommendations.
        """
        from mcp_server.services.network_analytics import (
            _pct, _ecpm, _ctr, _detect_entity_anomalies,
        )

        # Current period
        df = self.get_live_data_sync(start_date, end_date, force_refresh=True)
        # Comparison period
        comp_end   = start_date - timedelta(days=1)
        comp_start = comp_end - timedelta(days=compare_days - 1)
        try:
            df_prev = self.get_live_data_sync(comp_start, comp_end, force_refresh=True)
        except Exception:
            df_prev = None

        def _summarise(frame) -> Dict[str, Any]:
            if frame is None or frame.empty:
                return {"revenue": 0, "impressions": 0, "clicks": 0,
                        "fill_rate": 0, "ecpm": 0, "ctr": 0, "requests": 0, "match_rate": 0}
            rev  = float(frame["ad_server_cpm_and_cpc_revenue"].sum())
            imp  = int(frame["ad_server_impressions"].sum())
            clks = int(frame["ad_server_clicks"].sum()) if "ad_server_clicks" in frame.columns else 0
            req  = 0
            for col in ["canonical_ad_requests", "total_ad_requests", "ad_server_ad_requests"]:
                if col in frame.columns:
                    v = int(frame[col].sum())
                    if v > 0: req = v; break
            matched = 0
            for col in ["matched_requests", "total_responses_served", "programmatic_responses_served"]:
                if col in frame.columns:
                    v = int(frame[col].sum())
                    if v > 0: matched = v; break
            return {
                "revenue": round(rev, 2),
                "impressions": imp,
                "clicks": clks,
                "requests": req,
                "fill_rate": _pct(imp, req),
                "ecpm": _ecpm(rev, imp),
                "ctr": _ctr(clks, imp),
                "match_rate": _pct(matched, req),
            }

        curr = _summarise(df)
        prev = _summarise(df_prev)

        def _chg(c, p) -> float:
            if p == 0: return 0.0
            return round((c - p) / p * 100, 1)

        changes = {k: _chg(curr[k], prev[k]) for k in curr}

        # Top performers (by ad unit / app)
        top_performers: List[Dict] = []
        if not df.empty and "ad_unit_name" in df.columns:
            grp = df.groupby("ad_unit_name", as_index=False).agg(
                revenue=("ad_server_cpm_and_cpc_revenue", "sum"),
                impressions=("ad_server_impressions", "sum"),
            ).sort_values("revenue", ascending=False).head(5)
            for _, row in grp.iterrows():
                top_performers.append({
                    "name": str(row["ad_unit_name"]),
                    "revenue_usd": round(float(row["revenue"]), 2),
                    "impressions": int(row["impressions"]),
                })

        # Anomalies
        anomalies = _detect_entity_anomalies(
            {"revenue_usd": curr["revenue"], "impressions": curr["impressions"],
             "fill_rate_pct": curr["fill_rate"], "match_rate_pct": curr.get("match_rate", 0),
             "ctr_pct": curr["ctr"], "ad_requests": curr["requests"]},
            label="Network"
        )

        # Recommendations
        recs: List[str] = []
        if changes.get("revenue", 0) < -10:
            recs.append("Revenue declined significantly — investigate top performers for delivery issues.")
        if curr["fill_rate"] < 50:
            recs.append("Fill rate below 50% — increase bid density via Open Bidding or UPRs.")
        if curr["ecpm"] < 0.5:
            recs.append("eCPM below $0.50 — review floor pricing and programmatic demand.")
        if curr["ctr"] > 8.0:
            recs.append("CTR is unusually high — flag for IVT review.")
        if not recs:
            recs.append("Network performance is stable. Maintain current optimizations.")

        return {
            "period": f"{start_date} to {end_date}",
            "comparison_period": f"{comp_start} to {comp_end}",
            "current_period": curr,
            "previous_period": prev,
            "period_over_period_change_pct": changes,
            "top_performers": top_performers,
            "anomalies": anomalies,
            "strategic_recommendations": recs,
            "briefing_generated_at": str(date.today()),
        }

    def get_anomaly_report(
        self,
        start_date: date,
        end_date: date,
    ) -> Dict[str, Any]:
        """
        Deep anomaly detection across revenue, fill rate, CTR, and traffic.
        Scans each ad unit/app individually and flags issues.
        """
        from mcp_server.services.network_analytics import (
            _pct, _ecpm, _ctr, _detect_entity_anomalies,
        )

        df = self.get_live_data_sync(start_date, end_date, force_refresh=True)
        if df.empty:
            return {"error": "No data for the requested period.", "anomalies": []}

        all_anomalies: List[Dict] = []
        entity_col = "ad_unit_name" if "ad_unit_name" in df.columns else None

        if entity_col:
            for name, grp in df.groupby(entity_col):
                rev  = float(grp["ad_server_cpm_and_cpc_revenue"].sum())
                imp  = int(grp["ad_server_impressions"].sum())
                clks = int(grp["ad_server_clicks"].sum()) if "ad_server_clicks" in grp.columns else 0
                req  = 0
                for col in ["canonical_ad_requests", "total_ad_requests", "ad_server_ad_requests"]:
                    if col in grp.columns:
                        v = int(grp[col].sum())
                        if v > 0: req = v; break
                entity_metrics = {
                    "revenue_usd": rev, "impressions": imp,
                    "fill_rate_pct": _pct(imp, req),
                    "match_rate_pct": 0, "ctr_pct": _ctr(clks, imp),
                    "ad_requests": req,
                }
                detected = _detect_entity_anomalies(entity_metrics, label=str(name))
                all_anomalies.extend(detected)

        # Network-wide anomalies
        rev_total  = float(df["ad_server_cpm_and_cpc_revenue"].sum())
        imp_total  = int(df["ad_server_impressions"].sum())
        clk_total  = int(df["ad_server_clicks"].sum()) if "ad_server_clicks" in df.columns else 0
        req_total  = 0
        for col in ["canonical_ad_requests", "total_ad_requests", "ad_server_ad_requests"]:
            if col in df.columns:
                v = int(df[col].sum())
                if v > 0: req_total = v; break

        network_anomalies = _detect_entity_anomalies({
            "revenue_usd": rev_total, "impressions": imp_total,
            "fill_rate_pct": _pct(imp_total, req_total),
            "match_rate_pct": 0, "ctr_pct": _ctr(clk_total, imp_total),
            "ad_requests": req_total,
        }, label="Network-wide")
        all_anomalies = network_anomalies + all_anomalies

        critical = [a for a in all_anomalies if a.get("severity") == "critical"]
        warnings = [a for a in all_anomalies if a.get("severity") == "warning"]

        return {
            "period": f"{start_date} to {end_date}",
            "total_anomalies": len(all_anomalies),
            "critical_count": len(critical),
            "warning_count": len(warnings),
            "critical_anomalies": critical[:10],
            "warning_anomalies": warnings[:15],
            "summary": (
                f"{len(critical)} critical issue(s) and {len(warnings)} warning(s) detected."
                if all_anomalies else "No anomalies detected. Network is operating normally."
            ),
        }

    def get_optimization_opportunities(
        self,
        start_date: date,
        end_date: date,
    ) -> Dict[str, Any]:
        """
        AI-powered optimization opportunity scan across fill rate, eCPM, CTR,
        and revenue. Returns prioritised action items for the revenue team.
        """
        from mcp_server.services.network_analytics import _pct, _ecpm, _ctr

        df = self.get_live_data_sync(start_date, end_date, force_refresh=True)
        if df.empty:
            return {"error": "No data for the requested period.", "opportunities": []}

        opportunities: List[Dict] = []

        rev_total = float(df["ad_server_cpm_and_cpc_revenue"].sum())
        imp_total = int(df["ad_server_impressions"].sum())
        clk_total = int(df["ad_server_clicks"].sum()) if "ad_server_clicks" in df.columns else 0
        req_total = 0
        for col in ["canonical_ad_requests", "total_ad_requests", "ad_server_ad_requests"]:
            if col in df.columns:
                v = int(df[col].sum())
                if v > 0: req_total = v; break

        fill_rate = _pct(imp_total, req_total)
        ecpm_val  = _ecpm(rev_total, imp_total)
        ctr_val   = _ctr(clk_total, imp_total)
        unfilled  = req_total - imp_total if req_total > imp_total else 0

        # Opportunity: Low fill rate
        if fill_rate < 70 and req_total > 1000:
            estimated_rev = unfilled * ecpm_val / 1000 if ecpm_val > 0 else 0
            opportunities.append({
                "category": "Fill Rate",
                "priority": "High",
                "title": f"Fill Rate is {fill_rate:.1f}% — {unfilled:,} requests unfilled",
                "impact_estimate_usd": round(estimated_rev, 2),
                "recommendation": "Enable additional demand partners via Open Bidding. Lower floor prices on low-competition inventory.",
                "kpi_affected": ["fill_rate", "revenue", "impressions"],
            })

        # Opportunity: Low eCPM
        if ecpm_val < 0.5 and imp_total > 1000:
            opportunities.append({
                "category": "eCPM / Pricing",
                "priority": "High",
                "title": f"eCPM is only ${ecpm_val:.3f} — below market average",
                "impact_estimate_usd": None,
                "recommendation": "Review Unified Pricing Rules. Increase price floor on premium placements (Native, Rewarded). Enable header bidding.",
                "kpi_affected": ["ecpm", "revenue"],
            })

        # Opportunity: Low CTR
        if ctr_val < 0.3 and imp_total > 5000:
            opportunities.append({
                "category": "Creative / Placement",
                "priority": "Medium",
                "title": f"CTR is {ctr_val:.2f}% — user engagement is very low",
                "impact_estimate_usd": None,
                "recommendation": "Review ad placements for viewability. Refresh creative assets. A/B test placement positions.",
                "kpi_affected": ["ctr", "clicks"],
            })

        # Opportunity: Revenue below potential
        if rev_total < 100 and imp_total > 10000:
            opportunities.append({
                "category": "Monetization",
                "priority": "High",
                "title": f"High impressions ({imp_total:,}) but revenue is only ${rev_total:.2f}",
                "impact_estimate_usd": None,
                "recommendation": "Large impression volume not being fully monetized. Check demand channel configuration and Ad Exchange integration.",
                "kpi_affected": ["revenue", "ecpm"],
            })

        # Opportunity: High CTR (potential IVT)
        if ctr_val > 8.0 and imp_total > 1000:
            opportunities.append({
                "category": "Traffic Quality",
                "priority": "Critical",
                "title": f"CTR is {ctr_val:.1f}% — possible invalid traffic",
                "impact_estimate_usd": None,
                "recommendation": "Review for IVT using Google Ad Manager's Invalid Traffic report. Consider enabling Click Fraud detection.",
                "kpi_affected": ["ctr", "revenue"],
            })

        if not opportunities:
            opportunities.append({
                "category": "General",
                "priority": "Low",
                "title": "Network KPIs are within healthy ranges",
                "impact_estimate_usd": 0,
                "recommendation": "Continue monitoring. Consider scaling well-performing inventory segments.",
                "kpi_affected": [],
            })

        return {
            "period": f"{start_date} to {end_date}",
            "total_opportunities": len(opportunities),
            "opportunities": sorted(
                opportunities,
                key=lambda x: {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}.get(x["priority"], 4)
            ),
            "summary_metrics": {
                "revenue_usd": round(rev_total, 2),
                "impressions": imp_total,
                "fill_rate_pct": fill_rate,
                "ecpm_usd": ecpm_val,
                "ctr_pct": ctr_val,
                "unfilled_requests": unfilled,
            },
        }


    # ── GAP A: LINE ITEM CREATIVE ASSOCIATIONS (LICA) ─────────────────────────

    def get_line_item_creative_associations(
        self,
        limit: int = 200,
        line_item_id: str = None,
        creative_id: str = None,
        status_filter: str = None,
    ) -> Dict[str, Any]:
        """Fetch Line Item – Creative Associations (LICAs) from LineItemCreativeAssociationService.

        Answers questions like:
        - Which line items have creatives attached?
        - Which creatives are associated with which campaigns?
        - Are there active line items with no creative associations?
        """
        lica_service = self.client.GetService(
            "LineItemCreativeAssociationService", version=API_VERSION
        )
        sb = ad_manager.StatementBuilder(version=API_VERSION)
        conditions: List[str] = []
        if line_item_id:
            conditions.append("lineItemId = :liid")
            sb.WithBindVariable("liid", int(line_item_id))
        if creative_id:
            conditions.append("creativeId = :cid")
            sb.WithBindVariable("cid", int(creative_id))
        if status_filter:
            conditions.append("status = :st")
            sb.WithBindVariable("st", status_filter.upper())
        else:
            # Default: only active associations
            conditions.append("status = :st")
            sb.WithBindVariable("st", "ACTIVE")
        if conditions:
            sb.Where(" AND ".join(conditions))
        sb.Limit(int(limit))

        log.info(
            "Request made: Service: \"LineItemCreativeAssociationService\" "
            "Method: \"getLineItemCreativeAssociationsByStatement\" "
            "URL: \"https://ads.google.com/apis/ads/publisher/%s/LineItemCreativeAssociationService\"",
            API_VERSION,
        )
        res = lica_service.getLineItemCreativeAssociationsByStatement(sb.ToStatement())

        associations: List[Dict[str, Any]] = []
        for lica in getattr(res, "results", []) or []:
            start_dt_obj = getattr(lica, "startDateTime", None)
            end_dt_obj = getattr(lica, "endDateTime", None)
            associations.append({
                "line_item_id": str(getattr(lica, "lineItemId", "")),
                "creative_id": str(getattr(lica, "creativeId", "")),
                "creative_set_id": str(getattr(lica, "creativeSetId", "") or ""),
                "status": str(getattr(lica, "status", "")),
                "start_date_time": self._format_gam_dt(start_dt_obj),
                "end_date_time": self._format_gam_dt(end_dt_obj),
                "destination_url": str(getattr(lica, "destinationUrl", "") or ""),
                "rotation_type": str(getattr(lica, "rotation", {}).rotationType if hasattr(getattr(lica, "rotation", None) or {}, "rotationType") else ""),
            })

        # Build per-line-item summary: how many creatives per line item
        li_creative_count: Dict[str, int] = {}
        for a in associations:
            li_id = a["line_item_id"]
            li_creative_count[li_id] = li_creative_count.get(li_id, 0) + 1

        return {
            "total_associations": len(associations),
            "unique_line_items": len(li_creative_count),
            "unique_creatives": len({a["creative_id"] for a in associations}),
            "associations": associations,
            "creatives_per_line_item": [
                {"line_item_id": li_id, "creative_count": cnt}
                for li_id, cnt in sorted(li_creative_count.items(), key=lambda x: x[1])
            ],
        }

    def get_orphan_line_items(
        self,
        limit: int = 100,
        status_filter: str = "DELIVERING",
    ) -> Dict[str, Any]:
        """Find active line items that have NO creative associations.

        Answers: 'Which line items are running without creatives attached?'
        Cross-joins LineItemService with LineItemCreativeAssociationService.
        All computation is done in Python — the LLM receives the pre-computed result.
        """
        # Fetch delivering line items
        line_items = self.get_line_items(limit=limit, status_filter=status_filter)
        if not line_items:
            return {
                "_live_data_status": "unavailable",
                "_message": (
                    "I couldn't retrieve live data for this. "
                    "Google Ad Manager returned no line items with status "
                    f"'{status_filter}'. Cannot determine orphan status."
                ),
                "orphan_line_items": [],
            }

        # Fetch LICA records for those line items
        all_li_ids = {li["id"] for li in line_items}
        lica_service = self.client.GetService(
            "LineItemCreativeAssociationService", version=API_VERSION
        )
        # Fetch active associations — we only need the lineItemId column
        sb = ad_manager.StatementBuilder(version=API_VERSION)
        sb.Where("status = :st").WithBindVariable("st", "ACTIVE").Limit(2000)
        log.info(
            "Request made: Service: \"LineItemCreativeAssociationService\" "
            "Method: \"getLineItemCreativeAssociationsByStatement\" "
            "URL: \"https://ads.google.com/apis/ads/publisher/%s/LineItemCreativeAssociationService\"",
            API_VERSION,
        )
        lica_res = lica_service.getLineItemCreativeAssociationsByStatement(sb.ToStatement())
        li_ids_with_creatives: set = set()
        for lica in getattr(lica_res, "results", []) or []:
            li_ids_with_creatives.add(str(getattr(lica, "lineItemId", "")))

        # Identify orphans — delivering line items with zero creative associations
        orphans = [
            {
                "line_item_id": li["id"],
                "line_item_name": li["name"],
                "order_name": li["order_name"],
                "status": li["status"],
                "type": li["line_item_type"],
                "priority": li["priority"],
                "contracted_units": li["contracted_units_bought"],
                "delivered_impressions": li["impressions_delivered"],
                "flight_start": li.get("start_date_time", "N/A"),
                "flight_end": li.get("end_date_time", "N/A"),
                "issue": "No active creative association found — ads cannot serve",
            }
            for li in line_items
            if li["id"] not in li_ids_with_creatives
        ]

        return {
            "status_filter_used": status_filter,
            "line_items_checked": len(line_items),
            "orphan_count": len(orphans),
            "orphan_line_items": orphans,
            "summary": (
                f"{len(orphans)} line item(s) with status '{status_filter}' "
                "have no active creative associations and cannot serve ads."
                if orphans else
                f"All {len(line_items)} '{status_filter}' line items have at least one active creative."
            ),
        }

    # ── GAP B: AUDIENCE SEGMENT INTELLIGENCE ──────────────────────────────────

    def get_audience_segments(
        self,
        limit: int = 100,
        name_filter: str = None,
        type_filter: str = None,
        status_filter: str = None,
    ) -> Dict[str, Any]:
        """Fetch first-party and third-party Audience Segments from AudienceSegmentService.

        Answers questions like:
        - List all audience segments
        - Which audience segment has the most users?
        - What is the size of the Sports audience segment?
        - Show first-party vs third-party segment breakdown
        """
        import zeep
        seg_service = self.client.GetService(
            "AudienceSegmentService", version=API_VERSION
        )
        sb = ad_manager.StatementBuilder(version=API_VERSION)
        conditions: List[str] = []
        if status_filter:
            conditions.append("status = :st")
            sb.WithBindVariable("st", status_filter.upper())
        if name_filter:
            conditions.append("name LIKE :nm")
            sb.WithBindVariable("nm", f"%{name_filter}%")
        if type_filter:
            conditions.append("type = :tp")
            sb.WithBindVariable("tp", type_filter.upper())
        if conditions:
            sb.Where(" AND ".join(conditions))
        sb.Limit(int(limit))

        log.info(
            "Request made: Service: \"AudienceSegmentService\" "
            "Method: \"getAudienceSegmentsByStatement\" "
            "URL: \"https://ads.google.com/apis/ads/publisher/%s/AudienceSegmentService\"",
            API_VERSION,
        )
        res = seg_service.getAudienceSegmentsByStatement(sb.ToStatement())

        segments: List[Dict[str, Any]] = []
        for seg in getattr(res, "results", []) or []:
            sd = zeep.helpers.serialize_object(seg)
            segments.append({
                "id": str(sd.get("id", "")),
                "name": str(sd.get("name", "")),
                "description": str(sd.get("description", "") or ""),
                "status": str(sd.get("status", "")),
                "type": str(sd.get("type", "")),
                "size": int(sd.get("size", 0) or 0),
                "size_in_pixels": int(sd.get("sizeInPixels", 0) or 0),
                "data_provider_name": str(
                    (sd.get("dataProvider") or {}).get("name", "") or ""
                ),
                "category_labels": [
                    str(lbl.get("name", "")) for lbl in (sd.get("categoryLabels") or [])
                ],
            })

        if not segments:
            return {
                "_live_data_status": "unavailable",
                "_message": (
                    "I couldn't retrieve live data for this. "
                    "Google Ad Manager returned no audience segments matching the request. "
                    "This is not an estimate — no real numbers are available."
                ),
                "segments": [],
            }

        # Pandas summary — all arithmetic done here, not by the LLM
        df_segs = pd.DataFrame(segments)
        type_counts = df_segs["type"].value_counts().to_dict()
        total_reach = int(df_segs["size"].sum())
        largest_segment = df_segs.loc[df_segs["size"].idxmax(), "name"] if not df_segs.empty else "N/A"

        return {
            "total_segments": len(segments),
            "type_breakdown": type_counts,
            "total_combined_reach_users": total_reach,
            "largest_segment_by_size": largest_segment,
            "segments": sorted(segments, key=lambda x: x["size"], reverse=True),
        }

    # ── GAP C: NETWORK USERS & ROLES ──────────────────────────────────────────

    def get_network_users(
        self,
        limit: int = 100,
        name_filter: str = None,
        role_filter: str = None,
        active_only: bool = True,
    ) -> Dict[str, Any]:
        """Fetch network users and their roles from UserService.

        Answers questions like:
        - Who has admin access to my network?
        - List all users with trafficking rights
        - Which users have API access?
        - Show all active network users
        """
        import zeep
        user_service = self.client.GetService("UserService", version=API_VERSION)
        sb = ad_manager.StatementBuilder(version=API_VERSION)
        conditions: List[str] = []
        if active_only:
            conditions.append("isActive = :active")
            sb.WithBindVariable("active", True)
        if name_filter:
            conditions.append("name LIKE :nm")
            sb.WithBindVariable("nm", f"%{name_filter}%")
        if conditions:
            sb.Where(" AND ".join(conditions))
        sb.Limit(int(limit))

        log.info(
            "Request made: Service: \"UserService\" "
            "Method: \"getUsersByStatement\" "
            "URL: \"https://ads.google.com/apis/ads/publisher/%s/UserService\"",
            API_VERSION,
        )
        res = user_service.getUsersByStatement(sb.ToStatement())

        users: List[Dict[str, Any]] = []
        for u in getattr(res, "results", []) or []:
            ud = zeep.helpers.serialize_object(u)
            role_name = str(ud.get("roleName", "") or "")
            # Optional role filter (applied client-side since UserService doesn't support it in AWQL)
            if role_filter and role_filter.lower() not in role_name.lower():
                continue
            users.append({
                "id": str(ud.get("id", "")),
                "name": str(ud.get("name", "")),
                "email": str(ud.get("email", "")),
                "role_id": str(ud.get("roleId", "")),
                "role_name": role_name,
                "is_active": bool(ud.get("isActive", True)),
                "is_external": bool(ud.get("isExternallyManaged", False)),
                "preferred_locale": str(ud.get("preferredLocale", "") or ""),
            })

        if not users:
            return {
                "_live_data_status": "unavailable",
                "_message": (
                    "I couldn't retrieve live data for this. "
                    "Google Ad Manager returned no users matching the request. "
                    "Verify that the service account has UserService read permissions."
                ),
                "users": [],
            }

        # Pandas — compute role distribution, never by the LLM
        df_users = pd.DataFrame(users)
        role_counts = df_users["role_name"].value_counts().to_dict()

        return {
            "total_users": len(users),
            "active_only_filter": active_only,
            "role_breakdown": role_counts,
            "users": users,
        }

    # ── GAP D: CUSTOM TARGETING PERFORMANCE BY REPORTING DIMENSION ────────────

    def get_custom_targeting_performance(
        self,
        start_date: date,
        end_date: date,
        limit: int = 25,
    ) -> Dict[str, Any]:
        """Analyze which Custom Targeting Key-Values drive the most impressions and revenue.

        Runs a live GAM report grouped by CUSTOM_TARGETING_VALUE_ID dimension.
        All aggregation (impressions, revenue, eCPM, share %) is done in Pandas.

        Answers questions like:
        - Which custom key-values are most used?
        - What is the revenue by key-value targeting?
        - Show traffic by custom targeting
        - Top performing KV pairs by impressions or revenue
        """
        df = self.get_live_data_sync(
            start_date, end_date,
            extra_dims=["CUSTOM_TARGETING_VALUE_ID"],
            separate_report=True,
        )

        if df.empty:
            return {
                "_live_data_status": "unavailable",
                "_message": (
                    f"I couldn't retrieve live data for this. "
                    f"Google Ad Manager returned no custom targeting data for the period "
                    f"{start_date} to {end_date}. This is not an estimate — no real numbers are available."
                ),
                "results": [],
            }

        # The column name after lowercasing is "custom_targeting_value_id"
        dim_col = "custom_targeting_value_id"
        if dim_col not in df.columns:
            return {
                "_live_data_status": "unavailable",
                "_message": (
                    "The CUSTOM_TARGETING_VALUE_ID dimension was not returned by GAM for this period. "
                    "This dimension may not be enabled for your network. Live data unavailable."
                ),
                "results": [],
            }

        # Determine available metric columns
        rev_col = "total_line_item_level_all_revenue" if "total_line_item_level_all_revenue" in df.columns else "ad_server_cpm_and_cpc_revenue"
        imp_col = "total_line_item_level_impressions" if "total_line_item_level_impressions" in df.columns else "ad_server_impressions"
        clk_col = "total_line_item_level_clicks" if "total_line_item_level_clicks" in df.columns else (
            "ad_server_clicks" if "ad_server_clicks" in df.columns else None
        )

        agg_map: Dict[str, str] = {rev_col: "sum", imp_col: "sum"}
        if clk_col and clk_col in df.columns:
            agg_map[clk_col] = "sum"

        grouped = df.groupby(dim_col, as_index=False).agg(agg_map)
        grouped = grouped.sort_values(by=imp_col, ascending=False)

        total_imp = float(grouped[imp_col].sum())
        total_rev = float(grouped[rev_col].sum())

        results: List[Dict[str, Any]] = []
        for rank, row in enumerate(grouped.head(int(limit)).to_dict("records"), 1):
            imp = int(row.get(imp_col, 0))
            rev = float(row.get(rev_col, 0.0))
            clk = int(row.get(clk_col, 0)) if clk_col else 0
            ecpm = round(rev / imp * 1000.0, 2) if imp > 0 else 0.0
            ctr = round(clk / imp * 100.0, 4) if imp > 0 else 0.0
            imp_share = round(imp / total_imp * 100.0, 2) if total_imp > 0 else 0.0
            rev_share = round(rev / total_rev * 100.0, 2) if total_rev > 0 else 0.0
            results.append({
                "rank": rank,
                "custom_targeting_value_id": str(row[dim_col]),
                "impressions": imp,
                "revenue_usd": round(rev, 4),
                "clicks": clk,
                "ecpm_usd": ecpm,
                "ctr_pct": ctr,
                "impression_share_pct": imp_share,
                "revenue_share_pct": rev_share,
            })

        return {
            "date_range": f"{start_date} to {end_date}",
            "total_kv_combinations": len(grouped),
            "total_impressions": int(total_imp),
            "total_revenue_usd": round(total_rev, 2),
            "top_results_shown": len(results),
            "note": (
                "Results are grouped by CUSTOM_TARGETING_VALUE_ID. "
                "The value ID maps back to your Custom Targeting key-value definitions in GAM."
            ),
            "results": results,
        }


    # ── GAP: UNIFIED PRICING RULES (UPR) ─────────────────────────────────────
    # UnifiedPricingRuleService is the MODERN floor pricing system in GAM 360.
    # It is entirely separate from AdRuleService (legacy frequency/scheduling rules)
    # which get_pricing_rules() already calls. This tool closes the gap.

    def get_unified_pricing_rules(
        self,
        limit: int = 100,
        name_filter: str = None,
        status_filter: str = None,
    ) -> Dict[str, Any]:
        """Fetch Unified Pricing Rules (UPRs) from UnifiedPricingRuleService.

        UPRs are the modern floor pricing mechanism in Google Ad Manager 360.
        They define minimum CPM floors per inventory segment, device, geo, etc.
        This is DIFFERENT from AdRuleService (which handles legacy ad rules /
        frequency caps). The existing getPricingRules tool calls AdRuleService —
        this tool calls the correct modern service.

        Answers questions like:
        - What are my current floor prices?
        - Show me all active Unified Pricing Rules
        - What is the floor price for Mobile Banner inventory?
        - Which pricing rules target Connected TV?
        - Do I have any rules set above $X CPM?
        - Show me pricing rules by status / type
        """
        import zeep

        upr_service = self.client.GetService(
            "UnifiedPricingRuleService", version=API_VERSION
        )
        sb = ad_manager.StatementBuilder(version=API_VERSION)
        conditions: List[str] = []

        if status_filter:
            conditions.append("status = :st")
            sb.WithBindVariable("st", status_filter.upper())
        if name_filter:
            conditions.append("name LIKE :nm")
            sb.WithBindVariable("nm", f"%{name_filter}%")
        if conditions:
            sb.Where(" AND ".join(conditions))
        sb.Limit(int(limit))

        log.info(
            "Request made: Service: \"UnifiedPricingRuleService\" "
            "Method: \"getUnifiedPricingRulesByStatement\" "
            "URL: \"https://ads.google.com/apis/ads/publisher/%s/UnifiedPricingRuleService\"",
            API_VERSION,
        )
        res = upr_service.getUnifiedPricingRulesByStatement(sb.ToStatement())

        rules: List[Dict[str, Any]] = []
        for upr in getattr(res, "results", []) or []:
            raw = zeep.helpers.serialize_object(upr)

            # ── Floor price extraction ────────────────────────────────────────
            # UPR floor is a Money object: {microAmount: int, currencyCode: str}
            floor_obj = raw.get("floor") or {}
            floor_micro = int(floor_obj.get("microAmount", 0) or 0)
            floor_usd = round(floor_micro / 1_000_000, 4)
            currency = str(floor_obj.get("currencyCode", "USD") or "USD")

            # ── Targeting summary (human-readable, no math) ───────────────────
            targeting = raw.get("targeting") or {}
            targeting_summary: List[str] = []

            # Inventory targeting
            inv_tgt = targeting.get("inventoryTargeting") or {}
            targeted_units = inv_tgt.get("targetedAdUnits") or []
            if targeted_units:
                targeting_summary.append(
                    f"{len(targeted_units)} ad unit(s) targeted"
                )

            # Geo targeting
            geo_tgt = targeting.get("geoTargeting") or {}
            targeted_locs = geo_tgt.get("targetedLocations") or []
            if targeted_locs:
                loc_names = [
                    str(loc.get("displayName", loc.get("id", "?")))
                    for loc in targeted_locs[:5]
                ]
                targeting_summary.append(f"Geo: {', '.join(loc_names)}")

            # Device targeting
            device_tgt = targeting.get("deviceCategoryTargeting") or {}
            targeted_devices = device_tgt.get("targetedDeviceCategories") or []
            if targeted_devices:
                device_names = [
                    str(d.get("name", d.get("id", "?")))
                    for d in targeted_devices
                ]
                targeting_summary.append(f"Device: {', '.join(device_names)}")

            # Custom criteria (KV targeting)
            custom_tgt = targeting.get("customTargeting") or {}
            if custom_tgt:
                targeting_summary.append("Custom targeting applied")

            # Size targeting
            size_tgt = targeting.get("technologyTargeting") or {}
            if size_tgt:
                targeting_summary.append("Technology targeting applied")

            # Start / end dates
            start_dt = raw.get("startTime")
            end_dt = raw.get("endTime")
            start_str = (
                f"{start_dt['date']['year']}-{start_dt['date']['month']:02d}-{start_dt['date']['day']:02d}"
                if start_dt and start_dt.get("date") else "Always"
            )
            end_str = (
                f"{end_dt['date']['year']}-{end_dt['date']['month']:02d}-{end_dt['date']['day']:02d}"
                if end_dt and end_dt.get("date") else "No end date"
            )

            rules.append({
                "id": str(raw.get("id", "")),
                "name": str(raw.get("name", "")),
                "status": str(raw.get("status", "")),
                "pricing_rule_type": str(raw.get("pricingRuleType", "")),
                "floor_price_usd": floor_usd,
                "floor_currency": currency,
                "floor_price_formatted": f"${floor_usd:.4f} CPM ({currency})",
                "targeting_summary": (
                    "; ".join(targeting_summary) if targeting_summary
                    else "Network-wide (no specific targeting)"
                ),
                "start_date": start_str,
                "end_date": end_str,
            })

        if not rules:
            return {
                "_live_data_status": "unavailable",
                "_message": (
                    "I couldn't retrieve live data for this. "
                    "Google Ad Manager returned no Unified Pricing Rules matching the request. "
                    "Verify that the network has UPRs configured and that the service account "
                    "has UnifiedPricingRuleService read permissions. "
                    "This is not an estimate — no real numbers are available."
                ),
                "rules": [],
            }

        # ── Pandas summary — all arithmetic here, never by the LLM ──────────
        df_rules = pd.DataFrame(rules)

        status_counts = df_rules["status"].value_counts().to_dict()
        type_counts = df_rules["pricing_rule_type"].value_counts().to_dict()
        floors = df_rules["floor_price_usd"]
        floor_stats = {
            "min_floor_usd": round(float(floors.min()), 4),
            "max_floor_usd": round(float(floors.max()), 4),
            "median_floor_usd": round(float(floors.median()), 4),
            "mean_floor_usd": round(float(floors.mean()), 4),
            "rules_above_1usd": int((floors > 1.0).sum()),
            "rules_above_0_5usd": int((floors > 0.5).sum()),
            "rules_at_zero": int((floors == 0.0).sum()),
        }

        return {
            "total_rules": len(rules),
            "status_breakdown": status_counts,
            "type_breakdown": type_counts,
            "floor_price_stats": floor_stats,
            # Sorted by floor price descending so highest floors are first
            "rules": sorted(rules, key=lambda x: x["floor_price_usd"], reverse=True),
            "data_source": "UnifiedPricingRuleService (modern GAM 360 floor pricing)",
            "note": (
                "These are Unified Pricing Rules — the modern floor pricing system. "
                "For legacy Ad Rules (frequency caps, scheduling), use getPricingRules instead."
            ),
        }

    # ── GAP H1: IMPACT FORECASTING ───────────────────────────────────────────
    # The existing get_inventory_availability_forecast checks availability for a
    # prospective line item in isolation. This method adds ForecastOptions with
    # contendingLineItemIds so the response includes WHICH EXISTING CAMPAIGNS
    # would compete for inventory if the new line item is added.

    def get_impact_forecast(
        self,
        ad_unit_id: str,
        units: int = 100_000,
        days: int = 7,
        contending_line_item_ids: List[str] = None,
        line_item_type: str = "STANDARD",
        priority: int = 8,
    ) -> Dict[str, Any]:
        """Model the impact of adding a new line item on existing campaigns.

        Calls ForecastService.getAvailabilityForecast with a prospective line item
        and ForecastOptions.contendingLineItemIds. The API returns both:
        - Inventory availability for the prospective campaign
        - How much each contending existing campaign would be displaced

        Answers questions like:
        - If I add a new 100K impression campaign on ad unit X, which campaigns will be hurt?
        - Will adding this line item affect my existing guaranteed delivery?
        - What is the contention risk for ad unit Y over the next 7 days?
        - Show me the impact forecast for a new Standard line item on [ad_unit_id]

        Args:
            ad_unit_id: GAM ad unit ID to forecast for
            units: target impression goal for the prospective line item
            contending_line_item_ids: optional list of specific line item IDs to check
                impact against. If None, GAM auto-detects contending campaigns.
            line_item_type: type of prospective line item (STANDARD, SPONSORSHIP, etc.)
            priority: delivery priority (1-16, lower = higher priority)
        """
        forecast_service = self.client.GetService(
            "ForecastService", version=API_VERSION
        )

        # Start 2 days from now (GAM forecast requirement: start must be future)
        now = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=2)
        end = now + timedelta(days=int(days))

        prospective_line_item = {
            "lineItem": {
                "lineItemType": line_item_type.upper(),
                "costType": "CPM",
                "priority": int(priority),
                "startDateTimeType": "USE_START_DATE_TIME",
                "startDateTime": {
                    "date": {"year": now.year, "month": now.month, "day": now.day},
                    "hour": 0, "minute": 0, "second": 0,
                    "timeZoneId": "America/New_York",
                },
                "endDateTime": {
                    "date": {"year": end.year, "month": end.month, "day": end.day},
                    "hour": 23, "minute": 59, "second": 59,
                    "timeZoneId": "America/New_York",
                },
                "primaryGoal": {
                    "goalType": "LIFETIME",
                    "unitType": "IMPRESSIONS",
                    "units": int(units),
                },
                "targeting": {
                    "inventoryTargeting": {
                        "targetedAdUnits": [
                            {"adUnitId": str(ad_unit_id), "includeDescendants": True}
                        ]
                    }
                },
            }
        }

        # ForecastOptions — pass contending IDs if specified, else GAM auto-detects
        forecast_options: Dict[str, Any] = {}
        if contending_line_item_ids:
            forecast_options["contendingLineItemIds"] = [
                int(lid) for lid in contending_line_item_ids
                if str(lid).strip().isdigit()
            ]

        log.info(
            "Request made: Service: \"ForecastService\" "
            "Method: \"getAvailabilityForecast\" (impact mode, contendingLineItemIds=%s) "
            "URL: \"https://ads.google.com/apis/ads/publisher/%s/ForecastService\"",
            len(forecast_options.get("contendingLineItemIds", [])),
            API_VERSION,
        )
        res = forecast_service.getAvailabilityForecast(
            prospective_line_item, forecast_options
        )

        # ── Availability numbers (all Python arithmetic, not LLM) ─────────────
        avail    = int(getattr(res, "availableUnits",  0) or 0)
        matched  = int(getattr(res, "matchedUnits",    0) or 0)
        possible = int(getattr(res, "possibleUnits",   0) or 0)
        reserved = int(getattr(res, "reservedUnits",   0) or 0)
        avail_pct   = round(avail / matched * 100.0, 2) if matched > 0 else 0.0
        can_fulfill = avail >= int(units)
        shortfall   = max(0, int(units) - avail)

        # ── Contending campaigns ──────────────────────────────────────────────
        # GAM returns ContendingLineItem: lineItemId, name, contention (0–1 float)
        raw_contending = getattr(res, "contendingLineItems", []) or []
        contending_data: List[Dict[str, Any]] = []
        for cli in raw_contending:
            cli_id         = str(getattr(cli, "lineItemId", "") or "")
            cli_name       = str(getattr(cli, "name", "") or "")
            cli_contention = float(getattr(cli, "contention", 0.0) or 0.0)
            contention_pct = round(cli_contention * 100.0, 2)
            risk = (
                "HIGH"   if cli_contention > 0.30 else
                "MEDIUM" if cli_contention > 0.10 else
                "LOW"
            )
            contending_data.append({
                "line_item_id":   cli_id,
                "name":           cli_name,
                "contention_pct": contention_pct,
                "risk_level":     risk,
                "interpretation": (
                    f"This campaign shares {contention_pct:.1f}% of the same inventory. "
                    f"Adding the prospective line item may reduce its delivery."
                ),
            })

        # Pandas — sort by contention descending (never by the LLM)
        if contending_data:
            df_c = pd.DataFrame(contending_data).sort_values(
                "contention_pct", ascending=False
            )
            contending_data = df_c.to_dict("records")

        high_risk_count   = sum(1 for c in contending_data if c["risk_level"] == "HIGH")
        medium_risk_count = sum(1 for c in contending_data if c["risk_level"] == "MEDIUM")
        low_risk_count    = len(contending_data) - high_risk_count - medium_risk_count

        # ── Recommendation string (pre-computed, LLM just quotes it) ──────────
        if can_fulfill and not contending_data:
            rec = (
                f"Safe to add. Inventory is available ({avail:,} units) "
                f"and no competing campaigns were detected."
            )
        elif can_fulfill and high_risk_count == 0:
            rec = (
                f"Inventory available ({avail:,} units). "
                f"{len(contending_data)} low-to-medium risk campaign(s) detected — "
                f"monitor delivery but risk is manageable."
            )
        elif can_fulfill and high_risk_count > 0:
            rec = (
                f"Inventory available but {high_risk_count} HIGH-risk campaign(s) "
                f"compete heavily for this inventory. Adding this line item may cause "
                f"under-delivery for those campaigns. Review priority and targeting."
            )
        else:
            rec = (
                f"Insufficient inventory. Target is {int(units):,} impressions "
                f"but only {avail:,} are available (shortfall: {shortfall:,}). "
                f"Do not add without adjusting targeting, dates, or goal."
            )

        return {
            "ad_unit_id": str(ad_unit_id),
            "prospective_line_item": {
                "type":             line_item_type.upper(),
                "priority":         int(priority),
                "goal_impressions":  int(units),
                "forecast_days":     int(days),
                "start_date":        now.strftime("%Y-%m-%d"),
                "end_date":          end.strftime("%Y-%m-%d"),
            },
            "availability": {
                "available_impressions": avail,
                "matched_impressions":   matched,
                "possible_impressions":  possible,
                "reserved_impressions":  reserved,
                "availability_rate_pct": f"{avail_pct}%",
                "can_fulfill":           can_fulfill,
                "shortfall":             shortfall,
            },
            "contending_campaigns": {
                "total_contending":  len(contending_data),
                "high_risk_count":   high_risk_count,
                "medium_risk_count": medium_risk_count,
                "low_risk_count":    low_risk_count,
                "campaigns":         contending_data,
            },
            "recommendation": rec,
            "data_note": (
                "Contention percentages represent inventory overlap between the "
                "prospective line item and each existing campaign. Contention >30% "
                "means that campaign may lose significant delivery if this line item is added."
            ),
        }

    # ── GAP H2: VIDEO DELIVERY ANALYTICS ─────────────────────────────────────
    
    def get_video_analytics(
        self,
        start_date: date,
        end_date: date,
        breakdown_dimension: str = "VIDEO_POSITION_NAME",
    ) -> Dict[str, Any]:
        """Deep analytics for video viewership, drop-off, and pod performance.
        
        Fetches Video metrics using ReportService and processes them in Pandas.
        Answers: 'Show me video completion rates by ad position' or 'Video drop off by content'.
        
        Args:
            breakdown_dimension: VIDEO_POSITION_NAME (default), CONTENT_NAME, or VIDEO_AD_TYPE
        """
        import asyncio
        import io
        import gzip
        import urllib.request
        
        report_service = self._report_service()
        
        # Enforce valid video dimensions
        dim = str(breakdown_dimension).upper().strip()
        if dim not in ["VIDEO_POSITION_NAME", "CONTENT_NAME", "VIDEO_AD_TYPE", "VIDEO_PLACEMENT_NAME"]:
            dim = "VIDEO_POSITION_NAME" # Fallback
            
        report_query = {
            "dimensions": ["DATE", dim],
            "columns": [
                "AD_SERVER_IMPRESSIONS",
                "AD_SERVER_CPM_AND_CPC_REVENUE",
                "VIDEO_VIEWERSHIP_START",
                "VIDEO_VIEWERSHIP_FIRST_QUARTILE",
                "VIDEO_VIEWERSHIP_MIDPOINT",
                "VIDEO_VIEWERSHIP_THIRD_QUARTILE",
                "VIDEO_VIEWERSHIP_COMPLETE",
                "VIDEO_ERRORS"
            ],
            "dateRangeType": "CUSTOM_DATE",
            "startDate": self._to_gam_date(start_date),
            "endDate": self._to_gam_date(end_date),
        }
        report_job = {"reportQuery": report_query}
        
        try:
            log.info(f"Request made: Service: \"ReportService\" Method: \"runReportJob\" (Video Analytics, dim={dim})")
            report_job = report_service.runReportJob(report_job)
            job_id = report_job["id"]
        except Exception as e:
            log.error("Failed to run video analytics report: %s", e)
            return {"error": f"GAM API Error: {e}"}

        # Wait for the report (we are running in a sync thread)
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        if loop.is_running():
            raise RuntimeError("Cannot block in the main async loop. Ensure this is run in a thread.")
            
        success = loop.run_until_complete(self.wait_for_report(job_id))
        if not success:
            return {"error": "Report timeout or failed."}

        # Download report
        try:
            report_url = report_service.getReportDownloadUrlWithOptions(
                job_id, {"exportFormat": "CSV_DUMP", "useGzipCompression": True}
            )
            with urllib.request.urlopen(report_url) as resp:
                raw = resp.read()
            if report_url.endswith("gz") or raw[:2] == b"\x1f\x8b":
                raw = gzip.decompress(raw)
            raw = raw.decode("utf-8")
            df = pd.read_csv(io.StringIO(raw))
            del raw
            import gc; gc.collect()
        except Exception as e:
            return {"error": f"Failed to download video report: {e}"}

        # Standardize columns
        df.columns = [
            c.strip().lower().replace(" ", "_").replace("dimension.", "").replace("column.", "")
            for c in df.columns
        ]
        
        if df.empty:
            return {"_live_data_status": "unavailable", "_message": "No video delivery data available for this time period."}

        # Find the dimension column dynamically in the CSV
        known_metrics = {
            "ad_server_impressions", "ad_server_cpm_and_cpc_revenue",
            "video_viewership_start", "video_viewership_first_quartile",
            "video_viewership_midpoint", "video_viewership_third_quartile",
            "video_viewership_complete", "video_errors"
        }
        dim_col = None
        for c in df.columns:
            if c not in known_metrics and c != "date":
                dim_col = c
                break
                
        if not dim_col:
            dim_col = dim.lower() # Fallback if empty csv somehow bypassed empty check
            
        # ── Zero-Hallucination Math via Pandas ───────────────────────────────
        results = []
        for name, grp in df.groupby(dim_col):
            imps = int(grp.get("ad_server_impressions", pd.Series([0])).sum())
            if imps == 0:
                continue
            starts = int(grp.get("video_viewership_start", pd.Series([0])).sum())
            q1 = int(grp.get("video_viewership_first_quartile", pd.Series([0])).sum())
            mid = int(grp.get("video_viewership_midpoint", pd.Series([0])).sum())
            q3 = int(grp.get("video_viewership_third_quartile", pd.Series([0])).sum())
            completes = int(grp.get("video_viewership_complete", pd.Series([0])).sum())
            rev = float(grp.get("ad_server_cpm_and_cpc_revenue", pd.Series([0])).sum())
            errors = int(grp.get("video_errors", pd.Series([0])).sum())
            
            completion_rate = round(completes / starts * 100, 2) if starts > 0 else 0.0
            error_rate = round(errors / imps * 100, 2) if imps > 0 else 0.0
            
            results.append({
                dim_col: str(name),
                "impressions": imps,
                "starts": starts,
                "first_quartile": q1,
                "midpoint": mid,
                "third_quartile": q3,
                "completes": completes,
                "completion_rate_pct": completion_rate,
                "revenue_usd": round(rev, 2),
                "errors": errors,
                "error_rate_pct": error_rate
            })

        results.sort(key=lambda x: x["impressions"], reverse=True)
        
        # Aggregate totals
        total_imps = sum(r["impressions"] for r in results)
        total_starts = sum(r["starts"] for r in results)
        total_completes = sum(r["completes"] for r in results)
        total_rev = sum(r["revenue_usd"] for r in results)
        total_errors = sum(r["errors"] for r in results)
        
        if total_imps == 0:
            return {"_live_data_status": "unavailable", "_message": "No video impression data available for this time period."}

        return {
            "period": f"{start_date} to {end_date}",
            "breakdown_dimension": dim,
            "totals": {
                "impressions": total_imps,
                "starts": total_starts,
                "completes": total_completes,
                "completion_rate_pct": round(total_completes / total_starts * 100, 2) if total_starts > 0 else 0.0,
                "revenue_usd": round(total_rev, 2),
                "errors": total_errors,
            },
            "analytics": results[:20]
        }


