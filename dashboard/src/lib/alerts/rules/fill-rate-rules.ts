import type { Alert } from "../alert-types";
import { THRESHOLDS } from "../alert-thresholds";
import { getRecommendations } from "../alert-recommendations";
import type { BIAppRow } from "@/types";
import { fmt } from "../alert-utils";

export function generateFillRateAlerts(apps: BIAppRow[]): Alert[] {
  const alerts: Alert[] = [];
  const now = new Date().toISOString();
  const T = THRESHOLDS.fillRate;

  for (const app of apps) {
    if (app.ad_requests < T.minRequests) continue;

    const fr = app.fill_rate_pct;

    // Zero fill rate — critical
    if (fr === 0) {
      alerts.push({
        id: `fr-zero-${app.ad_unit_id}-${now}`,
        title: `Zero fill rate in ${app.ad_unit_name}`,
        appName: app.ad_unit_name,
        category: "fill_rate",
        severity: "critical",
        metric: "Fill Rate (%)",
        currentValue: 0,
        currentFormatted: "0%",
        expectedValue: T.low,
        expectedFormatted: `> ${T.low}%`,
        changePct: -100,
        direction: "zero",
        reason: `${fmt.num(app.ad_requests)} ad requests received but 0 impressions served — fill rate is 0%.`,
        suggestedAction: "Check active line items, floor prices, and ad unit targeting immediately.",
        aiRecommendations: getRecommendations("fill_rate", "zero"),
        generatedAt: now,
      });
    }
    // Critically low fill rate
    else if (fr <= T.critical) {
      alerts.push({
        id: `fr-critical-${app.ad_unit_id}-${now}`,
        title: `Critical fill rate (${fmt.pct(fr)}) in ${app.ad_unit_name}`,
        appName: app.ad_unit_name,
        category: "fill_rate",
        severity: "high",
        metric: "Fill Rate (%)",
        currentValue: fr,
        currentFormatted: fmt.pct(fr),
        expectedValue: T.low,
        expectedFormatted: `> ${T.low}%`,
        changePct: fr - T.low,
        direction: "threshold",
        reason: `Fill rate of ${fmt.pct(fr)} is critically low — most ad requests are going unfilled.`,
        suggestedAction: "Review floor prices and add additional demand sources.",
        aiRecommendations: getRecommendations("fill_rate", "drop"),
        generatedAt: now,
      });
    }
    // Low fill rate
    else if (fr < T.low) {
      alerts.push({
        id: `fr-low-${app.ad_unit_id}-${now}`,
        title: `Low fill rate (${fmt.pct(fr)}) in ${app.ad_unit_name}`,
        appName: app.ad_unit_name,
        category: "fill_rate",
        severity: "medium",
        metric: "Fill Rate (%)",
        currentValue: fr,
        currentFormatted: fmt.pct(fr),
        expectedValue: T.low,
        expectedFormatted: `≥ ${T.low}%`,
        changePct: fr - T.low,
        direction: "threshold",
        reason: `Fill rate of ${fmt.pct(fr)} is below the healthy threshold of ${T.low}%.`,
        suggestedAction: "Review floor prices and optimize demand sources.",
        aiRecommendations: getRecommendations("fill_rate", "threshold"),
        generatedAt: now,
      });
    }
  }

  return alerts;
}
