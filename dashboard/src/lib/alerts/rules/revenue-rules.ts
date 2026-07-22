import type { Alert, AlertSeverity } from "../alert-types";
import { THRESHOLDS } from "../alert-thresholds";
import { getRecommendations } from "../alert-recommendations";
import type { BIAppRow, BIAnomaly, BISummaryKPI } from "@/types";
import { fmt } from "../alert-utils";


/**
 * Revenue alert rules.
 * Fires on: zero revenue, large drops, large spikes, anomaly-detected drops.
 */
export function generateRevenueAlerts(
  apps: BIAppRow[],
  anomalies: BIAnomaly[],
  summary: BISummaryKPI[]
): Alert[] {
  const alerts: Alert[] = [];
  const now = new Date().toISOString();
  const T = THRESHOLDS.revenue;

  // ── 1. Network-level revenue change (from summary KPIs) ──────────────────
  const revKPI = summary.find((k) =>
    k.label.toLowerCase().includes("revenue")
  );
  if (revKPI && revKPI.previousValue > 0) {
    const changePct = revKPI.changePct;
    if (changePct <= -T.dropPct) {
      const sev: AlertSeverity = changePct <= -50 ? "critical" : "high";
      alerts.push({
        id: `rev-network-drop-${now}`,
        title: `Network revenue dropped ${Math.abs(changePct).toFixed(1)}%`,
        appName: "All Networks",
        category: "revenue",
        severity: sev,
        metric: "Total Revenue (USD)",
        currentValue: revKPI.value,
        currentFormatted: fmt.usd(revKPI.value),
        expectedValue: revKPI.previousValue,
        expectedFormatted: fmt.usd(revKPI.previousValue),
        changePct,
        direction: "drop",
        reason: `Total network revenue dropped ${Math.abs(changePct).toFixed(1)}% compared to the previous period.`,
        suggestedAction: "Review fill rate and advertiser demand across all ad units.",
        aiRecommendations: getRecommendations("revenue", "drop"),
        generatedAt: now,
      });
    } else if (changePct >= T.spikePct) {
      alerts.push({
        id: `rev-network-spike-${now}`,
        title: `Network revenue spiked ${changePct.toFixed(1)}%`,
        appName: "All Networks",
        category: "revenue",
        severity: "medium",
        metric: "Total Revenue (USD)",
        currentValue: revKPI.value,
        currentFormatted: fmt.usd(revKPI.value),
        expectedValue: revKPI.previousValue,
        expectedFormatted: fmt.usd(revKPI.previousValue),
        changePct,
        direction: "spike",
        reason: `Total network revenue increased ${changePct.toFixed(1)}% — verify this is expected.`,
        suggestedAction: "Validate against your Ad Manager reporting to confirm accuracy.",
        aiRecommendations: getRecommendations("revenue", "spike"),
        generatedAt: now,
      });
    }
  }

  // ── 2. Per-app zero revenue ───────────────────────────────────────────────
  for (const app of apps) {
    if (app.revenue_usd === 0 && app.ad_requests > 200) {
      alerts.push({
        id: `rev-zero-${app.ad_unit_id}-${now}`,
        title: `Zero revenue in ${app.ad_unit_name}`,
        appName: app.ad_unit_name,
        category: "revenue",
        severity: "critical",
        metric: "Revenue (USD)",
        currentValue: 0,
        currentFormatted: "$0.00",
        expectedValue: 0,
        expectedFormatted: "—",
        changePct: -100,
        direction: "zero",
        reason: "App has ad requests but is generating zero revenue — all monetization has stopped.",
        suggestedAction: "Verify line item delivery and fill rate immediately.",
        aiRecommendations: getRecommendations("revenue", "zero"),
        generatedAt: now,
      });
    }
  }

  // ── 3. Per-app revenue anomalies (from anomaly engine) ───────────────────
  const revAnomalies = anomalies.filter(
    (a) => a.metric.toLowerCase().includes("revenue")
  );
  for (const anomaly of revAnomalies) {
    if (Math.abs(anomaly.changePct) < T.dropPct) continue;
    const isDrop = anomaly.changePct < 0;
    const sev: AlertSeverity =
      anomaly.severity === "High" ? (anomaly.changePct <= -50 ? "critical" : "high")
        : anomaly.severity === "Medium" ? "medium"
          : "low";

    alerts.push({
      id: `rev-anomaly-${anomaly.id}-${now}`,
      title: isDrop
        ? `Revenue dropped ${Math.abs(anomaly.changePct).toFixed(1)}% in ${anomaly.ad_unit_name}`
        : `Revenue spiked ${anomaly.changePct.toFixed(1)}% in ${anomaly.ad_unit_name}`,
      appName: anomaly.ad_unit_name,
      category: "revenue",
      severity: sev,
      metric: "Revenue (USD)",
      currentValue: anomaly.currentValue,
      currentFormatted: fmt.usd(anomaly.currentValue),
      expectedValue: anomaly.previousValue,
      expectedFormatted: fmt.usd(anomaly.previousValue),
      changePct: anomaly.changePct,
      direction: isDrop ? "drop" : "spike",
      reason: anomaly.description || `Revenue changed ${anomaly.changePct.toFixed(1)}% vs historical average.`,
      suggestedAction: isDrop
        ? "Check fill rate, inventory, and advertiser demand for this app."
        : "Validate the spike against your Ad Manager reports to confirm accuracy.",
      aiRecommendations: getRecommendations("revenue", isDrop ? "drop" : "spike"),
      generatedAt: now,
    });
  }

  return alerts;
}
