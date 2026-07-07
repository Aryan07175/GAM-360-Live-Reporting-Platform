import os
import io
import gzip
import time
import asyncio
import logging
from datetime import date, datetime, timezone
import pandas as pd
from googleads import ad_manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("gam_client")

API_VERSION = os.getenv("GAM_API_VERSION", "v202602")
TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "300")) # 5 minutes

DIMENSIONS = ["DATE", "AD_UNIT_NAME", "AD_UNIT_ID"]
COLUMNS = [
    "AD_SERVER_IMPRESSIONS",
    "AD_SERVER_CLICKS",
    "AD_SERVER_CTR",
    "AD_SERVER_AD_REQUESTS",
    "AD_SERVER_FILL_RATE",
    "AD_SERVER_CPM_AND_CPC_REVENUE",
    "AD_SERVER_WITHOUT_CPD_AVERAGE_ECPM",
]

class CacheManager:
    """
    In-memory cache with single-flight request deduplication.
    """
    def __init__(self):
        self.store = {} # { cache_key: { "data": df, "cached_at": datetime } }
        self.locks = {} # { cache_key: asyncio.Lock }
    
    def get(self, key: str):
        entry = self.store.get(key)
        if entry:
            age = (datetime.now(timezone.utc) - entry["cached_at"]).total_seconds()
            if age < TTL_SECONDS:
                return entry["data"], entry["cached_at"]
            else:
                del self.store[key]
        return None, None
        
    def set(self, key: str, data):
        self.store[key] = {
            "data": data,
            "cached_at": datetime.now(timezone.utc)
        }
        
    def get_lock(self, key: str) -> asyncio.Lock:
        if key not in self.locks:
            self.locks[key] = asyncio.Lock()
        return self.locks[key]
        
    async def cleanup_loop(self):
        while True:
            await asyncio.sleep(60)
            now = datetime.now(timezone.utc)
            keys_to_delete = []
            for k, v in self.store.items():
                if (now - v["cached_at"]).total_seconds() >= TTL_SECONDS:
                    keys_to_delete.append(k)
            for k in keys_to_delete:
                del self.store[k]
            # also cleanup unused locks
            for k in list(self.locks.keys()):
                if k not in self.store and not self.locks[k].locked():
                    del self.locks[k]

cache_manager = CacheManager()

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
        report_service = self._report_service()
        report_query = {
            "dimensions": DIMENSIONS,
            "columns": COLUMNS,
            "dateRangeType": "CUSTOM_DATE",
            "startDate": self._to_gam_date(start),
            "endDate": self._to_gam_date(end),
        }
        report_job = {"reportQuery": report_query}
        report_job = report_service.runReportJob(report_job)
        return report_job["id"]

    async def wait_for_report(self, job_id: int, poll_interval: int = 5) -> bool:
        report_service = self._report_service()
        while True:
            # We use asyncio.sleep to not block the event loop in MCP server
            status = report_service.getReportJobStatus(job_id)
            if status == "COMPLETED":
                return True
            elif status == "FAILED":
                return False
            await asyncio.sleep(poll_interval)

    def download_report(self, job_id: int) -> pd.DataFrame:
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
        except Exception:
            import urllib.request
            with urllib.request.urlopen(report_url) as resp:
                raw = resp.read()
            if report_url.endswith("gz") or raw[:2] == b"\x1f\x8b":
                raw = gzip.decompress(raw)
            raw = raw.decode("utf-8")

        df = pd.read_csv(io.StringIO(raw))
        df.columns = [c.strip().lower().replace(" ", "_").replace("dimension.", "").replace("column.", "") for c in df.columns]
        
        revenue_cols = [c for c in df.columns if "revenue" in c or "ecpm" in c or "cpm" in c]
        use_micros = os.getenv("REVENUE_IN_MICROS", "false").lower() == "true"
        if not use_micros:
            for col in revenue_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce") / 1_000_000
        for col in revenue_cols:
            if col in df.columns:
                df[col] = df[col].round(6)
        
        # We enforce types to float for stats
        df = df.fillna(0)
        return df

    async def get_cached_data(self, target_date: date) -> tuple[pd.DataFrame, str]:
        """
        Returns (DataFrame, cached_at_iso_string)
        """
        cache_key = f"gam_data_{self.network_code}_{target_date.isoformat()}"
        lock = cache_manager.get_lock(cache_key)
        
        async with lock:
            data, cached_at = cache_manager.get(cache_key)
            if data is not None:
                return data, cached_at.isoformat()
            
            # Cache miss - fetch from GAM
            log.info(f"Cache miss for {cache_key}. Fetching from GAM API...")
            
            # Run blocking API calls in executor to prevent freezing the MCP event loop
            job_id = await asyncio.to_thread(self.run_report, target_date, target_date)
            success = await self.wait_for_report(job_id)
            if not success:
                raise RuntimeError(f"GAM Report job failed.")
                
            df = await asyncio.to_thread(self.download_report, job_id)
            cache_manager.set(cache_key, df)
            
            data, cached_at = cache_manager.get(cache_key)
            return data, cached_at.isoformat()
