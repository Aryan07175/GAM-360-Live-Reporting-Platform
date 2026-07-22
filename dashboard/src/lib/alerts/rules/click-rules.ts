import type { Alert } from "../alert-types";
import { THRESHOLDS } from "../alert-thresholds";
import { getRecommendations } from "../alert-recommendations";
import type { BIAppRow, BIAnomaly } from "@/types";
import { fmt } from "../alert-utils";

export function generateClickAlerts(apps: BIAppRow[], anomalies: BIAnomaly[]): Alert[] {
  const alerts: Alert[] = [];
  const now = new Date().toISOString();
  const T = THRESHOLDS.clicks;

  // ── 1. Zero clicks with impressions ─────────────────────────────────────
  for (const app of apps) {
    if (app.impressions >= T.minImpressions && app.clicks === 0) {
      alerts.push({
        id: `click-zero-${app.ad_unit_id}-${now}`,
        title: `Zero clicks in ${app.ad_unit_name}`,
        appName: app.ad_unit_name,
        category: "clicks",
        severity: "medium",
        metric: "Clicks",
        currentValue: 0,
        currentFormatted: "0",
        expectedValue: Math.round(app.impressions * 0.005),
        expectedFormatted: fmt.num(Math.round(app.impressions * 0.005)),
        changePct: -100,
        direction: "zero",
        reason: `${fmt.num(app.impressions)} impressions served but zero clicks recorded — click tracking may be broken.`,
        suggestedAction: "Verify click tracking URLs and creative configuration.",
        aiRecommendations: getRecommendations("clicks", "zero"),
        generatedAt: now,
      });
    }
  }

  // ── 2. Click anomalies ───────────────────────────────────────────────────
  const clickAnomalies = anomalies.filter((a) =>
    a.metric.toLowerCase().includes("click")
  );
  for (const anomaly of clickAnomalies) {
    if (Math.abs(anomaly.changePct) < T.dropPct) continue;
    const isDrop = anomaly.changePct < 0;
    alerts.push({
      id: `click-anomaly-${anomaly.id}-${now}`,
      title: isDrop
        ? `Clicks dropped ${Math.abs(anomaly.changePct).toFixed(1)}% in ${anomaly.ad_unit_name}`
        : `Clicks spiked ${anomaly.changePct.toFixed(1)}% in ${anomaly.ad_unit_name}`,
      appName: anomaly.ad_unit_name,
      category: "clicks",
      severity: isDrop
        ? anomaly.severity === "High" ? "high" : "medium"
        : anomaly.changePct >= T.spikePct ? "high" : "medium",
      metric: "Clicks",
      currentValue: anomaly.currentValue,
      currentFormatted: fmt.num(anomaly.currentValue),
      expectedValue: anomaly.previousValue,
      expectedFormatted: fmt.num(anomaly.previousValue),
      changePct: anomaly.changePct,
      direction: isDrop ? "drop" : "spike",
      reason: anomaly.description || `Clicks changed ${anomaly.changePct.toFixed(1)}% vs baseline.`,
      suggestedAction: isDrop
        ? "Review ad creative quality and placement visibility."
        : "Investigate for click fraud and invalid traffic patterns.",
      aiRecommendations: getRecommendations("clicks", isDrop ? "drop" : "spike"),
      generatedAt: now,
    });
  }

  return alerts;
}
