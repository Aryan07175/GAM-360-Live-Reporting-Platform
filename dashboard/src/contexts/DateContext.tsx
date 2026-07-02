"use client";

import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import { getLatestReportDate, getAvailableDates } from "@/services/api";

interface DateContextValue {
  /** The currently selected date for dashboard queries (YYYY-MM-DD) */
  selectedDate: string | null;
  /** The latest date with real data in Postgres */
  latestDate: string | null;
  /** All dates that have data in the database */
  availableDates: string[];
  /** Whether the date is still being fetched on first load */
  dateLoading: boolean;
  /** Update the selected date */
  setSelectedDate: (date: string) => void;
  /** Refresh all data (re-fetches latest date + bumps refresh key) */
  refresh: () => void;
  /** A counter that increments every time refresh() is called — pages can depend on this */
  refreshKey: number;
  /** Whether a refresh is in progress */
  refreshing: boolean;
}

const DateContext = createContext<DateContextValue>({
  selectedDate: null,
  latestDate: null,
  availableDates: [],
  dateLoading: true,
  setSelectedDate: () => {},
  refresh: () => {},
  refreshKey: 0,
  refreshing: false,
});

export function DateProvider({ children }: { children: React.ReactNode }) {
  const [selectedDate, setSelectedDateState] = useState<string | null>(null);
  const [latestDate, setLatestDate] = useState<string | null>(null);
  const [availableDates, setAvailableDates] = useState<string[]>([]);
  const [dateLoading, setDateLoading] = useState(true);
  const [refreshKey, setRefreshKey] = useState(0);
  const [refreshing, setRefreshing] = useState(false);

  const fetchLatest = useCallback(async () => {
    setRefreshing(true);
    try {
      const [latest, dates] = await Promise.all([
        getLatestReportDate(),
        getAvailableDates(),
      ]);
      setLatestDate(latest);
      setAvailableDates(dates);
      // Only auto-set the date on first load; after that, user controls it
      setSelectedDateState((prev) => (prev === null ? latest : prev));
    } finally {
      setDateLoading(false);
      setRefreshing(false);
    }
  }, []);

  // Initial fetch
  useEffect(() => {
    fetchLatest();
  }, [fetchLatest]);

  // Auto-refresh every 5 minutes to pick up new data
  useEffect(() => {
    const interval = setInterval(() => {
      fetchLatest();
      setRefreshKey((k) => k + 1);
    }, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, [fetchLatest]);

  const setSelectedDate = (date: string) => {
    setSelectedDateState(date);
    setRefreshKey((k) => k + 1);
  };

  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      const [latest, dates] = await Promise.all([
        getLatestReportDate(),
        getAvailableDates(),
      ]);
      setLatestDate(latest);
      setAvailableDates(dates);
      setRefreshKey((k) => k + 1);
    } finally {
      setRefreshing(false);
    }
  }, []);

  return (
    <DateContext.Provider
      value={{
        selectedDate,
        latestDate,
        availableDates,
        dateLoading,
        setSelectedDate,
        refresh,
        refreshKey,
        refreshing,
      }}
    >
      {children}
    </DateContext.Provider>
  );
}

export function useDateContext() {
  return useContext(DateContext);
}
