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
from typing import Optional, Callable
import pandas as pd
from googleads import ad_manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("gam_client")

API_VERSION = os.getenv("GAM_API_VERSION", "v202602")
REQUEST_TIMEOUT = int(os.getenv("GAM_REQUEST_TIMEOUT", "120"))  # seconds
MAX_PARALLEL = int(os.getenv("GAM_MAX_PARALLEL_REQUESTS", "5"))

DIMENSIONS = ["DATE", "HOUR", "AD_UNIT_NAME", "AD_UNIT_ID"]
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

    # --- Ad Exchange (programmatic) ---
    "AD_EXCHANGE_LINE_ITEM_LEVEL_IMPRESSIONS",
    "AD_EXCHANGE_LINE_ITEM_LEVEL_CLICKS",
    "AD_EXCHANGE_LINE_ITEM_LEVEL_REVENUE",

    # --- Total Network (All Channels) ---
    "TOTAL_LINE_ITEM_LEVEL_IMPRESSIONS",
    "TOTAL_LINE_ITEM_LEVEL_CLICKS",
    "TOTAL_LINE_ITEM_LEVEL_CPM_AND_CPC_REVENUE",
    "TOTAL_LINE_ITEM_LEVEL_WITHOUT_CPD_AVERAGE_ECPM",
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

    def run_report(self, start: date, end: date) -> int:
        """Submit a report job to Google Ad Manager."""
        report_service = self._report_service()
        
        # Omit HOUR dimension for large ranges to prevent millions of rows and OOM crashes.
        # Only keep HOUR for single or 2-day ranges where hourly filtering is useful.
        day_count = (end - start).days + 1
        report_dims = ["DATE", "AD_UNIT_NAME", "AD_UNIT_ID"]
        if day_count <= 2:
            report_dims.insert(1, "HOUR")
            
        report_query = {
            "dimensions": report_dims,
            "columns": COLUMNS,
            "dateRangeType": "CUSTOM_DATE",
            "startDate": self._to_gam_date(start),
            "endDate": self._to_gam_date(end),
        }
        report_job = {"reportQuery": report_query}
        report_job = report_service.runReportJob(report_job)
        log.info(f"GAM report job submitted: {report_job['id']} ({start} to {end})")
        return report_job["id"]

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
        downloader = self.client.GetDataDownloader(version=API_VERSION)
        try:
            raw = downloader.DownloadReportAsString(
                job_id, export_format="CSV_DUMP", use_gzip_compression=True
            )
        except Exception as e:
            log.warning(f"DownloadReportAsString failed, falling back to manual download: {e}")
            import urllib.request
            with urllib.request.urlopen(report_url) as resp:
                raw = resp.read()
            if report_url.endswith("gz") or raw[:2] == b"\x1f\x8b":
                raw = gzip.decompress(raw)
            raw = raw.decode("utf-8")

        df = pd.read_csv(io.StringIO(raw))
        df.columns = [
            c.strip().lower().replace(" ", "_").replace("dimension.", "").replace("column.", "")
            for c in df.columns
        ]

        # Ensure all channel columns exist (GAM omits them if channel has no data)
        channel_cols = [
            "ad_server_impressions", "ad_server_clicks", "ad_server_cpm_and_cpc_revenue",
            "adsense_line_item_level_impressions", "adsense_line_item_level_clicks",
            "adsense_line_item_level_revenue",
            "ad_exchange_line_item_level_impressions", "ad_exchange_line_item_level_clicks",
            "ad_exchange_line_item_level_revenue",
            "total_line_item_level_impressions", "total_line_item_level_clicks",
            "total_line_item_level_cpm_and_cpc_revenue",
            "total_line_item_level_without_cpd_average_ecpm",
            "ad_server_ctr", "ad_server_ad_requests", "ad_server_fill_rate",
            "ad_server_without_cpd_average_ecpm",
        ]
        for c in channel_cols:
            if c not in df.columns:
                df[c] = 0.0

        # Convert all metric columns to numeric before summing
        for c in channel_cols:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

        # ── Combine channels based on Demand Channel Filter ──
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
        else:
            # Total Network (All)
            # Map the native GAM Total metrics to our canonical dataframe columns.
            # AD_SERVER_AD_REQUESTS is untouched, as GAM does not have a "Total ad requests".
            df["ad_server_impressions"] = df["total_line_item_level_impressions"]
            df["ad_server_clicks"] = df["total_line_item_level_clicks"]
            df["ad_server_cpm_and_cpc_revenue"] = df["total_line_item_level_cpm_and_cpc_revenue"]
            df["ad_server_without_cpd_average_ecpm"] = df["total_line_item_level_without_cpd_average_ecpm"]

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

        # ── Diagnostic logging ──
        total_rows = len(df)
        rev_sum = df["ad_server_cpm_and_cpc_revenue"].sum()
        imp_sum = df["ad_server_impressions"].sum()
        ecpm_calc = (rev_sum / imp_sum * 1000) if imp_sum > 0 else 0
        unique_ad_units = df["ad_unit_name"].nunique() if "ad_unit_name" in df.columns else 0
        date_min = df["date"].min() if "date" in df.columns else "N/A"
        date_max = df["date"].max() if "date" in df.columns else "N/A"

        # Duplicate check: look for rows with identical (date, ad_unit_id) combos
        dedup_cols = [c for c in ["date", "ad_unit_id"] if c in df.columns]
        dup_count = df.duplicated(subset=dedup_cols).sum() if dedup_cols else 0

        log.info(
            "[DIAG] Report download complete:\n"
            "  Total rows: %d\n"
            "  Duplicate rows (date+ad_unit_id): %d\n"
            "  Revenue sum: %.6f\n"
            "  Impression sum: %.0f\n"
            "  Computed eCPM: %.6f\n"
            "  Unique Ad Units: %d\n"
            "  Date range: %s to %s\n"
            "  Demand channel: %s",
            total_rows, dup_count, rev_sum, imp_sum, ecpm_calc,
            unique_ad_units, date_min, date_max, demand_channel,
        )

        return df

    async def get_live_data(
        self, start: date, end: date, force_refresh: bool = False, demand_channel: str = "all"
    ) -> pd.DataFrame:
        """
        Fetch LIVE data from Google Ad Manager. Always generates a new report.
        
        If force_refresh=False, uses request-scoped deduplication (30s window)
        to avoid duplicate requests within a single page load's Promise.all().
        
        If force_refresh=True, always generates a brand-new report.
        """
        key = _dedup._key(self.network_code, start, end) + f"_{demand_channel}"
        lock = _dedup._get_lock(key)

        async with lock:
            # Check deduplication (only if not force refresh)
            if not force_refresh:
                existing = _dedup.get_if_fresh(key)
                if existing is not None:
                    log.info(f"Dedup hit for {key} (within 30s window)")
                    return existing

            # Always fetch fresh from GAM
            log.info(f"Fetching LIVE data from GAM: {start} to {end}")

            # Run blocking API calls in executor
            job_id = await asyncio.to_thread(self.run_report, start, end)
            await self.wait_for_report(job_id)
            df = await asyncio.to_thread(self.download_report, job_id, demand_channel)

            # Store for deduplication (30s only)
            _dedup.store(key, df)

            log.info(f"LIVE data fetched: {len(df)} rows ({start} to {end})")
            return df

    async def get_live_data_multi_day(
        self, start: date, end: date, force_refresh: bool = False, demand_channel: str = "all"
    ) -> pd.DataFrame:
        """
        Fetch data for a date range from Google Ad Manager.
        
        The GAM API can handle date ranges up to a full year in a single report,
        so we only split into chunks for very large ranges (> 90 days).
        Chunks are 30-day blocks fetched in parallel with concurrency limits.
        """
        day_count = (end - start).days + 1

        # For ranges up to 90 days, fetch as a single GAM report
        if day_count <= 90:
            df = await self.get_live_data(start, end, force_refresh, demand_channel)
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
                            return await self.get_live_data(s, e, force_refresh, demand_channel)
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

            # Combine all successful results
            dfs = list(results)
            if not dfs:
                raise RuntimeError("All GAM report chunks failed")

            df = pd.concat(dfs, ignore_index=True)
            log.info(f"Combined {len(dfs)} chunks: {len(df)} total rows")

        # For "programmatic" filter, we just return the dataset as is here, 
        # but we handle the metric combination in get_live_data based on what's available
        # Programmatic Guaranteed will be missed because it's part of ad_server_cpm_and_cpc_revenue
        # which we cannot separate without breaking ad requests.

        return df

