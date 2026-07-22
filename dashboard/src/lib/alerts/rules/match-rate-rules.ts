import type { Alert } from "../alert-types";
import { getRecommendations } from "../alert-recommendations";
import type { BIAnomaly } from "@/types";
import { fmt } from "../alert-utils";
import { THRESHOLDS } from "../alert-thresholds";

/**
 * Match rate rules — fires when anomaly data contains match_rate metrics.
 * Since match_rate is not directly in BIAppRow, we rely on the anomaly engine.
 */
export function generateMatchRateAlerts(anomalies: BIAnomaly[]): Alert[] {
  const alerts: Alert[] = [];
  const now = new Date().toISOString();
  const T = THRESHOLDS.matchRate;

  const mrAnomalies = anomalies.filter((a) =>
    a.metric.toLowerCase().includes("match")
  );

  for (const anomaly of mrAnomalies) {
    // Treat currentValue as a percentage (0-100)
    const mr = anomaly.currentValue;

    if (mr <= T.critical) {
      alerts.push({
        id: `mr-critical-${anomaly.id}-${now}`,
        title: `Critical match rate (${fmt.pct(mr)}) in ${anomaly.ad_unit_name}`,
        appName: anomaly.ad_unit_name,
        category: "match_rate",
        severity: "high",
        metric: "Match Rate (%)",
        currentValue: mr,
        currentFormatted: fmt.pct(mr),
        expectedValue: T.low,
        expectedFormatted: `> ${T.low}%`,
        changePct: anomaly.changePct,
        direction: "threshold",
        reason: `Match rate of ${fmt.pct(mr)} is critically low — most ad requests are not being matched.`,
        suggestedAction: "Review audience targeting rules and consent signal configuration.",
        aiRecommendations: getRecommendations("match_rate", "threshold"),
        generatedAt: now,
      });
    } else if (mr <= T.low || anomaly.changePct <= -T.dropPct) {
      alerts.push({
        id: `mr-low-${anomaly.id}-${now}`,
        title: `Low match rate (${fmt.pct(mr)}) in ${anomaly.ad_unit_name}`,
        appName: anomaly.ad_unit_name,
        category: "match_rate",
        severity: "medium",
        metric: "Match Rate (%)",
        currentValue: mr,
        currentFormatted: fmt.pct(mr),
        expectedValue: T.low,
        expectedFormatted: `≥ ${T.low}%`,
        changePct: anomaly.changePct,
        direction: "drop",
        reason: anomaly.description || `Match rate of ${fmt.pct(mr)} is below the ${T.low}% threshold.`,
        suggestedAction: "Expand audience targeting or review user identifier signal availability.",
        aiRecommendations: getRecommendations("match_rate", "drop"),
        generatedAt: now,
      });
    }
  }

  return alerts;
}
