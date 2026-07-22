// ─── Alert Type Definitions ───────────────────────────────────────────────────
// Central type file for the GAM 360 alert engine.
// All alert-related interfaces and enums live here.

export type AlertSeverity = "critical" | "high" | "medium" | "low";

export type AlertCategory =
  | "revenue"
  | "impressions"
  | "ctr"
  | "fill_rate"
  | "ecpm"
  | "requests"
  | "clicks"
  | "match_rate"
  | "users"
  | "error";

export type AlertDirection = "drop" | "spike" | "zero" | "threshold";

export interface Alert {
  /** Unique identifier */
  id: string;
  /** Short headline e.g. "Revenue dropped 42%" */
  title: string;
  /** App/ad-unit name, or "Network" for network-level alerts */
  appName: string;
  category: AlertCategory;
  severity: AlertSeverity;
  /** Human-readable metric name e.g. "Revenue (USD)" */
  metric: string;
  /** Raw numeric current value */
  currentValue: number;
  /** Formatted current value e.g. "$920.00" */
  currentFormatted: string;
  /** Raw numeric expected/reference value */
  expectedValue: number;
  /** Formatted expected value e.g. "$1,600.00" */
  expectedFormatted: string;
  /** Percentage change — negative = drop, positive = spike */
  changePct: number;
  /** Direction of alert */
  direction: AlertDirection;
  /** One-line explanation of why this alert fired */
  reason: string;
  /** One-line suggested immediate action */
  suggestedAction: string;
  /** 3–5 AI-generated recommendation bullet points */
  aiRecommendations: string[];
  /** ISO timestamp when the alert was generated */
  generatedAt: string;
}

// ─── Summary Counts ──────────────────────────────────────────────────────────

export interface AlertSummary {
  total: number;
  critical: number;
  high: number;
  medium: number;
  low: number;
  byCategory: Record<AlertCategory, number>;
}
