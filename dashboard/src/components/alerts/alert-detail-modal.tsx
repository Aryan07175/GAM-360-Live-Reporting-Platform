"use client";

import { motion, AnimatePresence } from "framer-motion";
import {
  X, AlertCircle, AlertTriangle, Info, TrendingDown, TrendingUp,
  CheckCircle, ArrowRight, BarChart2, DollarSign, Activity,
  Eye, Percent, Wifi, MousePointer, WifiOff,
} from "lucide-react";
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

const SEVERITY_LABELS: Record<AlertSeverity, string> = {
  critical: "Critical",
  high: "High",
  medium: "Medium",
  low: "Low",
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

interface AlertDetailModalProps {
  alert: Alert | null;
  onClose: () => void;
}

export function AlertDetailModal({ alert, onClose }: AlertDetailModalProps) {
  return (
    <AnimatePresence>
      {alert && (
        <>
          {/* Backdrop */}
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            onClick={onClose}
            className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm"
          />

          {/* Modal */}
          <motion.div
            key="modal"
            initial={{ opacity: 0, y: 40, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.97 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className={cn(
              "fixed inset-x-4 top-[5%] z-50 mx-auto max-w-2xl",
              "max-h-[90vh] overflow-y-auto",
              "rounded-2xl border border-border bg-card shadow-2xl"
            )}
          >
            <ModalContent alert={alert} onClose={onClose} />
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

function ModalContent({ alert, onClose }: { alert: Alert; onClose: () => void }) {
  const colors = severityColors(alert.severity);
  const SeverityIcon = SEVERITY_ICONS[alert.severity];
  const CategoryIcon = CATEGORY_ICONS[alert.category] ?? Activity;
  const isDrop = alert.changePct < 0;

  return (
    <div>
      {/* Header */}
      <div className={cn("px-6 pt-6 pb-4 border-b border-border border-l-4 rounded-t-2xl", colors.border)}>
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className={cn("rounded-xl p-3 flex-shrink-0", colors.iconBg)}>
              <SeverityIcon className={cn("h-6 w-6", colors.icon)} />
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap mb-1">
                <span className={cn(
                  "text-[11px] font-bold px-2 py-0.5 rounded-full border uppercase tracking-wide",
                  colors.badge
                )}>
                  {SEVERITY_LABELS[alert.severity]}
                </span>
                <span className="text-[11px] text-muted-foreground font-medium border border-border rounded-full px-2 py-0.5">
                  <CategoryIcon className="inline h-3 w-3 mr-1" />
                  {CATEGORY_LABELS[alert.category]}
                </span>
              </div>
              <h2 className="text-lg font-bold text-foreground break-words [overflow-wrap:anywhere]">
                {alert.title}
              </h2>
              <p className="text-sm text-muted-foreground mt-0.5">
                {alert.appName !== "All Networks" && alert.appName !== "System"
                  ? `Application: ${alert.appName}`
                  : alert.appName}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="flex-shrink-0 rounded-lg p-2 hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
      </div>

      <div className="p-6 space-y-6">
        {/* Metrics comparison */}
        <div className="grid grid-cols-3 gap-3">
          <div className="rounded-xl bg-muted/50 p-4">
            <p className="text-xs text-muted-foreground mb-1">Current Value</p>
            <p className="text-xl font-bold text-foreground">{alert.currentFormatted}</p>
            <p className="text-xs text-muted-foreground mt-1">{alert.metric}</p>
          </div>
          <div className="rounded-xl bg-muted/50 p-4">
            <p className="text-xs text-muted-foreground mb-1">Expected Value</p>
            <p className="text-xl font-bold text-foreground">{alert.expectedFormatted}</p>
            <p className="text-xs text-muted-foreground mt-1">Baseline / Threshold</p>
          </div>
          <div className={cn(
            "rounded-xl p-4",
            isDrop ? "bg-rose-500/8 border border-rose-500/20" : "bg-emerald-500/8 border border-emerald-500/20"
          )}>
            <p className="text-xs text-muted-foreground mb-1">Difference</p>
            <div className="flex items-center gap-1">
              {isDrop
                ? <TrendingDown className="h-5 w-5 text-rose-500" />
                : <TrendingUp className="h-5 w-5 text-emerald-500" />}
              <p className={cn(
                "text-xl font-bold",
                isDrop ? "text-rose-600" : "text-emerald-600"
              )}>
                {alert.changePct > 0 ? "+" : ""}{alert.changePct.toFixed(1)}%
              </p>
            </div>
            <p className="text-xs text-muted-foreground mt-1">{timeAgo(alert.generatedAt)}</p>
          </div>
        </div>

        {/* Reason */}
        <div className="rounded-xl border border-amber-400/30 bg-amber-400/5 p-4">
          <h3 className="text-sm font-semibold text-foreground mb-2 flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-amber-500" />
            Why this alert fired
          </h3>
          <p className="text-sm text-muted-foreground leading-relaxed">{alert.reason}</p>
        </div>

        {/* Suggested immediate action */}
        <div className="rounded-xl border border-blue-400/30 bg-blue-400/5 p-4">
          <h3 className="text-sm font-semibold text-foreground mb-2 flex items-center gap-2">
            <ArrowRight className="h-4 w-4 text-blue-500" />
            Suggested Action
          </h3>
          <p className="text-sm text-muted-foreground leading-relaxed">{alert.suggestedAction}</p>
        </div>

        {/* AI Recommendations */}
        <div className="rounded-xl border border-indigo-500/20 bg-indigo-500/5 p-4">
          <h3 className="text-sm font-semibold text-foreground mb-3 flex items-center gap-2">
            <Activity className="h-4 w-4 text-indigo-500" />
            AI Recommendations
          </h3>
          <ul className="space-y-2">
            {alert.aiRecommendations.map((rec, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-muted-foreground">
                <CheckCircle className="h-4 w-4 text-indigo-500 flex-shrink-0 mt-0.5" />
                <span className="break-words [overflow-wrap:anywhere]">{rec}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Affected metric details */}
        <div className="rounded-xl border border-border bg-muted/30 p-4">
          <h3 className="text-sm font-semibold text-foreground mb-3">Affected Metric</h3>
          <div className="flex items-center gap-3 text-sm">
            <CategoryIcon className="h-5 w-5 text-muted-foreground flex-shrink-0" />
            <div>
              <p className="font-medium text-foreground">{alert.metric}</p>
              <p className="text-xs text-muted-foreground">
                Category: {CATEGORY_LABELS[alert.category]} · Alert generated {timeAgo(alert.generatedAt)}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
