"use client";

import { useTheme } from "next-themes";
import { Moon, Sun, User, Calendar as CalendarIcon, RefreshCw, Download, Database, Bell } from "lucide-react";
import { useRouter } from "next/navigation";
import { format, parseISO } from "date-fns";
import { Button } from "@/components/ui/button";

interface HeaderProps {
  /** The actual date the displayed data is from (from Postgres MAX(report_date)) */
  dataDate?: string | null;
}

export function Header({ dataDate }: HeaderProps) {
  const { setTheme, theme } = useTheme();
  const router = useRouter();

  const displayDate = dataDate
    ? format(parseISO(dataDate), "MMM dd, yyyy")
    : format(new Date(), "MMM dd, yyyy");

  return (
    <header className="flex h-16 shrink-0 items-center justify-between border-b bg-background px-6 shadow-sm">
      <div className="flex items-center gap-4">
        <h1 className="text-xl font-semibold tracking-tight">Google Ad Manager 360 Analytics</h1>
        <div className="hidden h-5 w-px bg-border md:block" />
        <span className="hidden text-sm text-muted-foreground md:inline-block">Network: 22846411849</span>
      </div>

      <div className="flex items-center gap-3">
        <Button variant="outline" size="sm" className="hidden sm:flex h-9 border-dashed" title={dataDate ? `Showing data as of ${displayDate}` : "Using today's date"}>
          {dataDate ? (
            <Database className="mr-2 h-4 w-4 text-emerald-500" />
          ) : (
            <CalendarIcon className="mr-2 h-4 w-4" />
          )}
          {dataDate ? `Data as of: ${displayDate}` : displayDate}
        </Button>
        
        <Button variant="outline" size="sm" className="hidden sm:flex h-9">
          <RefreshCw className="mr-2 h-4 w-4" />
          Refresh
        </Button>

        <Button 
          size="sm" 
          className="hidden sm:flex h-9 bg-indigo-600 hover:bg-indigo-700 text-white"
          onClick={() => {
            const url = dataDate ? `/api/export?date=${dataDate}` : "/api/export";
            window.location.href = url;
          }}
        >
          <Download className="mr-2 h-4 w-4" />
          Generate Report
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
