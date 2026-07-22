"use client";

import { motion } from "framer-motion";
import {
  AlertCircle, AlertTriangle, Info, TrendingDown, TrendingUp,
  DollarSign, Eye, Activity, Wifi, WifiOff, ChevronRight,
  BarChart2, MousePointer, Percent,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { Alert, AlertCategory, AlertSeverity } from "@/lib/alerts/alert-types";
import { severityColors, CATEGORY_LABELS, timeAgo } from "@/lib/alerts/alert-utils";

// ─── Icon Maps ────────────────────────────────────────────────────────────────

const SEVERITY_ICONS: Record<AlertSeverity, React.ComponentType<{ className?: string }>> = {
  critical: AlertCircle,
  high: AlertTriangle,
  medium: AlertTriangle,
  low: Info,
};

const CATEGORY_ICONS: Record<AlertCategory, React.ComponentType<{ className?: string }>> = {
  revenue: DollarSign,
  impressions: BarChart2,
  ctr: Eye,
  fill_rate: Percent,
  ecpm: Activity,
  requests: Wifi,
  clicks: MousePointer,
  match_rate: BarChart2,
  users: Activity,
  error: WifiOff,
};

// ─── Component ────────────────────────────────────────────────────────────────

interface AlertCardProps {
  alert: Alert;
  onClick: (alert: Alert) => void;
  index?: number;
}

export function AlertCard({ alert, onClick, index = 0 }: AlertCardProps) {
  const colors = severityColors(alert.severity);
  const SeverityIcon = SEVERITY_ICONS[alert.severity];
  const CategoryIcon = CATEGORY_ICONS[alert.category] ?? Activity;
  const isDrop = alert.changePct < 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, delay: index * 0.03 }}
    >
      <button
        onClick={() => onClick(alert)}
        className={cn(
          "w-full text-left group",
          "rounded-xl border border-border bg-card",
          "border-l-4 transition-all duration-200",
          "hover:shadow-md hover:border-border/80",
          "focus:outline-none focus:ring-2 focus:ring-offset-1",
          colors.border,
          colors.ring
        )}
      >
        <div className="p-4">
          {/* Top row: icon + title + category badge + chevron */}
          <div className="flex items-start gap-3">
            {/* Severity icon */}
            <div className={cn("flex-shrink-0 mt-0.5 rounded-lg p-2", colors.iconBg)}>
              <SeverityIcon className={cn("h-4 w-4", colors.icon)} />
            </div>

            {/* Title + meta */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <p className="text-sm font-semibold text-foreground break-words [overflow-wrap:anywhere]">
                  {alert.title}
                </p>
                {/* Severity badge */}
                <span className={cn(
                  "text-[10px] font-semibold px-1.5 py-0.5 rounded-full border uppercase tracking-wide",
                  colors.badge
                )}>
                  {alert.severity}
                </span>
              </div>

              {/* App name */}
              <p className="mt-0.5 text-xs text-muted-foreground truncate">
                {alert.appName !== "All Networks" && alert.appName !== "System"
                  ? `App: ${alert.appName}`
                  : alert.appName}
              </p>
            </div>

            {/* Category + chevron */}
            <div className="flex items-center gap-2 flex-shrink-0">
              <Badge variant="outline" className="text-[10px] hidden sm:inline-flex">
                <CategoryIcon className="h-3 w-3 mr-1" />
                {CATEGORY_LABELS[alert.category]}
              </Badge>
              <ChevronRight className="h-4 w-4 text-muted-foreground group-hover:text-foreground transition-colors" />
            </div>
          </div>

          {/* Metrics row */}
          <div className="mt-3 grid grid-cols-3 gap-3">
            {/* Current value */}
            <div className="rounded-lg bg-muted/50 px-3 py-2">
              <p className="text-[10px] text-muted-foreground mb-0.5">Current</p>
              <p className="text-sm font-bold text-foreground">{alert.currentFormatted}</p>
            </div>

            {/* Expected value */}
            <div className="rounded-lg bg-muted/50 px-3 py-2">
              <p className="text-[10px] text-muted-foreground mb-0.5">Expected</p>
              <p className="text-sm font-bold text-foreground">{alert.expectedFormatted}</p>
            </div>

            {/* Change % */}
            <div className={cn(
              "rounded-lg px-3 py-2 flex flex-col",
              isDrop ? "bg-rose-500/8" : "bg-emerald-500/8"
            )}>
              <p className="text-[10px] text-muted-foreground mb-0.5">Change</p>
              <div className="flex items-center gap-1">
                {isDrop
                  ? <TrendingDown className="h-3 w-3 text-rose-500 flex-shrink-0" />
                  : <TrendingUp className="h-3 w-3 text-emerald-500 flex-shrink-0" />}
                <p className={cn(
                  "text-sm font-bold",
                  isDrop ? "text-rose-600" : "text-emerald-600"
                )}>
                  {alert.changePct > 0 ? "+" : ""}{alert.changePct.toFixed(1)}%
                </p>
              </div>
            </div>
          </div>

          {/* Reason + action row */}
          <div className="mt-3 flex items-start gap-2 text-xs text-muted-foreground">
            <p className="flex-1 line-clamp-1">{alert.reason}</p>
            <p className="text-[10px] text-muted-foreground/60 flex-shrink-0 ml-2">
              {timeAgo(alert.generatedAt)}
            </p>
          </div>
        </div>
      </button>
    </motion.div>
  );
}
