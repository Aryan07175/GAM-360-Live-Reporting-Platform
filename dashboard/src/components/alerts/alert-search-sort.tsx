"use client";

import { Search, ArrowUpDown } from "lucide-react";
import { cn } from "@/lib/utils";

export type SortOption =
  | "newest"
  | "oldest"
  | "severity"
  | "app_name"
  | "largest_drop"
  | "largest_increase";

const SORT_OPTIONS: { key: SortOption; label: string }[] = [
  { key: "severity", label: "Severity" },
  { key: "newest", label: "Newest" },
  { key: "oldest", label: "Oldest" },
  { key: "largest_drop", label: "Largest Drop" },
  { key: "largest_increase", label: "Largest Increase" },
  { key: "app_name", label: "App Name" },
];

interface AlertSearchSortProps {
  search: string;
  sort: SortOption;
  onSearchChange: (v: string) => void;
  onSortChange: (v: SortOption) => void;
  resultCount: number;
  totalCount: number;
}

export function AlertSearchSort({
  search,
  sort,
  onSearchChange,
  onSortChange,
  resultCount,
  totalCount,
}: AlertSearchSortProps) {
  return (
    <div className="flex items-center gap-3 flex-wrap">
      {/* Search */}
      <div className="relative flex-1 min-w-[200px]">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
        <input
          type="text"
          placeholder="Search by app, metric, or alert type..."
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          className={cn(
            "w-full pl-9 pr-4 py-2 text-sm rounded-lg",
            "bg-muted/50 border border-border",
            "placeholder:text-muted-foreground/60",
            "focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500/50",
            "transition-all duration-150"
          )}
        />
      </div>

      {/* Sort */}
      <div className="flex items-center gap-2">
        <ArrowUpDown className="h-4 w-4 text-muted-foreground flex-shrink-0" />
        <select
          value={sort}
          onChange={(e) => onSortChange(e.target.value as SortOption)}
          className={cn(
            "text-sm rounded-lg px-3 py-2 pr-8",
            "bg-muted/50 border border-border",
            "focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500/50",
            "transition-all duration-150 cursor-pointer"
          )}
        >
          {SORT_OPTIONS.map(({ key, label }) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </select>
      </div>

      {/* Result count */}
      <p className="text-xs text-muted-foreground flex-shrink-0">
        {resultCount === totalCount
          ? `${totalCount} alert${totalCount !== 1 ? "s" : ""}`
          : `${resultCount} of ${totalCount}`}
      </p>
    </div>
  );
}
