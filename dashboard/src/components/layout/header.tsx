"use client";

import { useState } from "react";
import { useTheme } from "next-themes";
import {
  Moon, Sun, User, RefreshCw, Download, Bell,
  ChevronDown, Calendar, Zap,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { format, parseISO } from "date-fns";
import { Button } from "@/components/ui/button";
import { LiveStatusIndicator } from "@/components/live/live-status-indicator";
import { useLiveReport } from "@/contexts/DateContext";
import { exportToCSV, exportToExcel, exportToMarkdown, exportToPDF } from "@/services/export-service";
import type { DatePreset } from "@/types";

const DATE_PRESETS: { value: DatePreset; label: string }[] = [
  { value: "today", label: "Today" },
  { value: "yesterday", label: "Yesterday" },
  { value: "last7days", label: "Last 7 Days" },
  { value: "last30days", label: "Last 30 Days" },
  { value: "thisMonth", label: "This Month" },
  { value: "lastMonth", label: "Last Month" },
  { value: "custom", label: "Custom Range" },
];

export function Header() {
  const { setTheme, theme } = useTheme();
  const router = useRouter();
  const {
    datePreset,
    startDate,
    endDate,
    startTime,
    endTime,
    setDatePreset,
    setCustomRange,
    isLoading,
    lastFetchedAt,
    error,
    refresh,
    reportData,
    demandChannel,
    setDemandChannel,
  } = useLiveReport();

  const [showDatePicker, setShowDatePicker] = useState(false);
  const [showDemandPicker, setShowDemandPicker] = useState(false);
  const [showExport, setShowExport] = useState(false);
  const [customStart, setCustomStart] = useState(startDate);
  const [customEnd, setCustomEnd] = useState(endDate);
  const [customSTime, setCustomSTime] = useState(startTime || "00:00");
  const [customETime, setCustomETime] = useState(endTime || "23:59");

  const presetLabel = DATE_PRESETS.find((p) => p.value === datePreset)?.label || "Select Date";

  const displayRange =
    startDate === endDate
      ? `${format(parseISO(startDate), "MMM dd, yyyy")} ${startTime !== "00:00" || endTime !== "23:59" ? `(${startTime} - ${endTime})` : ""}`
      : `${format(parseISO(startDate), "MMM dd")} → ${format(parseISO(endDate), "MMM dd, yyyy")}`;

  return (
    <header className="flex h-16 shrink-0 items-center justify-between border-b bg-background px-6 shadow-sm">
      {/* Left */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <Zap className="h-5 w-5 text-indigo-500" />
          <h1 className="text-lg font-semibold tracking-tight hidden md:block">
            GAM 360 Live Analytics
          </h1>
        </div>
        <LiveStatusIndicator
          isLoading={isLoading}
          lastFetchedAt={lastFetchedAt}
          error={error}
        />
      </div>

      {/* Right */}
      <div className="flex items-center gap-2">
        {/* Date Preset Selector */}
        <div className="relative">
          <Button
            variant="outline"
            size="sm"
            className="h-9 min-w-[200px] justify-between gap-2 font-medium"
            onClick={() => setShowDatePicker((v) => !v)}
          >
            <Calendar className="h-4 w-4 text-muted-foreground" />
            <span className="flex-1 text-left truncate">
              {presetLabel}: {displayRange}
            </span>
            <ChevronDown className="h-3 w-3 text-muted-foreground" />
          </Button>

          {showDatePicker && (
            <>
              <div
                className="fixed inset-0 z-40"
                onClick={() => setShowDatePicker(false)}
              />
              <div className="absolute right-0 top-11 z-50 bg-background border rounded-xl shadow-xl p-4 w-80 animate-in fade-in slide-in-from-top-2 duration-200">
                <p className="text-xs text-muted-foreground font-medium mb-3 uppercase tracking-wider">
                  Date Range
                </p>

                {/* Presets */}
                <div className="space-y-1 mb-4">
                  {DATE_PRESETS.filter((p) => p.value !== "custom").map(
                    (preset) => (
                      <button
                        key={preset.value}
                        className={`w-full text-left text-sm px-3 py-2 rounded-md transition-colors hover:bg-muted flex items-center justify-between ${
                          datePreset === preset.value
                            ? "bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 font-medium"
                            : "text-foreground"
                        }`}
                        onClick={() => {
                          setDatePreset(preset.value);
                          setShowDatePicker(false);
                        }}
                      >
                        {preset.label}
                        {datePreset === preset.value && (
                          <span className="h-1.5 w-1.5 rounded-full bg-indigo-500" />
                        )}
                      </button>
                    )
                  )}
                </div>

                {/* Custom Range */}
                <div className="border-t pt-3 space-y-2">
                  <p className="text-xs text-muted-foreground font-medium uppercase tracking-wider">
                    Custom Range
                  </p>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="text-[10px] text-muted-foreground">Start Date</label>
                      <input
                        type="date"
                        className="w-full rounded-md border bg-background px-2 py-1.5 text-xs ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring cursor-pointer"
                        value={customStart}
                        onChange={(e) => setCustomStart(e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="text-[10px] text-muted-foreground">End Date</label>
                      <input
                        type="date"
                        className="w-full rounded-md border bg-background px-2 py-1.5 text-xs ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring cursor-pointer"
                        value={customEnd}
                        onChange={(e) => setCustomEnd(e.target.value)}
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="text-[10px] text-muted-foreground">Start Time</label>
                      <input
                        type="time"
                        className="w-full rounded-md border bg-background px-2 py-1.5 text-xs ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring cursor-pointer"
                        value={customSTime}
                        onChange={(e) => setCustomSTime(e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="text-[10px] text-muted-foreground">End Time</label>
                      <input
                        type="time"
                        className="w-full rounded-md border bg-background px-2 py-1.5 text-xs ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring cursor-pointer"
                        value={customETime}
                        onChange={(e) => setCustomETime(e.target.value)}
                      />
                    </div>
                  </div>
                  <Button
                    size="sm"
                    className="w-full bg-indigo-600 hover:bg-indigo-700 text-white text-xs mt-2"
                    onClick={() => {
                      if (customStart && customEnd) {
                        setCustomRange(customStart, customEnd, customSTime, customETime);
                        setShowDatePicker(false);
                      }
                    }}
                  >
                    Apply Custom Range
                  </Button>
                </div>
              </div>
            </>
          )}
        </div>

        {/* Demand Channel Filter */}
        <div className="relative">
          <Button
            variant="outline"
            size="sm"
            className="h-9 gap-2"
            onClick={() => setShowDemandPicker((v) => !v)}
          >
            <span className="font-medium text-muted-foreground">Channel:</span>
            <span>{demandChannel === "all" ? "Total Network" : "Programmatic Only"}</span>
            <ChevronDown className="h-3 w-3 text-muted-foreground" />
          </Button>

          {showDemandPicker && (
            <>
              <div
                className="fixed inset-0 z-40"
                onClick={() => setShowDemandPicker(false)}
              />
              <div className="absolute right-0 top-11 z-50 bg-background border rounded-lg shadow-xl py-1 w-48 animate-in fade-in slide-in-from-top-2 duration-200">
                <button
                  className={`w-full text-left text-sm px-3 py-2 transition-colors ${
                    demandChannel === "all" ? "bg-muted font-medium" : "hover:bg-muted"
                  }`}
                  onClick={() => {
                    setDemandChannel("all");
                    setShowDemandPicker(false);
                  }}
                >
                  Total Network (All)
                </button>
                <button
                  className={`w-full text-left text-sm px-3 py-2 transition-colors ${
                    demandChannel === "programmatic" ? "bg-muted font-medium" : "hover:bg-muted"
                  }`}
                  onClick={() => {
                    setDemandChannel("programmatic");
                    setShowDemandPicker(false);
                  }}
                >
                  Programmatic Only
                </button>
              </div>
            </>
          )}
        </div>

        {/* Refresh */}
        <Button
          variant="outline"
          size="sm"
          className={`h-9 gap-2 ${isLoading ? "opacity-60" : ""}`}
          onClick={refresh}
          disabled={isLoading}
          title="Fetch fresh data from Google Ad Manager"
        >
          <RefreshCw
            className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`}
          />
          <span className="hidden sm:inline">
            {isLoading ? "Fetching..." : "Refresh"}
          </span>
        </Button>

        {/* Export Dropdown */}
        <div className="relative">
          <Button
            variant="outline"
            size="sm"
            className="h-9 gap-2"
            onClick={() => setShowExport((v) => !v)}
            disabled={!reportData}
          >
            <Download className="h-4 w-4" />
            <span className="hidden sm:inline">Export</span>
          </Button>

          {showExport && reportData && (
            <>
              <div
                className="fixed inset-0 z-40"
                onClick={() => setShowExport(false)}
              />
              <div className="absolute right-0 top-11 z-50 bg-background border rounded-lg shadow-xl py-1 w-40 animate-in fade-in slide-in-from-top-2 duration-200">
                {[
                  { label: "CSV", fn: () => exportToCSV(reportData) },
                  { label: "Excel", fn: () => exportToExcel(reportData) },
                  { label: "Markdown", fn: () => exportToMarkdown(reportData) },
                  { label: "PDF (Print)", fn: () => exportToPDF() },
                ].map((item) => (
                  <button
                    key={item.label}
                    className="w-full text-left text-sm px-3 py-2 hover:bg-muted transition-colors"
                    onClick={() => {
                      item.fn();
                      setShowExport(false);
                    }}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </>
          )}
        </div>

        {/* Theme Toggle */}
        <Button
          variant="ghost"
          size="icon"
          className="h-9 w-9 rounded-full"
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
        >
          <Sun className="h-[1.2rem] w-[1.2rem] rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
          <Moon className="absolute h-[1.2rem] w-[1.2rem] rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
          <span className="sr-only">Toggle theme</span>
        </Button>

        {/* Alerts */}
        <Button
          variant="ghost"
          size="icon"
          className="relative h-9 w-9 rounded-full"
          onClick={() => router.push("/alerts")}
        >
          <Bell className="h-[1.2rem] w-[1.2rem]" />
          <span className="absolute top-2 right-2 h-2 w-2 rounded-full bg-red-600 border-2 border-background" />
          <span className="sr-only">View alerts</span>
        </Button>

        {/* User */}
        <Button
          variant="ghost"
          size="icon"
          className="h-9 w-9 rounded-full bg-muted"
        >
          <User className="h-4 w-4" />
        </Button>
      </div>
    </header>
  );
}
