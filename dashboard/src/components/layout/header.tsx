"use client";

import { useState } from "react";
import { useTheme } from "next-themes";
import {
  Moon, Sun, User, Calendar as CalendarIcon, RefreshCw,
  Download, Database, Bell, ChevronLeft, ChevronRight, AlertCircle,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { format, parseISO } from "date-fns";
import { Button } from "@/components/ui/button";
import { useDateContext } from "@/contexts/DateContext";

export function Header() {
  const { setTheme, theme } = useTheme();
  const router = useRouter();
  const {
    selectedDate, latestDate, availableDates, dateLoading,
    setSelectedDate, refresh, refreshing,
  } = useDateContext();
  const [showPicker, setShowPicker] = useState(false);

  const displayDate = selectedDate
    ? format(parseISO(selectedDate), "MMM dd, yyyy")
    : dateLoading
    ? "Loading..."
    : format(new Date(), "MMM dd, yyyy");

  const isLiveDate = selectedDate === latestDate && !!latestDate;
  const hasData = selectedDate ? availableDates.includes(selectedDate) : false;

  // Navigate to the previous date that actually has data
  const goToPrevDay = () => {
    if (!selectedDate || availableDates.length === 0) return;
    const sorted = [...availableDates].sort();
    const idx = sorted.indexOf(selectedDate);
    if (idx > 0) {
      setSelectedDate(sorted[idx - 1]);
    } else if (idx === -1) {
      // Current date isn't in available list — find nearest earlier date
      const earlier = sorted.filter((d) => d < selectedDate);
      if (earlier.length > 0) setSelectedDate(earlier[earlier.length - 1]);
    }
  };

  // Navigate to the next date that actually has data
  const goToNextDay = () => {
    if (!selectedDate || availableDates.length === 0) return;
    const sorted = [...availableDates].sort();
    const idx = sorted.indexOf(selectedDate);
    if (idx !== -1 && idx < sorted.length - 1) {
      setSelectedDate(sorted[idx + 1]);
    } else if (idx === -1) {
      // Current date isn't in available list — find nearest later date
      const later = sorted.filter((d) => d > selectedDate);
      if (later.length > 0) setSelectedDate(later[0]);
    }
  };

  const canGoNext = (() => {
    if (!selectedDate || availableDates.length === 0) return false;
    const sorted = [...availableDates].sort();
    const idx = sorted.indexOf(selectedDate);
    if (idx !== -1) return idx < sorted.length - 1;
    return sorted.some((d) => d > selectedDate);
  })();

  const canGoPrev = (() => {
    if (!selectedDate || availableDates.length === 0) return false;
    const sorted = [...availableDates].sort();
    const idx = sorted.indexOf(selectedDate);
    if (idx !== -1) return idx > 0;
    return sorted.some((d) => d < selectedDate);
  })();

  return (
    <header className="flex h-16 shrink-0 items-center justify-between border-b bg-background px-6 shadow-sm">
      <div className="flex items-center gap-4">
        <h1 className="text-xl font-semibold tracking-tight">Google Ad Manager 360 Analytics</h1>
        <div className="hidden h-5 w-px bg-border md:block" />
        <span className="hidden text-sm text-muted-foreground md:inline-block">Network: 22846411849</span>
      </div>

      <div className="flex items-center gap-3">
        {/* Date Selector */}
        <div className="hidden sm:flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={goToPrevDay}
            disabled={!canGoPrev}
            title="Previous date with data"
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>

          <div className="relative">
            <Button
              variant="outline"
              size="sm"
              className={`h-9 border-dashed min-w-[180px] font-medium ${
                !hasData && selectedDate
                  ? "border-amber-500/50 text-amber-600 dark:text-amber-400"
                  : isLiveDate
                  ? "border-emerald-500/50 text-emerald-600 dark:text-emerald-400"
                  : ""
              }`}
              title={
                !hasData && selectedDate
                  ? `No data for ${displayDate}. Click to select a date with data.`
                  : selectedDate
                  ? `Viewing data as of ${displayDate}. Click to change.`
                  : "Loading date..."
              }
              onClick={() => setShowPicker((v) => !v)}
            >
              {!hasData && selectedDate ? (
                <AlertCircle className="mr-2 h-4 w-4 text-amber-500" />
              ) : selectedDate ? (
                <Database className={`mr-2 h-4 w-4 ${isLiveDate ? "text-emerald-500" : "text-muted-foreground"}`} />
              ) : (
                <CalendarIcon className="mr-2 h-4 w-4" />
              )}
              {selectedDate ? `Data as of: ${displayDate}` : displayDate}
              {isLiveDate && (
                <span className="ml-2 inline-flex items-center rounded-full bg-emerald-100 dark:bg-emerald-900/40 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-700 dark:text-emerald-400">
                  LIVE
                </span>
              )}
              {!hasData && selectedDate && (
                <span className="ml-2 inline-flex items-center rounded-full bg-amber-100 dark:bg-amber-900/40 px-1.5 py-0.5 text-[10px] font-semibold text-amber-700 dark:text-amber-400">
                  NO DATA
                </span>
              )}
            </Button>

            {/* Date picker dropdown */}
            {showPicker && (
              <div className="absolute right-0 top-10 z-50 bg-background border rounded-xl shadow-xl p-4 w-72 animate-in fade-in slide-in-from-top-2 duration-200">
                <p className="text-xs text-muted-foreground font-medium mb-3 uppercase tracking-wider">Select Date</p>
                <input
                  type="date"
                  className="w-full rounded-md border bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring cursor-pointer"
                  value={selectedDate || ""}
                  max={latestDate || undefined}
                  onChange={(e) => {
                    if (e.target.value) {
                      setSelectedDate(e.target.value);
                      setShowPicker(false);
                    }
                  }}
                />

                {/* Available dates section */}
                {availableDates.length > 0 && (
                  <div className="mt-3">
                    <p className="text-xs text-muted-foreground mb-2 flex items-center gap-1">
                      <Database className="h-3 w-3" />
                      Dates with data ({availableDates.length}):
                    </p>
                    <div className="space-y-1 max-h-48 overflow-y-auto">
                      {[...availableDates].sort().reverse().map((date) => (
                        <button
                          key={date}
                          className={`w-full text-left text-sm px-3 py-1.5 rounded-md transition-colors hover:bg-muted flex items-center justify-between ${
                            selectedDate === date
                              ? "bg-muted font-medium text-foreground"
                              : "text-muted-foreground"
                          }`}
                          onClick={() => {
                            setSelectedDate(date);
                            setShowPicker(false);
                          }}
                        >
                          <span>{format(parseISO(date), "MMM dd, yyyy (EEE)")}</span>
                          {date === latestDate && (
                            <span className="text-[10px] font-semibold text-emerald-500 bg-emerald-500/10 px-1.5 py-0.5 rounded-full">
                              LATEST
                            </span>
                          )}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {availableDates.length === 0 && (
                  <p className="mt-3 text-xs text-muted-foreground text-center py-2">
                    No data found in database. Run the GAM pipeline to sync data.
                  </p>
                )}
              </div>
            )}
          </div>

          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={goToNextDay}
            disabled={!canGoNext}
            title="Next date with data"
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>

        {/* Close picker on outside click overlay */}
        {showPicker && (
          <div className="fixed inset-0 z-40" onClick={() => setShowPicker(false)} />
        )}

        <Button
          variant="outline"
          size="sm"
          className={`hidden sm:flex h-9 ${refreshing ? "opacity-60" : ""}`}
          onClick={refresh}
          disabled={refreshing}
          title="Refresh live data from database"
        >
          <RefreshCw className={`mr-2 h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
          {refreshing ? "Refreshing..." : "Refresh"}
        </Button>

        <Button
          size="sm"
          className="hidden sm:flex h-9 bg-indigo-600 hover:bg-indigo-700 text-white"
          onClick={() => {
            const url = selectedDate ? `/api/export?date=${selectedDate}` : "/api/export";
            window.location.href = url;
          }}
        >
          <Download className="mr-2 h-4 w-4" />
          Export CSV
        </Button>

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

        <Button
          variant="ghost"
          size="icon"
          className="relative h-9 w-9 rounded-full"
          onClick={() => router.push("/alerts")}
        >
          <Bell className="h-[1.2rem] w-[1.2rem]" />
          <span className="absolute top-2 right-2 h-2 w-2 rounded-full bg-red-600 border-2 border-background"></span>
          <span className="sr-only">View alerts</span>
        </Button>

        <Button variant="ghost" size="icon" className="h-9 w-9 rounded-full bg-muted">
          <User className="h-4 w-4" />
        </Button>
      </div>
    </header>
  );
}
