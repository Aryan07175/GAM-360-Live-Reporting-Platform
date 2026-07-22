import type { Alert, AlertSeverity } from "../alert-types";
import { THRESHOLDS } from "../alert-thresholds";
import { getRecommendations } from "../alert-recommendations";
import type { BIAppRow, BIAnomaly, BISummaryKPI } from "@/types";
import { fmt } from "../alert-utils";

export function generateImpressionAlerts(
  apps: BIAppRow[],
  anomalies: BIAnomaly[],
  summary: BISummaryKPI[]
): Alert[] {
  const alerts: Alert[] = [];
  const now = new Date().toISOString();
  const T = THRESHOLDS.impressions;

  // ── 1. Network-level impression change ───────────────────────────────────
  const impKPI = summary.find((k) => k.label.toLowerCase().includes("impression"));
  if (impKPI && impKPI.previousValue > 0) {
    const changePct = impKPI.changePct;
    if (changePct <= -T.dropPct) {
      const sev: AlertSeverity = changePct <= -60 ? "critical" : "high";
      alerts.push({
        id: `imp-network-drop-${now}`,
        title: `Impressions dropped ${Math.abs(changePct).toFixed(1)}% network-wide`,
        appName: "All Networks",
        category: "impressions",
        severity: sev,
        metric: "Total Impressions",
        currentValue: impKPI.value,
        currentFormatted: fmt.num(impKPI.value),
        expectedValue: impKPI.previousValue,
        expectedFormatted: fmt.num(impKPI.previousValue),
        changePct,
        direction: "drop",
        reason: `Total impressions dropped ${Math.abs(changePct).toFixed(1)}% compared to the previous period.`,
        suggestedAction: "Check app traffic, fill rate, and ad unit availability.",
        aiRecommendations: getRecommendations("impressions", "drop"),
        generatedAt: now,
      });
    }
  }

  // ── 2. Zero impressions with active requests ─────────────────────────────
  for (const app of apps) {
    if (app.impressions === 0 && app.ad_requests > T.minImpressions) {
      alerts.push({
        id: `imp-zero-${app.ad_unit_id}-${now}`,
        title: `Zero impressions in ${app.ad_unit_name}`,
        appName: app.ad_unit_name,
        category: "impressions",
        severity: "critical",
        metric: "Impressions",
        currentValue: 0,
        currentFormatted: "0",
        expectedValue: app.ad_requests,
        expectedFormatted: fmt.num(app.ad_requests),
        changePct: -100,
        direction: "zero",
        reason: `${fmt.num(app.ad_requests)} ad requests received but zero impressions served — fill rate is 0%.`,
        suggestedAction: "Verify ad SDK integration and check active line items.",
        aiRecommendations: getRecommendations("impressions", "zero"),
        generatedAt: now,
      });
    }
  }

  // ── 3. Per-app impression anomalies ─────────────────────────────────────
  const impAnomalies = anomalies.filter((a) =>
    a.metric.toLowerCase().includes("impression")
  );
  for (const anomaly of impAnomalies) {
    if (Math.abs(anomaly.changePct) < T.dropPct) continue;
    const isDrop = anomaly.changePct < 0;
    const sev: AlertSeverity =
      anomaly.severity === "High" ? "high" : anomaly.severity === "Medium" ? "medium" : "low";

    alerts.push({
      id: `imp-anomaly-${anomaly.id}-${now}`,
      title: isDrop
        ? `Impressions dropped ${Math.abs(anomaly.changePct).toFixed(1)}% in ${anomaly.ad_unit_name}`
        : `Impressions spiked ${anomaly.changePct.toFixed(1)}% in ${anomaly.ad_unit_name}`,
      appName: anomaly.ad_unit_name,
      category: "impressions",
      severity: sev,
      metric: "Impressions",
      currentValue: anomaly.currentValue,
      currentFormatted: fmt.num(anomaly.currentValue),
      expectedValue: anomaly.previousValue,
      expectedFormatted: fmt.num(anomaly.previousValue),
      changePct: anomaly.changePct,
      direction: isDrop ? "drop" : "spike",
      reason: anomaly.description || `Impressions changed ${anomaly.changePct.toFixed(1)}% vs baseline.`,
      suggestedAction: isDrop
        ? "Check user traffic, ad unit availability and fill rate."
        : "Validate for duplicate ad unit tagging or invalid traffic.",
      aiRecommendations: getRecommendations("impressions", isDrop ? "drop" : "spike"),
      generatedAt: now,
    });
  }

  return alerts;
}
