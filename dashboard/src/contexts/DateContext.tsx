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
import {
  fetchExecutiveSummary,
  fetchRevenueByApplication,
  fetchRevenueTrend,
  fetchAnomalies,
  fetchRecommendations,
  fetchPerformanceRanking,
} from "@/actions/report-actions";

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
  setDatePreset: (preset: DatePreset) => void;
  setCustomRange: (start: string, end: string, startTime?: string, endTime?: string) => void;

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
  customStartDate: "",
  customEndDate: "",
  customStartTime: "00:00",
  customEndTime: "23:59",
  setDatePreset: () => {},
  setCustomRange: () => {},
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
        currentSection: "Executive Summary",
        sections: defaultProgress.sections.map((s) => ({
          ...s,
          status: "loading" as const,
        })),
      });

      const sections = [
        {
          index: 0,
          name: "Executive Summary",
          fn: async () => {
            const result = await fetchExecutiveSummary(
              startDate,
              endDate,
              startTime,
              endTime,
              forceRefresh
            );
            setSummaryData(result);
            return result;
          },
        },
        {
          index: 1,
          name: "Applications",
          fn: async () => {
            const result = await fetchRevenueByApplication(
              startDate,
              endDate,
              startTime,
              endTime,
              forceRefresh
            );
            setAppsData(result);
            return result;
          },
        },
        {
          index: 2,
          name: "Revenue Trend",
          fn: async () => {
            const result = await fetchRevenueTrend(
              startDate,
              endDate,
              startTime,
              endTime,
              forceRefresh
            );
            setTrendData(result);
            return result;
          },
        },
        {
          index: 3,
          name: "Anomaly Detection",
          fn: async () => {
            const result = await fetchAnomalies(
              startDate,
              endDate,
              startTime,
              endTime,
              forceRefresh
            );
            setAnomalyData(result);
            return result;
          },
        },
        {
          index: 4,
          name: "Recommendations",
          fn: async () => {
            const result = await fetchRecommendations(
              startDate,
              endDate,
              startTime,
              endTime,
              forceRefresh
            );
            setRecommendationData(result);
            return result;
          },
        },
        {
          index: 5,
          name: "Performance Ranking",
          fn: async () => {
            const result = await fetchPerformanceRanking(
              startDate,
              endDate,
              startTime,
              endTime,
              forceRefresh
            );
            setRankingData(result);
            return result;
          },
        },
      ];

      // Fire all sections in parallel
      const promises = sections.map(async (section) => {
        try {
          updateSection(section.index, "loading");
          const result = await section.fn();
          updateSection(section.index, result ? "done" : "error", result ? undefined : "No data returned");
        } catch (err: any) {
          updateSection(section.index, "error", err.message);
        }
      });

      await Promise.allSettled(promises);

      setLastFetchedAt(new Date().toISOString());
      setIsLoading(false);
    },
    [startDate, endDate, updateSection]
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
    setDatePreset,
    setCustomRange,
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
