"use client";

import React, { createContext, useContext, useMemo } from "react";
import { useLiveReport } from "@/contexts/DateContext";
import { runAlertEngine, computeAlertSummary } from "@/lib/alerts/alert-engine";
import type { Alert, AlertSummary } from "@/lib/alerts/alert-types";

// ─── Context Shape ────────────────────────────────────────────────────────────

interface AlertContextValue {
  alerts: Alert[];
  summary: AlertSummary;
  /** Convenience shorthand for summary.critical */
  criticalCount: number;
  /** Convenience shorthand for summary.total */
  totalCount: number;
  /** True while the report data is still loading */
  isLoading: boolean;
}

const DEFAULT_SUMMARY: AlertSummary = {
  total: 0,
  critical: 0,
  high: 0,
  medium: 0,
  low: 0,
  byCategory: {
    revenue: 0,
    impressions: 0,
    ctr: 0,
    fill_rate: 0,
    ecpm: 0,
    requests: 0,
    clicks: 0,
    match_rate: 0,
    users: 0,
    error: 0,
  },
};

const AlertContext = createContext<AlertContextValue>({
  alerts: [],
  summary: DEFAULT_SUMMARY,
  criticalCount: 0,
  totalCount: 0,
  isLoading: false,
});

// ─── Provider ─────────────────────────────────────────────────────────────────

export function AlertProvider({ children }: { children: React.ReactNode }) {
  const { appsData, trendData, summaryData, anomalyData, error, isLoading } =
    useLiveReport();

  // Re-run the alert engine whenever the underlying data changes.
  // useMemo ensures this is O(1) re-renders when data hasn't changed.
  const alerts = useMemo<Alert[]>(() => {
    if (!appsData && !summaryData && !anomalyData && !error) return [];

    return runAlertEngine({
      apps: appsData?.apps ?? [],
      trend: trendData?.trend ?? [],
      summary: summaryData?.summary ?? [],
      anomalies: anomalyData?.anomalies ?? [],
      error,
    });
  }, [appsData, trendData, summaryData, anomalyData, error]);

  const summary = useMemo(() => computeAlertSummary(alerts), [alerts]);

  const value: AlertContextValue = {
    alerts,
    summary,
    criticalCount: summary.critical,
    totalCount: summary.total,
    isLoading,
  };

  return (
    <AlertContext.Provider value={value}>{children}</AlertContext.Provider>
  );
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function useAlerts(): AlertContextValue {
  const ctx = useContext(AlertContext);
  if (!ctx) {
    throw new Error("useAlerts must be used inside <AlertProvider>");
  }
  return ctx;
}
