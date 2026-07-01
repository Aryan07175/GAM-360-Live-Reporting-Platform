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
  History,
  Bell
} from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { name: "Dashboard", href: "/", icon: LayoutDashboard },
  { name: "Applications", href: "/applications", icon: AppWindow },
  { name: "Revenue Analytics", href: "/revenue", icon: BarChart3 },
  { name: "Trend Analysis", href: "/trends", icon: TrendingUp },
  { name: "Anomaly Detection", href: "/anomalies", icon: AlertTriangle },
  { name: "Alerts", href: "/alerts", icon: Bell },
  { name: "Reports", href: "/reports", icon: FileText },
  { name: "Report History", href: "/history", icon: History },
  { name: "Settings", href: "/settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <div className="flex h-screen w-64 flex-col border-r bg-card px-4 py-6 shadow-sm">
      <div className="mb-8 flex items-center space-x-2 px-2">
        <div className="h-8 w-8 rounded-lg bg-primary flex items-center justify-center">
          <BarChart3 className="h-5 w-5 text-primary-foreground" />
        </div>
        <span className="text-lg font-bold tracking-tight">GAM 360</span>
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
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground"
              )}
            >
              <item.icon
                className={cn(
                  "mr-3 h-5 w-5 flex-shrink-0 transition-colors",
                  isActive ? "text-primary" : "text-muted-foreground group-hover:text-foreground"
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
            <div className="h-2 w-2 rounded-full bg-green-500" />
            <span className="text-xs font-medium">Connected to GAM</span>
          </div>
          <p className="mt-1 text-[10px] text-muted-foreground">Last sync: 5m ago</p>
        </div>
      </div>
    </div>
  );
}
