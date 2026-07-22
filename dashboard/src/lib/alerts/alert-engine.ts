// ─── Alert Engine ─────────────────────────────────────────────────────────────
// Orchestrates all rule sets and returns a deduplicated, sorted Alert[].

import type { Alert, AlertCategory, AlertSummary } from "./alert-types";
import type { BIAppRow, BIAnomaly, BISummaryKPI, BIDailyPoint } from "@/types";
import { generateRevenueAlerts } from "./rules/revenue-rules";
import { generateImpressionAlerts } from "./rules/impression-rules";
import { generateCTRAlerts } from "./rules/ctr-rules";
import { generateFillRateAlerts } from "./rules/fill-rate-rules";
import { generateEcpmAlerts } from "./rules/ecpm-rules";
import { generateRequestAlerts } from "./rules/request-rules";
import { generateClickAlerts } from "./rules/click-rules";
import { generateMatchRateAlerts } from "./rules/match-rate-rules";
import { generateErrorAlerts } from "./rules/error-rules";

export interface AlertEngineInput {
  apps: BIAppRow[];
  trend: BIDailyPoint[];
  summary: BISummaryKPI[];
  anomalies: BIAnomaly[];
  error: string | null;
}

const SEVERITY_ORDER: Record<string, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
};

/**
 * Runs all rule sets and returns deduplicated, severity-sorted alerts.
 */
export function runAlertEngine(input: AlertEngineInput): Alert[] {
  const { apps, summary, anomalies, error } = input;

  const allAlerts: Alert[] = [
    ...generateErrorAlerts(error),
    ...generateRevenueAlerts(apps, anomalies, summary),
    ...generateImpressionAlerts(apps, anomalies, summary),
    ...generateCTRAlerts(apps),
    ...generateFillRateAlerts(apps),
    ...generateEcpmAlerts(apps, anomalies),
    ...generateRequestAlerts(apps, anomalies, summary),
    ...generateClickAlerts(apps, anomalies),
    ...generateMatchRateAlerts(anomalies),
  ];

  // Deduplication: for same (appName + category), keep only the highest severity
  const deduped = deduplicateAlerts(allAlerts);

  // Sort: severity first, then by absolute changePct magnitude
  return deduped.sort((a, b) => {
    const sevDiff = SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity];
    if (sevDiff !== 0) return sevDiff;
    return Math.abs(b.changePct) - Math.abs(a.changePct);
  });
}

function deduplicateAlerts(alerts: Alert[]): Alert[] {
  const seen = new Map<string, Alert>();

  for (const alert of alerts) {
    // For network-level (appName = "All Networks"), don't deduplicate — each is unique
    const key = alert.appName === "All Networks" || alert.appName === "System"
      ? alert.id
      : `${alert.appName}::${alert.category}`;

    const existing = seen.get(key);
    if (!existing) {
      seen.set(key, alert);
    } else {
      // Keep the one with higher severity (lower order number)
      if (SEVERITY_ORDER[alert.severity] < SEVERITY_ORDER[existing.severity]) {
        seen.set(key, alert);
      }
    }
  }

  return Array.from(seen.values());
}

/**
 * Computes alert summary counts from an Alert[].
 */
export function computeAlertSummary(alerts: Alert[]): AlertSummary {
  const byCategory = {} as Record<AlertCategory, number>;
  const categories: AlertCategory[] = [
    "revenue", "impressions", "ctr", "fill_rate", "ecpm",
    "requests", "clicks", "match_rate", "users", "error",
  ];
  for (const cat of categories) byCategory[cat] = 0;

  for (const alert of alerts) {
    byCategory[alert.category] = (byCategory[alert.category] || 0) + 1;
  }

  return {
    total: alerts.length,
    critical: alerts.filter((a) => a.severity === "critical").length,
    high: alerts.filter((a) => a.severity === "high").length,
    medium: alerts.filter((a) => a.severity === "medium").length,
    low: alerts.filter((a) => a.severity === "low").length,
    byCategory,
  };
}

