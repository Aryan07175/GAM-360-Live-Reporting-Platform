"use client";

import React, {
  createContext,
  useContext,
  useState,
  useCallback,
  useMemo,
} from "react";
import {
  format,
  subDays,
  startOfMonth,
  endOfMonth,
  subMonths,
} from "date-fns";
import type {
  DatePreset,
  LiveReportData,
  BISummaryKPI,
  BIAppRow,
  BIDailyPoint,
  BIAnomaly,
  BIInsight,
  Recommendation,
  PerformanceRanking,
  ReportProgress,
  SectionStatus,
} from "@/types";
import { fetchFullReport } from "@/actions/report-actions";

// ─── Date Range Computation ─────────────────────────────────────────────────

function computeDateRange(
  preset: DatePreset,
  customStart?: string,
  customEnd?: string
): { startDate: string; endDate: string } {
  const today = new Date();
  const yesterday = subDays(today, 1);

  switch (preset) {
    case "today":
      return {
        startDate: format(today, "yyyy-MM-dd"),
        endDate: format(today, "yyyy-MM-dd"),
      };
    case "yesterday":
      return {
        startDate: format(yesterday, "yyyy-MM-dd"),
        endDate: format(yesterday, "yyyy-MM-dd"),
      };
    case "last7days":
      return {
        startDate: format(subDays(today, 6), "yyyy-MM-dd"),
        endDate: format(today, "yyyy-MM-dd"),
      };
    case "last30days":
      return {
        startDate: format(subDays(today, 29), "yyyy-MM-dd"),
        endDate: format(today, "yyyy-MM-dd"),
      };
    case "thisMonth":
      return {
        startDate: format(startOfMonth(today), "yyyy-MM-dd"),
        endDate: format(today, "yyyy-MM-dd"),
      };
    case "lastMonth": {
      const prevMonth = subMonths(today, 1);
      return {
        startDate: format(startOfMonth(prevMonth), "yyyy-MM-dd"),
        endDate: format(endOfMonth(prevMonth), "yyyy-MM-dd"),
      };
    }
    case "custom":
      return {
        startDate: customStart || format(yesterday, "yyyy-MM-dd"),
        endDate: customEnd || format(yesterday, "yyyy-MM-dd"),
      };
    default:
      return {
        startDate: format(yesterday, "yyyy-MM-dd"),
        endDate: format(yesterday, "yyyy-MM-dd"),
      };
  }
}

// ─── Context Type ───────────────────────────────────────────────────────────

interface LiveReportContextValue {
  // Date controls
  datePreset: DatePreset;
  startDate: string;
  endDate: string;
  startTime: string;
  endTime: string;
  customStartDate: string;
  customEndDate: string;
  customStartTime: string;
  customEndTime: string;
  demandChannel: string;
  setDatePreset: (preset: DatePreset) => void;
  setCustomRange: (start: string, end: string, startTime?: string, endTime?: string) => void;
  setDemandChannel: (channel: string) => void;

  // Report data
  reportData: LiveReportData | null;
  summaryData: { summary: BISummaryKPI[]; fetchedAt: string } | null;
  appsData: { apps: BIAppRow[]; fetchedAt: string } | null;
  trendData: { trend: BIDailyPoint[]; fetchedAt: string } | null;
  anomalyData: { anomalies: BIAnomaly[]; fetchedAt: string } | null;
  recommendationData: {
    recommendations: Recommendation[];
    fetchedAt: string;
  } | null;
  rankingData: {
    rankings: PerformanceRanking[];
    fetchedAt: string;
  } | null;

  // Loading & Progress
  isLoading: boolean;
  progress: ReportProgress;
  error: string | null;
  lastFetchedAt: string | null;

  // Actions
  generateReport: (forceRefresh?: boolean) => Promise<void>;
  refresh: () => Promise<void>;
  clearError: () => void;
}

const defaultProgress: ReportProgress = {
  total: 6,
  completed: 0,
  currentSection: "",
  sections: [
    { name: "Executive Summary", status: "pending" },
    { name: "Applications", status: "pending" },
    { name: "Revenue Trend", status: "pending" },
    { name: "Anomaly Detection", status: "pending" },
    { name: "Recommendations", status: "pending" },
    { name: "Performance Ranking", status: "pending" },
  ],
};

const LiveReportContext = createContext<LiveReportContextValue>({
  datePreset: "yesterday",
  startDate: "",
  endDate: "",
  startTime: "00:00",
  endTime: "23:59",
  customStartDate: "",
  customEndDate: "",
  customStartTime: "00:00",
  customEndTime: "23:59",
  demandChannel: "all",
  setDatePreset: () => {},
  setCustomRange: () => {},
  setDemandChannel: () => {},
  reportData: null,
  summaryData: null,
  appsData: null,
  trendData: null,
  anomalyData: null,
  recommendationData: null,
  rankingData: null,
  isLoading: false,
  progress: defaultProgress,
  error: null,
  lastFetchedAt: null,
  generateReport: async () => {},
  refresh: async () => {},
  clearError: () => {},
});

// ─── Provider ───────────────────────────────────────────────────────────────

export function LiveReportProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  // Date state
  const [datePreset, setDatePresetState] = useState<DatePreset>("yesterday");
  const [customStartDate, setCustomStartDate] = useState<string>("");
  const [customEndDate, setCustomEndDate] = useState<string>("");
  const [customStartTime, setCustomStartTime] = useState<string>("00:00");
  const [customEndTime, setCustomEndTime] = useState<string>("23:59");
  const [demandChannel, setDemandChannelState] = useState<string>("all");

  // Compute effective dates
  const { startDate, endDate, startTime, endTime } = useMemo(() => {
    const dates = computeDateRange(datePreset, customStartDate, customEndDate);
    if (datePreset === "custom") {
      return { ...dates, startTime: customStartTime, endTime: customEndTime };
    }
    return { ...dates, startTime: "00:00", endTime: "23:59" };
  }, [datePreset, customStartDate, customEndDate, customStartTime, customEndTime]);

  // Data state — each section independent for progressive loading
  const [summaryData, setSummaryData] = useState<{
    summary: BISummaryKPI[];
    fetchedAt: string;
  } | null>(null);
  const [appsData, setAppsData] = useState<{
    apps: BIAppRow[];
    fetchedAt: string;
  } | null>(null);
  const [trendData, setTrendData] = useState<{
    trend: BIDailyPoint[];
    fetchedAt: string;
  } | null>(null);
  const [anomalyData, setAnomalyData] = useState<{
    anomalies: BIAnomaly[];
    fetchedAt: string;
  } | null>(null);
  const [recommendationData, setRecommendationData] = useState<{
    recommendations: Recommendation[];
    fetchedAt: string;
  } | null>(null);
  const [rankingData, setRankingData] = useState<{
    rankings: PerformanceRanking[];
    fetchedAt: string;
  } | null>(null);

  // Loading state
  const [isLoading, setIsLoading] = useState(false);
  const [progress, setProgress] = useState<ReportProgress>({
    ...defaultProgress,
  });
  const [error, setError] = useState<string | null>(null);
  const [lastFetchedAt, setLastFetchedAt] = useState<string | null>(null);

  // Compose full report data from sections
  const reportData = useMemo<LiveReportData | null>(() => {
    if (!summaryData && !appsData) return null;
    return {
      startDate,
      endDate,
      fetchedAt: lastFetchedAt || new Date().toISOString(),
      summary: summaryData?.summary || [],
      apps: appsData?.apps || [],
      topApps: (appsData?.apps || []).slice(0, 10),
      bottomApps: [...(appsData?.apps || [])].reverse().slice(0, 10),
      dailyTrend: trendData?.trend || [],
      anomalies: anomalyData?.anomalies || [],
      insights: [],
      recommendations: recommendationData?.recommendations || [],
      rankings: rankingData?.rankings || [],
    };
  }, [
    summaryData,
    appsData,
    trendData,
    anomalyData,
    recommendationData,
    rankingData,
    startDate,
    endDate,
    lastFetchedAt,
  ]);

  // ─── Section update helper ────────────────────────────────────────────────

  const updateSection = useCallback(
    (index: number, status: SectionStatus["status"], errorMsg?: string) => {
      setProgress((prev) => {
        const newSections = [...prev.sections];
        newSections[index] = {
          ...newSections[index],
          status,
          error: errorMsg,
        };
        const completed = newSections.filter(
          (s) => s.status === "done" || s.status === "error"
        ).length;
        const loading = newSections.find((s) => s.status === "loading");
        return {
          ...prev,
          completed,
          currentSection: loading?.name || "",
          sections: newSections,
        };
      });
    },
    []
  );

  // ─── Generate Report ──────────────────────────────────────────────────────

  const generateReport = useCallback(
    async (forceRefresh: boolean = false) => {
      setIsLoading(true);
      setError(null);
      setSummaryData(null);
      setAppsData(null);
      setTrendData(null);
      setAnomalyData(null);
      setRecommendationData(null);
      setRankingData(null);
      setProgress({
        total: 6,
        completed: 0,
        currentSection: "Generating Full Report",
        sections: defaultProgress.sections.map((s) => ({
          ...s,
          status: "loading" as const,
        })),
      });

      // ── Backend health pre-check with auto-retry ────────────────────────────
      // Render free tier sleeps after inactivity. Cold starts take 30–90s.
      // We retry the health check every 15s for up to 90s total before giving up.
      const MCP_URL =
        process.env.NEXT_PUBLIC_MCP_SERVER_URL ||
        "https://gam-360-live-reporting-platform.onrender.com";

      console.log(`[GAM360] Health check → /api/health (backend: ${MCP_URL})`);

      const MAX_HEALTH_RETRIES = 6;
      const HEALTH_RETRY_DELAY_MS = 15_000; // 15s between retries
      let backendAlive = false;

      for (let attempt = 1; attempt <= MAX_HEALTH_RETRIES; attempt++) {
        try {
          const healthRes = await fetch("/api/health", {
            method: "GET",
            cache: "no-store",
            signal: AbortSignal.timeout(20_000),
          });

          console.log(`[GAM360] Health attempt ${attempt}/${MAX_HEALTH_RETRIES}: ${healthRes.status}`);

          if (healthRes.ok) {
            const health = await healthRes.json();
            console.log("[GAM360] Backend alive:", health);

            // Warn about missing credentials but don't retry
            if (
              health?.gam?.network_code === null ||
              health?.gam?.credentials_file_present === false
            ) {
              setError(
                "Backend is running but GAM credentials are not configured. " +
                "Set GAM_NETWORK_CODE and GAM_SERVICE_ACCOUNT_JSON in your Render environment."
              );
              setIsLoading(false);
              return;
            }

            backendAlive = true;
            break; // ✅ Backend is healthy — exit retry loop
          }

          // 502/503/504 = cold-starting — retry
          console.warn(`[GAM360] Backend not ready (${healthRes.status}), attempt ${attempt}/${MAX_HEALTH_RETRIES}`);

        } catch (healthErr: any) {
          const errName: string = healthErr?.name || "";
          console.warn(`[GAM360] Health check error on attempt ${attempt}/${MAX_HEALTH_RETRIES}: ${errName}`);
        }

        if (attempt < MAX_HEALTH_RETRIES) {
          // Wait before next retry
          await new Promise((resolve) => setTimeout(resolve, HEALTH_RETRY_DELAY_MS));
        }
      }

      if (!backendAlive) {
        // All retries exhausted — show error
        setError(
          "Backend is unavailable after multiple retries. " +
          "The Render service may be redeploying. Please try again in a minute."
        );
        setIsLoading(false);
        setProgress({
          total: 6,
          completed: 0,
          currentSection: "",
          sections: defaultProgress.sections.map((s) => ({
            ...s,
            status: "error" as const,
            error: "Backend unavailable",
          })),
        });
        return;
      }


      try {
        const result = await fetchFullReport(
          startDate,
          endDate,
          startTime,
          endTime,
          demandChannel,
          forceRefresh
        );

        if (result) {
          setSummaryData({ summary: result.summary, fetchedAt: result.fetchedAt });
          setAppsData({ apps: result.apps, fetchedAt: result.fetchedAt });
          setTrendData({ trend: result.dailyTrend, fetchedAt: result.fetchedAt });
          setAnomalyData({ anomalies: result.anomalies, fetchedAt: result.fetchedAt });
          setRecommendationData({ recommendations: result.recommendations, fetchedAt: result.fetchedAt });
          setRankingData({ rankings: result.rankings, fetchedAt: result.fetchedAt });

          setProgress({
            total: 6,
            completed: 6,
            currentSection: "",
            sections: defaultProgress.sections.map((s) => ({
              ...s,
              status: "done" as const,
            })),
          });
        } else {
          const noDataMsg = "No data returned from the backend. The GAM API may have returned an empty report for this date range.";
          setError(noDataMsg);
          setProgress((prev) => ({
            ...prev,
            sections: prev.sections.map((s) => ({
              ...s,
              status: "error" as const,
              error: "No data returned",
            })),
          }));
        }
      } catch (err: any) {
        const rawMsg: string = err?.message || "Failed to fetch report from backend";
        let friendlyMsg = rawMsg;

        // Classify error type for a better user message
        if (rawMsg.includes("404")) {
          friendlyMsg = "API endpoint not found (404). The backend route may have changed. Check /api/tool on the Render service.";
        } else if (rawMsg.includes("401") || rawMsg.includes("403")) {
          friendlyMsg = "Authentication error (401/403). Check your API credentials in Render environment variables.";
        } else if (rawMsg.includes("500") || rawMsg.includes("502") || rawMsg.includes("503")) {
          friendlyMsg = `Backend server error (${rawMsg.match(/\d{3}/)?.[0] || "5xx"}). Check Render logs for the traceback.`;
        } else if (rawMsg.toLowerCase().includes("timeout") || rawMsg.toLowerCase().includes("timed out")) {
          friendlyMsg = "The GAM report request timed out. The date range may be too large or the GAM API is slow. Try a shorter range.";
        } else if (rawMsg.toLowerCase().includes("network") || rawMsg.toLowerCase().includes("fetch")) {
          friendlyMsg = "Network error while fetching the report. Check your internet connection and Render service status.";
        }

        console.error("[GAM360] fetchFullReport error:", rawMsg);
        setError(friendlyMsg);
        setProgress((prev) => ({
          ...prev,
          sections: prev.sections.map((s) => ({
            ...s,
            status: "error" as const,
            error: friendlyMsg,
          })),
        }));
      }

      setLastFetchedAt(new Date().toISOString());
      setIsLoading(false);
    },
    [startDate, endDate, startTime, endTime, demandChannel, updateSection]
  );


  // ─── Refresh (force new GAM request) ──────────────────────────────────────

  const refresh = useCallback(async () => {
    await generateReport(true);
  }, [generateReport]);

  // ─── Date Setters ─────────────────────────────────────────────────────────

  const setDatePreset = useCallback((preset: DatePreset) => {
    setDatePresetState(preset);
  }, []);

  const setCustomRange = useCallback((start: string, end: string, sTime: string = "00:00", eTime: string = "23:59") => {
    setCustomStartDate(start);
    setCustomEndDate(end);
    setCustomStartTime(sTime);
    setCustomEndTime(eTime);
    setDatePresetState("custom");
  }, []);

  const clearError = useCallback(() => setError(null), []);

  // ─── Context Value ────────────────────────────────────────────────────────

  const value: LiveReportContextValue = {
    datePreset,
    startDate,
    endDate,
    startTime,
    endTime,
    customStartDate,
    customEndDate,
    customStartTime,
    customEndTime,
    demandChannel,
    setDatePreset,
    setCustomRange,
    setDemandChannel: setDemandChannelState,
    reportData,
    summaryData,
    appsData,
    trendData,
    anomalyData,
    recommendationData,
    rankingData,
    isLoading,
    progress,
    error,
    lastFetchedAt,
    generateReport,
    refresh,
    clearError,
  };

  return (
    <LiveReportContext.Provider value={value}>
      {children}
    </LiveReportContext.Provider>
  );
}

export function useLiveReport() {
  return useContext(LiveReportContext);
}

// Keep backward compatibility alias
export function useDateContext() {
  const ctx = useLiveReport();
  return {
    selectedDate: ctx.startDate,
    latestDate: format(subDays(new Date(), 1), "yyyy-MM-dd"),
    availableDates: [] as string[],
    dateLoading: false,
    setSelectedDate: (date: string) => ctx.setCustomRange(date, date),
    refresh: ctx.refresh,
    refreshKey: ctx.lastFetchedAt ? new Date(ctx.lastFetchedAt).getTime() : 0,
    refreshing: ctx.isLoading,
  };
}
