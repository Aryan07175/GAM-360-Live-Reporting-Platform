import type { Alert } from "../alert-types";
import { THRESHOLDS } from "../alert-thresholds";
import { getRecommendations } from "../alert-recommendations";
import type { BIAppRow, BIAnomaly } from "@/types";
import { fmt } from "../alert-utils";

export function generateEcpmAlerts(apps: BIAppRow[], anomalies: BIAnomaly[]): Alert[] {
  const alerts: Alert[] = [];
  const now = new Date().toISOString();
  const T = THRESHOLDS.ecpm;

  // ── 1. Per-app absolute eCPM thresholds ──────────────────────────────────
  for (const app of apps) {
    if (app.impressions < T.minImpressions) continue;
    const ecpm = app.ecpm_usd;

    if (ecpm > 0 && ecpm <= T.veryLow) {
      alerts.push({
        id: `ecpm-very-low-${app.ad_unit_id}-${now}`,
        title: `Critically low eCPM (${fmt.ecpm(ecpm)}) in ${app.ad_unit_name}`,
        appName: app.ad_unit_name,
        category: "ecpm",
        severity: "critical",
        metric: "eCPM (USD)",
        currentValue: ecpm,
        currentFormatted: fmt.ecpm(ecpm),
        expectedValue: T.low,
        expectedFormatted: `> ${fmt.ecpm(T.low)}`,
        changePct: ((ecpm - T.low) / T.low) * 100,
        direction: "threshold",
        reason: `eCPM of ${fmt.ecpm(ecpm)} is critically low — ad inventory is barely monetized.`,
        suggestedAction: "Review floor prices and premium demand availability for this unit.",
        aiRecommendations: getRecommendations("ecpm", "threshold"),
        generatedAt: now,
      });
    } else if (ecpm > T.veryLow && ecpm <= T.low) {
      alerts.push({
        id: `ecpm-low-${app.ad_unit_id}-${now}`,
        title: `Low eCPM (${fmt.ecpm(ecpm)}) in ${app.ad_unit_name}`,
        appName: app.ad_unit_name,
        category: "ecpm",
        severity: "high",
        metric: "eCPM (USD)",
        currentValue: ecpm,
        currentFormatted: fmt.ecpm(ecpm),
        expectedValue: T.low,
        expectedFormatted: `> ${fmt.ecpm(T.low)}`,
        changePct: ((ecpm - T.low) / T.low) * 100,
        direction: "threshold",
        reason: `eCPM of ${fmt.ecpm(ecpm)} is below the expected minimum of ${fmt.ecpm(T.low)}.`,
        suggestedAction: "Add premium demand sources and review floor price settings.",
        aiRecommendations: getRecommendations("ecpm", "threshold"),
        generatedAt: now,
      });
    }
  }

  // ── 2. eCPM anomaly drops ─────────────────────────────────────────────────
  const ecpmAnomalies = anomalies.filter((a) =>
    a.metric.toLowerCase().includes("ecpm") || a.metric.toLowerCase().includes("cpm")
  );
  for (const anomaly of ecpmAnomalies) {
    if (anomaly.changePct > -T.dropPct) continue;
    alerts.push({
      id: `ecpm-drop-${anomaly.id}-${now}`,
      title: `eCPM dropped ${Math.abs(anomaly.changePct).toFixed(1)}% in ${anomaly.ad_unit_name}`,
      appName: anomaly.ad_unit_name,
      category: "ecpm",
      severity: anomaly.changePct <= -60 ? "critical" : "high",
      metric: "eCPM (USD)",
      currentValue: anomaly.currentValue,
      currentFormatted: fmt.ecpm(anomaly.currentValue),
      expectedValue: anomaly.previousValue,
      expectedFormatted: fmt.ecpm(anomaly.previousValue),
      changePct: anomaly.changePct,
      direction: "drop",
      reason: anomaly.description || `eCPM dropped ${Math.abs(anomaly.changePct).toFixed(1)}% vs historical baseline.`,
      suggestedAction: "Review auction competitiveness and floor price settings.",
      aiRecommendations: getRecommendations("ecpm", "drop"),
      generatedAt: now,
    });
  }

  return alerts;
}
