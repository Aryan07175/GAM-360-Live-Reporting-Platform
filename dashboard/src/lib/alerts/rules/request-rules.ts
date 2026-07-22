import type { Alert } from "../alert-types";
import { THRESHOLDS } from "../alert-thresholds";
import { getRecommendations } from "../alert-recommendations";
import type { BIAppRow, BIAnomaly, BISummaryKPI } from "@/types";
import { fmt } from "../alert-utils";

export function generateRequestAlerts(
  apps: BIAppRow[],
  anomalies: BIAnomaly[],
  summary: BISummaryKPI[]
): Alert[] {
  const alerts: Alert[] = [];
  const now = new Date().toISOString();
  const T = THRESHOLDS.requests;

  // ── 1. Network-level request change ─────────────────────────────────────
  const reqKPI = summary.find((k) =>
    k.label.toLowerCase().includes("request")
  );
  if (reqKPI && reqKPI.previousValue > 0 && reqKPI.changePct <= -T.dropPct) {
    alerts.push({
      id: `req-network-drop-${now}`,
      title: `Ad requests dropped ${Math.abs(reqKPI.changePct).toFixed(1)}% network-wide`,
      appName: "All Networks",
      category: "requests",
      severity: reqKPI.changePct <= -50 ? "high" : "medium",
      metric: "Total Ad Requests",
      currentValue: reqKPI.value,
      currentFormatted: fmt.num(reqKPI.value),
      expectedValue: reqKPI.previousValue,
      expectedFormatted: fmt.num(reqKPI.previousValue),
      changePct: reqKPI.changePct,
      direction: "drop",
      reason: `Total ad requests dropped ${Math.abs(reqKPI.changePct).toFixed(1)}% — user traffic or ad serving may be impacted.`,
      suggestedAction: "Check user session data and ad SDK health across all apps.",
      aiRecommendations: getRecommendations("requests", "drop"),
      generatedAt: now,
    });
  }

  // ── 2. Zero requests per app ─────────────────────────────────────────────
  for (const app of apps) {
    if (app.ad_requests === 0) {
      alerts.push({
        id: `req-zero-${app.ad_unit_id}-${now}`,
        title: `Zero ad requests from ${app.ad_unit_name}`,
        appName: app.ad_unit_name,
        category: "requests",
        severity: "critical",
        metric: "Ad Requests",
        currentValue: 0,
        currentFormatted: "0",
        expectedValue: 0,
        expectedFormatted: "—",
        changePct: -100,
        direction: "zero",
        reason: "No ad requests received from this app unit — SDK may not be initialized.",
        suggestedAction: "Check the ad SDK integration and app traffic for this unit.",
        aiRecommendations: getRecommendations("requests", "zero"),
        generatedAt: now,
      });
    }
  }

  // ── 3. Request anomalies ─────────────────────────────────────────────────
  const reqAnomalies = anomalies.filter((a) =>
    a.metric.toLowerCase().includes("request")
  );
  for (const anomaly of reqAnomalies) {
    if (Math.abs(anomaly.changePct) < T.dropPct) continue;
    const isDrop = anomaly.changePct < 0;
    alerts.push({
      id: `req-anomaly-${anomaly.id}-${now}`,
      title: isDrop
        ? `Requests dropped ${Math.abs(anomaly.changePct).toFixed(1)}% in ${anomaly.ad_unit_name}`
        : `Requests spiked ${anomaly.changePct.toFixed(1)}% in ${anomaly.ad_unit_name}`,
      appName: anomaly.ad_unit_name,
      category: "requests",
      severity: anomaly.severity === "High" ? "high" : anomaly.severity === "Medium" ? "medium" : "low",
      metric: "Ad Requests",
      currentValue: anomaly.currentValue,
      currentFormatted: fmt.num(anomaly.currentValue),
      expectedValue: anomaly.previousValue,
      expectedFormatted: fmt.num(anomaly.previousValue),
      changePct: anomaly.changePct,
      direction: isDrop ? "drop" : "spike",
      reason: anomaly.description || `Ad requests changed ${anomaly.changePct.toFixed(1)}% vs baseline.`,
      suggestedAction: isDrop
        ? "Check app user traffic and ad SDK initialization."
        : "Verify for bot traffic or duplicate ad requests.",
      aiRecommendations: getRecommendations("requests", isDrop ? "drop" : "spike"),
      generatedAt: now,
    });
  }

  return alerts;
}
