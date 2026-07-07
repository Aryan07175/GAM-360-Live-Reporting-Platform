"use client";

import React, { createContext, useContext, useState, useEffect, useCallback } from "react";

interface DateContextValue {
  selectedDate: string | null;
  latestDate: string | null;
  availableDates: string[]; // Keep empty array to not break UI that mapped it
  dateLoading: boolean;
  setSelectedDate: (date: string) => void;
  refresh: () => void;
  refreshKey: number;
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
      // Latest date is just yesterday in the real-time MCP setup,
      // because GAM finalizes yesterday's data by today.
      const yesterday = new Date();
      yesterday.setDate(yesterday.getDate() - 1);
      const latestStr = yesterday.toISOString().split("T")[0];
      
      const dates = [];
      for(let i=0; i<180; i++) {
        const d = new Date(yesterday);
        d.setDate(d.getDate() - i);
        dates.push(d.toISOString().split("T")[0]);
      }
      
      setLatestDate(latestStr);
      setAvailableDates(dates);
      setSelectedDateState((prev) => (prev === null ? latestStr : prev));
    } finally {
      setDateLoading(false);
      setRefreshing(false);
    }
  }, []);

  // Initial fetch
  useEffect(() => {
    fetchLatest();
  }, [fetchLatest]);

  // Auto-refresh every 5 minutes
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
