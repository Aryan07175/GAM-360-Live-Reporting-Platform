"""
GAM Client — Live-Only Mode
Every call generates a fresh report from Google Ad Manager.
No persistent cache. No database. No ETL.

Request-scoped deduplication (30s window) prevents duplicate concurrent
requests for the same date range during a single page load's Promise.all().
"""

import os
import io
import gzip
import asyncio
import logging
from datetime import date, datetime, timezone, timedelta
from typing import Optional, Callable, List
import pandas as pd
from googleads import ad_manager, errors

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("gam_client")

API_VERSION = os.getenv("GAM_API_VERSION", "v202602")
REQUEST_TIMEOUT = int(os.getenv("GAM_REQUEST_TIMEOUT", "120"))  # seconds
MAX_PARALLEL = int(os.getenv("GAM_MAX_PARALLEL_REQUESTS", "5"))

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

    # --- Total Network: request / fill / code metrics (WSDL-confirmed) ---
    "TOTAL_CODE_SERVED_COUNT",

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
}

# Dimensions that CANNOT be combined with AD_UNIT_NAME / AD_UNIT_ID in one report.
# For these, run_report() will use DATE + dimension only (no ad-unit breakdown).
DIMENSIONS_NEED_SEPARATE_REPORT = {"ADVERTISER_NAME", "CLASSIFIED_ADVERTISER_NAME", "COUNTRY_NAME"}

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

        if separate_report:
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

        # Columns: for separate-report mode, only request total-network columns
        # (ad-unit-level columns like AD_SERVER_AD_REQUESTS conflict with non-unit dims).
        if separate_report:
            report_cols = [
                "TOTAL_LINE_ITEM_LEVEL_IMPRESSIONS",
                "TOTAL_LINE_ITEM_LEVEL_CLICKS",
                "TOTAL_LINE_ITEM_LEVEL_CPM_AND_CPC_REVENUE",
                "TOTAL_LINE_ITEM_LEVEL_WITHOUT_CPD_AVERAGE_ECPM",
                "TOTAL_LINE_ITEM_LEVEL_CTR",
                "TOTAL_AD_REQUESTS",
                "TOTAL_RESPONSES_SERVED",
                "TOTAL_FILL_RATE",
            ]
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
        import urllib.request
        with urllib.request.urlopen(report_url) as resp:
            raw = resp.read()
        if report_url.endswith("gz") or raw[:2] == b"\x1f\x8b":
            import gzip
            raw = gzip.decompress(raw)
        raw = raw.decode("utf-8")

        df = pd.read_csv(io.StringIO(raw))
        df.columns = [
            c.strip().lower().replace(" ", "_").replace("dimension.", "").replace("column.", "")
            for c in df.columns
        ]

        # Ensure all channel columns exist (GAM omits them if channel has no data)
        for c in ALL_CHANNEL_COLS:
            if c not in df.columns:
                df[c] = 0.0

        # Convert all metric columns to numeric before summing
        for c in ALL_CHANNEL_COLS:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

        # ── Combine channels based on Demand Channel Filter ──────────────────
        if demand_channel == "programmatic":
            # Isolate programmatic revenue by excluding Ad Server (Direct-sold) revenue.
            # NOTE: This excludes Programmatic Guaranteed and Preferred Deals because
            # we cannot use LINE_ITEM_TYPE dimension without breaking Ad Requests.
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
            # For programmatic channels GAM does not expose a separate ad-requests
            # column — use the combined impressions as the best available proxy.
            if df["ad_server_ad_requests"].sum() == 0:
                df["ad_server_ad_requests"] = df["ad_server_impressions"]
                log.info("[ad_requests] AD_SERVER_AD_REQUESTS is 0 (programmatic mode) — "
                         "falling back to combined programmatic impressions as proxy.")
        else:
            # Total Network (All)
            # Map the native GAM Total metrics to our canonical dataframe columns.
            # AD_SERVER_AD_REQUESTS is untouched, as GAM does not have a "Total ad requests".
            df["ad_server_impressions"] = df["total_line_item_level_impressions"]
            df["ad_server_clicks"] = df["total_line_item_level_clicks"]
            df["ad_server_cpm_and_cpc_revenue"] = df["total_line_item_level_cpm_and_cpc_revenue"]
            df["ad_server_without_cpd_average_ecpm"] = df["total_line_item_level_without_cpd_average_ecpm"]
            # GAM's AD_SERVER_AD_REQUESTS only counts direct/ad-server requests.
            # On networks with mixed or programmatic-only demand it is frequently 0.
            # When that happens, fall back to total impressions as the best available
            # proxy (every impression required at least one ad request).
            if df["ad_server_ad_requests"].sum() == 0:
                df["ad_server_ad_requests"] = df["total_line_item_level_impressions"]
                log.info("[ad_requests] AD_SERVER_AD_REQUESTS is 0 — falling back to "
                         "total_line_item_level_impressions as proxy for ad requests.")

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

        df = df.fillna(0)

        # ── Diagnostic logging ──────────────────────────────────────────────
        total_rows = len(df)
        rev_sum = df["ad_server_cpm_and_cpc_revenue"].sum()
        imp_sum = df["ad_server_impressions"].sum()
        adx_imp = df["adx_impressions"].sum()
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
            "  Demand channel: %s",
            total_rows, dup_count, rev_sum, imp_sum,
            adx_imp, adx_match, ecpm_calc,
            unique_ad_units, date_min, date_max, demand_channel,
        )

        return df

    async def get_live_data(
        self, start: date, end: date, force_refresh: bool = False,
        demand_channel: str = "all", extra_dims: List[str] = None,
        separate_report: bool = False,
    ) -> pd.DataFrame:
        """
        Fetch LIVE data from Google Ad Manager. Always generates a new report.

        If force_refresh=False, uses request-scoped deduplication (30s window)
        to avoid duplicate requests within a single page load's Promise.all().

        If force_refresh=True, always generates a brand-new report.

        extra_dims: additional GAM dimension names (e.g. ["CHILD_NETWORK_CODE"])
        separate_report: if True, omit AD_UNIT_NAME/ID from dims (for advertiser/country)
        """
        extra_suffix = "_".join(extra_dims) if extra_dims else ""
        sep_suffix = "_sep" if separate_report else ""
        key = _dedup._key(self.network_code, start, end) + f"_{demand_channel}_{extra_suffix}{sep_suffix}"
        lock = _dedup._get_lock(key)

        async with lock:
            if not force_refresh:
                existing = _dedup.get_if_fresh(key)
                if existing is not None:
                    log.info(f"Dedup hit for {key} (within 30s window)")
                    return existing

            log.info(f"Fetching LIVE data from GAM: {start} to {end} (extra_dims={extra_dims} separate={separate_report})")

            job_id = await asyncio.to_thread(self.run_report, start, end, extra_dims, separate_report)
            await self.wait_for_report(job_id)
            df = await asyncio.to_thread(self.download_report, job_id, demand_channel)

            _dedup.store(key, df)
            log.info(f"LIVE data fetched: {len(df)} rows ({start} to {end})")
            return df

    async def get_live_data_multi_day(
        self, start: date, end: date, force_refresh: bool = False,
        demand_channel: str = "all", extra_dims: List[str] = None,
        separate_report: bool = False,
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
            df = await self.get_live_data(start, end, force_refresh, demand_channel, extra_dims, separate_report)
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
                            return await self.get_live_data(s, e, force_refresh, demand_channel, extra_dims, separate_report)
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
