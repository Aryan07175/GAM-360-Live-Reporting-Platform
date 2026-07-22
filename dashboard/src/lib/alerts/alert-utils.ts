// ─── Alert Utility Functions ──────────────────────────────────────────────────

/**
 * Formatting helpers for alert values.
 */
export const fmt = {
  usd: (v: number) =>
    new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(v),
  pct: (v: number) => `${v.toFixed(2)}%`,
  num: (v: number) => new Intl.NumberFormat("en-US").format(Math.round(v)),
  ecpm: (v: number) => `$${v.toFixed(3)}`,
};

/**
 * Returns a human-readable "X minutes ago" string from an ISO timestamp.
 */
export function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const diffSec = Math.floor(diffMs / 1000);
  if (diffSec < 60) return "just now";
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin} minute${diffMin !== 1 ? "s" : ""} ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr} hour${diffHr !== 1 ? "s" : ""} ago`;
  const diffDay = Math.floor(diffHr / 24);
  return `${diffDay} day${diffDay !== 1 ? "s" : ""} ago`;
}

/**
 * Computes a percentage change between current and previous.
 * Returns 0 if previous is 0 to avoid division by zero.
 */
export function pctChange(current: number, previous: number): number {
  if (previous === 0) return current > 0 ? 100 : 0;
  return ((current - previous) / Math.abs(previous)) * 100;
}

/**
 * Returns the severity color classes for a given severity level.
 */
export function severityColors(severity: "critical" | "high" | "medium" | "low") {
  switch (severity) {
    case "critical":
      return {
        border: "border-l-rose-500",
        badge: "bg-rose-500/10 text-rose-600 border-rose-500/30",
        icon: "text-rose-500",
        iconBg: "bg-rose-500/10",
        dot: "bg-rose-500",
        ring: "ring-rose-500/20",
      };
    case "high":
      return {
        border: "border-l-orange-500",
        badge: "bg-orange-500/10 text-orange-600 border-orange-500/30",
        icon: "text-orange-500",
        iconBg: "bg-orange-500/10",
        dot: "bg-orange-500",
        ring: "ring-orange-500/20",
      };
    case "medium":
      return {
        border: "border-l-amber-400",
        badge: "bg-amber-400/10 text-amber-600 border-amber-400/30",
        icon: "text-amber-500",
        iconBg: "bg-amber-400/10",
        dot: "bg-amber-400",
        ring: "ring-amber-400/20",
      };
    case "low":
      return {
        border: "border-l-blue-400",
        badge: "bg-blue-400/10 text-blue-600 border-blue-400/30",
        icon: "text-blue-400",
        iconBg: "bg-blue-400/10",
        dot: "bg-blue-400",
        ring: "ring-blue-400/20",
      };
  }
}

/**
 * Maps AlertCategory to a display label.
 */
export const CATEGORY_LABELS: Record<string, string> = {
  revenue: "Revenue",
  impressions: "Impressions",
  ctr: "CTR",
  fill_rate: "Fill Rate",
  ecpm: "eCPM",
  requests: "Requests",
  clicks: "Clicks",
  match_rate: "Match Rate",
  users: "Users",
  error: "Error",
};

/**
 * Maps AlertSeverity to a display label.
 */
export const SEVERITY_LABELS: Record<string, string> = {
  critical: "Critical",
  high: "High",
  medium: "Medium",
  low: "Low",
};
