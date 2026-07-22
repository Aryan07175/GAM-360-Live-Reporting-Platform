"use client";

import { useEffect, useState, useMemo, useCallback } from "react";
import { motion } from "framer-motion";
import { Bell, Zap, RefreshCw, CheckCircle2, Info } from "lucide-react";
import { format, parseISO } from "date-fns";
import { useLiveReport } from "@/contexts/DateContext";
import { useAlerts } from "@/contexts/AlertContext";
import { AlertSummaryBar } from "@/components/alerts/alert-summary-bar";
import { AlertCard } from "@/components/alerts/alert-card";
import { AlertFilters } from "@/components/alerts/alert-filters";
import { AlertSearchSort } from "@/components/alerts/alert-search-sort";
import { AlertDetailModal } from "@/components/alerts/alert-detail-modal";
import { Skeleton } from "@/components/ui/skeleton";
import type { Alert } from "@/lib/alerts/alert-types";
import type { FilterCategory, FilterSeverity } from "@/components/alerts/alert-filters";
import type { SortOption } from "@/components/alerts/alert-search-sort";

// ─── Skeleton ────────────────────────────────────────────────────────────────

function AlertCardSkeleton() {
  return (
    <div className="rounded-xl border border-border bg-card p-4 space-y-3">
      <div className="flex items-start gap-3">
        <Skeleton className="h-10 w-10 rounded-lg flex-shrink-0" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-3 w-1/2" />
        </div>
        <Skeleton className="h-6 w-16 rounded-full" />
      </div>
      <div className="grid grid-cols-3 gap-3">
        <Skeleton className="h-14 rounded-lg" />
        <Skeleton className="h-14 rounded-lg" />
        <Skeleton className="h-14 rounded-lg" />
      </div>
    </div>
  );
}

// ─── Sorting logic ───────────────────────────────────────────────────────────

const SEVERITY_ORDER: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };

function sortAlerts(alerts: Alert[], sort: SortOption): Alert[] {
  return [...alerts].sort((a, b) => {
    switch (sort) {
      case "newest":
        return new Date(b.generatedAt).getTime() - new Date(a.generatedAt).getTime();
      case "oldest":
        return new Date(a.generatedAt).getTime() - new Date(b.generatedAt).getTime();
      case "severity":
        return SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity];
      case "app_name":
        return a.appName.localeCompare(b.appName);
      case "largest_drop":
        return a.changePct - b.changePct; // most negative first
      case "largest_increase":
        return b.changePct - a.changePct; // most positive first
      default:
        return 0;
    }
  });
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function AlertsPage() {
  const { startDate, endDate, appsData, isLoading, generateReport, refresh, lastFetchedAt } =
    useLiveReport();
  const { alerts, summary } = useAlerts();

  // Filters & search state
  const [activeCategory, setActiveCategory] = useState<FilterCategory>("all");
  const [activeSeverity, setActiveSeverity] = useState<FilterSeverity>("all");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<SortOption>("severity");
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null);

  // Auto-fetch on first load
  useEffect(() => {
    if (!appsData) generateReport();
  }, [appsData, generateReport]);

  // Close modal on ESC
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") setSelectedAlert(null);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  const displayRange = useMemo(() => {
    try {
      return startDate === endDate
        ? format(parseISO(startDate), "MMM dd, yyyy")
        : `${format(parseISO(startDate), "MMM dd")} → ${format(parseISO(endDate), "MMM dd, yyyy")}`;
    } catch {
      return "—";
    }
  }, [startDate, endDate]);

  // Filter + search + sort
  const filteredAlerts = useMemo(() => {
    let result = alerts;

    if (activeCategory !== "all") {
      result = result.filter((a) => a.category === activeCategory);
    }
    if (activeSeverity !== "all") {
      result = result.filter((a) => a.severity === activeSeverity);
    }
    if (search.trim()) {
      const q = search.toLowerCase();
      result = result.filter(
        (a) =>
          a.appName.toLowerCase().includes(q) ||
          a.title.toLowerCase().includes(q) ||
          a.metric.toLowerCase().includes(q) ||
          a.category.toLowerCase().includes(q) ||
          a.reason.toLowerCase().includes(q)
      );
    }

    return sortAlerts(result, sort);
  }, [alerts, activeCategory, activeSeverity, search, sort]);

  const handleRefresh = useCallback(async () => {
    setActiveCategory("all");
    setActiveSeverity("all");
    setSearch("");
    await refresh();
  }, [refresh]);

  // ── Loading skeleton ─────────────────────────────────────────────────────
  if (isLoading && !appsData) {
    return (
      <div className="space-y-6">
        <div>
          <Skeleton className="h-8 w-48 mb-2" />
          <Skeleton className="h-4 w-72" />
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-20 rounded-xl" />
          ))}
        </div>
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => <AlertCardSkeleton key={i} />)}
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-2xl font-bold tracking-tight flex items-center gap-2">
              <Zap className="h-6 w-6 text-indigo-500" />
              Live Alerts
            </h2>
            <p className="text-sm text-muted-foreground mt-0.5">
              Real-time alerts from live GAM data · {displayRange}
              {lastFetchedAt && (
                <span className="ml-2 text-xs text-muted-foreground/60">
                  · Last updated {format(new Date(lastFetchedAt), "HH:mm:ss")}
                </span>
              )}
            </p>
          </div>
          <button
            onClick={handleRefresh}
            disabled={isLoading}
            className="flex items-center gap-2 rounded-lg border border-border bg-muted/50 px-3 py-2 text-sm font-medium hover:bg-muted transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>

        {/* Summary bar */}
        <AlertSummaryBar summary={summary} />

        {/* User alerts notice */}
        <div className="flex items-start gap-2 rounded-xl border border-blue-400/20 bg-blue-400/5 px-4 py-3">
          <Info className="h-4 w-4 text-blue-500 flex-shrink-0 mt-0.5" />
          <p className="text-xs text-muted-foreground">
            <span className="font-medium text-foreground">Active User alerts</span> (DAU/WAU/MAU) are not shown because
            Google Ad Manager does not provide user metrics directly.
            To enable them, integrate{" "}
            <span className="font-medium text-indigo-500">Firebase Analytics</span> or{" "}
            <span className="font-medium text-indigo-500">GA4</span> as a data source.
          </p>
        </div>

        {/* Filters */}
        <AlertFilters
          activeCategory={activeCategory}
          activeSeverity={activeSeverity}
          summary={summary}
          onCategoryChange={setActiveCategory}
          onSeverityChange={setActiveSeverity}
        />

        {/* Search + sort */}
        <AlertSearchSort
          search={search}
          sort={sort}
          onSearchChange={setSearch}
          onSortChange={setSort}
          resultCount={filteredAlerts.length}
          totalCount={alerts.length}
        />

        {/* Alert list */}
        {alerts.length === 0 ? (
          /* All clear */
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-xl border border-dashed border-border bg-card py-20 text-center"
          >
            <CheckCircle2 className="h-12 w-12 text-green-500 mx-auto mb-4" />
            <h3 className="text-lg font-semibold mb-1">All Clear</h3>
            <p className="text-sm text-muted-foreground max-w-sm mx-auto">
              No alerts detected for the selected date range. All metrics are within healthy thresholds.
            </p>
          </motion.div>
        ) : filteredAlerts.length === 0 ? (
          /* No results after filtering */
          <div className="rounded-xl border border-dashed border-border bg-card py-16 text-center">
            <Bell className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
            <h3 className="text-base font-semibold mb-1">No matching alerts</h3>
            <p className="text-sm text-muted-foreground">
              Try clearing filters or adjusting your search query.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {filteredAlerts.map((alert, i) => (
              <AlertCard
                key={alert.id}
                alert={alert}
                onClick={setSelectedAlert}
                index={i}
              />
            ))}
          </div>
        )}
      </div>

      {/* Detail modal */}
      <AlertDetailModal
        alert={selectedAlert}
        onClose={() => setSelectedAlert(null)}
      />
    </>
  );
}
