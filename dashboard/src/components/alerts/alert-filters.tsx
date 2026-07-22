"use client";

import { cn } from "@/lib/utils";
import { CATEGORY_LABELS } from "@/lib/alerts/alert-utils";
import type { AlertCategory, AlertSummary } from "@/lib/alerts/alert-types";

// ─── Types ────────────────────────────────────────────────────────────────────

export type FilterCategory = AlertCategory | "all";
export type FilterSeverity = "all" | "critical" | "high" | "medium" | "low";

interface AlertFiltersProps {
  activeCategory: FilterCategory;
  activeSeverity: FilterSeverity;
  summary: AlertSummary;
  onCategoryChange: (cat: FilterCategory) => void;
  onSeverityChange: (sev: FilterSeverity) => void;
}

// ─── Filter Config ────────────────────────────────────────────────────────────

const CATEGORY_FILTERS: { key: FilterCategory; label: string }[] = [
  { key: "all", label: "All" },
  { key: "revenue", label: "Revenue" },
  { key: "impressions", label: "Impressions" },
  { key: "ctr", label: "CTR" },
  { key: "fill_rate", label: "Fill Rate" },
  { key: "ecpm", label: "eCPM" },
  { key: "requests", label: "Requests" },
  { key: "clicks", label: "Clicks" },
  { key: "match_rate", label: "Match Rate" },
  { key: "error", label: "Errors" },
];

const SEVERITY_FILTERS: { key: FilterSeverity; label: string; color: string }[] = [
  { key: "all", label: "All Severity", color: "text-foreground" },
  { key: "critical", label: "Critical", color: "text-rose-600" },
  { key: "high", label: "High", color: "text-orange-600" },
  { key: "medium", label: "Medium", color: "text-amber-600" },
  { key: "low", label: "Low", color: "text-blue-600" },
];

// ─── Component ────────────────────────────────────────────────────────────────

export function AlertFilters({
  activeCategory,
  activeSeverity,
  summary,
  onCategoryChange,
  onSeverityChange,
}: AlertFiltersProps) {
  return (
    <div className="space-y-3">
      {/* Category filter pills */}
      <div className="flex items-center gap-1.5 flex-wrap">
        {CATEGORY_FILTERS.map(({ key, label }) => {
          const count =
            key === "all"
              ? summary.total
              : summary.byCategory[key as AlertCategory] ?? 0;
          const isActive = activeCategory === key;

          return (
            <button
              key={key}
              onClick={() => onCategoryChange(key)}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium",
                "border transition-all duration-150",
                isActive
                  ? "bg-indigo-500/10 border-indigo-500/40 text-indigo-600 dark:text-indigo-400"
                  : "bg-muted/50 border-border text-muted-foreground hover:text-foreground hover:bg-muted"
              )}
            >
              {label}
              {count > 0 && (
                <span className={cn(
                  "text-[9px] font-bold px-1 rounded-full",
                  isActive
                    ? "bg-indigo-500 text-white"
                    : "bg-muted-foreground/20 text-muted-foreground"
                )}>
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Severity filter pills */}
      <div className="flex items-center gap-1.5 flex-wrap">
        <span className="text-xs text-muted-foreground mr-1">Severity:</span>
        {SEVERITY_FILTERS.map(({ key, label, color }) => {
          const count =
            key === "all"
              ? summary.total
              : summary[key as Exclude<FilterSeverity, "all">] ?? 0;
          const isActive = activeSeverity === key;

          return (
            <button
              key={key}
              onClick={() => onSeverityChange(key)}
              className={cn(
                "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-medium",
                "border transition-all duration-150",
                isActive
                  ? `border-current bg-current/10 ${color}`
                  : "bg-muted/50 border-border text-muted-foreground hover:text-foreground"
              )}
            >
              {label}
              {count > 0 && (
                <span className="text-[9px] font-bold">({count})</span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
