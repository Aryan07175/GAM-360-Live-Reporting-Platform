"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  BarChart3,
  AppWindow,
  FileText,
  AlertTriangle,
  Settings,
  TrendingUp,
  Bell,
  Zap,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useLiveReport } from "@/contexts/DateContext";

const navItems = [
  { name: "Dashboard", href: "/", icon: LayoutDashboard },
  { name: "Applications", href: "/applications", icon: AppWindow },
  { name: "Revenue Analytics", href: "/revenue", icon: BarChart3 },
  { name: "Trend Analysis", href: "/trends", icon: TrendingUp },
  { name: "Anomaly Detection", href: "/anomalies", icon: AlertTriangle },
  { name: "Alerts", href: "/alerts", icon: Bell },
  { name: "Reports", href: "/reports", icon: FileText },
  { name: "Settings", href: "/settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const { isLoading, lastFetchedAt } = useLiveReport();

  const getTimeAgo = (iso: string): string => {
    const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
    if (diff < 60) return `${diff}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    return `${Math.floor(diff / 3600)}h ago`;
  };

  return (
    <div className="flex h-screen w-64 flex-col border-r bg-card px-4 py-6 shadow-sm">
      <div className="mb-8 flex items-center space-x-2 px-2">
        <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center">
          <Zap className="h-5 w-5 text-white" />
        </div>
        <div>
          <span className="text-lg font-bold tracking-tight">GAM 360</span>
          <span className="ml-1.5 text-[9px] font-semibold text-indigo-500 bg-indigo-500/10 px-1.5 py-0.5 rounded-full uppercase">
            Live
          </span>
        </div>
      </div>

      <nav className="flex-1 space-y-1">
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                "group flex items-center rounded-md px-3 py-2 text-sm font-medium transition-all duration-200",
                isActive
                  ? "bg-indigo-500/10 text-indigo-600 dark:text-indigo-400"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground"
              )}
            >
              <item.icon
                className={cn(
                  "mr-3 h-5 w-5 flex-shrink-0 transition-colors",
                  isActive
                    ? "text-indigo-500"
                    : "text-muted-foreground group-hover:text-foreground"
                )}
              />
              <span className="flex-1">{item.name}</span>
              {item.name === "Alerts" && (
                <span className="h-1.5 w-1.5 rounded-full bg-red-500 mr-1" />
              )}
            </Link>
          );
        })}
      </nav>

      <div className="mt-auto px-2">
        <div className="rounded-lg border bg-muted/50 p-4">
          <div className="flex items-center space-x-2">
            <div
              className={`h-2 w-2 rounded-full ${
                isLoading
                  ? "bg-indigo-500 animate-pulse"
                  : lastFetchedAt
                  ? "bg-green-500"
                  : "bg-muted-foreground/40"
              }`}
            />
            <span className="text-xs font-medium">
              {isLoading
                ? "Fetching Live Data..."
                : lastFetchedAt
                ? "Connected to GAM"
                : "Ready"}
            </span>
          </div>
          <p className="mt-1 text-[10px] text-muted-foreground">
            {lastFetchedAt
              ? `Last fetch: ${getTimeAgo(lastFetchedAt)}`
              : "No data fetched yet"}
          </p>
          <p className="mt-0.5 text-[10px] text-muted-foreground/60">
            All data is live from Google Ad Manager
          </p>
        </div>
      </div>
    </div>
  );
}
