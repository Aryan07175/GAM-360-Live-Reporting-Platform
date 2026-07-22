import type { Alert, AlertSeverity } from "../alert-types";
import { THRESHOLDS } from "../alert-thresholds";
import { getRecommendations } from "../alert-recommendations";
import type { BIAppRow } from "@/types";
import { fmt } from "../alert-utils";

export function generateCTRAlerts(apps: BIAppRow[]): Alert[] {
  const alerts: Alert[] = [];
  const now = new Date().toISOString();
  const T = THRESHOLDS.ctr;

  for (const app of apps) {
    // Skip apps with insufficient volume
    if (app.impressions < T.minImpressions) continue;

    const ctr = app.ctr_pct;

    // Critically high CTR (likely click fraud)
    if (ctr >= T.veryHigh) {
      alerts.push({
        id: `ctr-very-high-${app.ad_unit_id}-${now}`,
        title: `Critically high CTR (${fmt.pct(ctr)}) in ${app.ad_unit_name}`,
        appName: app.ad_unit_name,
        category: "ctr",
        severity: "critical",
        metric: "CTR (%)",
        currentValue: ctr,
        currentFormatted: fmt.pct(ctr),
        expectedValue: T.high,
        expectedFormatted: fmt.pct(T.high),
        changePct: ctr - T.veryHigh,
        direction: "spike",
        reason: `CTR of ${fmt.pct(ctr)} far exceeds the suspicious threshold of ${fmt.pct(T.veryHigh)}. Likely invalid clicks.`,
        suggestedAction: "Report to GAM support and enable invalid traffic filtering immediately.",
        aiRecommendations: getRecommendations("ctr", "spike"),
        generatedAt: now,
      });
    }
    // Suspiciously high CTR
    else if (ctr >= T.high) {
      const sev: AlertSeverity = ctr >= 25 ? "high" : "medium";
      alerts.push({
        id: `ctr-high-${app.ad_unit_id}-${now}`,
        title: `High CTR detected (${fmt.pct(ctr)}) in ${app.ad_unit_name}`,
        appName: app.ad_unit_name,
        category: "ctr",
        severity: sev,
        metric: "CTR (%)",
        currentValue: ctr,
        currentFormatted: fmt.pct(ctr),
        expectedValue: T.high,
        expectedFormatted: `< ${fmt.pct(T.high)}`,
        changePct: ctr - T.high,
        direction: "threshold",
        reason: `CTR of ${fmt.pct(ctr)} exceeds the healthy threshold of ${fmt.pct(T.high)}. Investigate for accidental clicks.`,
        suggestedAction: "Review ad placement for accidental tap areas and check for invalid traffic.",
        aiRecommendations: getRecommendations("ctr", "spike"),
        generatedAt: now,
      });
    }
    // Critically low CTR
    else if (ctr > 0 && ctr <= T.veryLow) {
      alerts.push({
        id: `ctr-very-low-${app.ad_unit_id}-${now}`,
        title: `Very low CTR (${fmt.pct(ctr)}) in ${app.ad_unit_name}`,
        appName: app.ad_unit_name,
        category: "ctr",
        severity: "high",
        metric: "CTR (%)",
        currentValue: ctr,
        currentFormatted: fmt.pct(ctr),
        expectedValue: T.low,
        expectedFormatted: `> ${fmt.pct(T.low)}`,
        changePct: ctr - T.low,
        direction: "drop",
        reason: `CTR of ${fmt.pct(ctr)} is critically low, indicating poor ad visibility or creative quality issues.`,
        suggestedAction: "Review ad placement visibility and creative relevance for this unit.",
        aiRecommendations: getRecommendations("ctr", "drop"),
        generatedAt: now,
      });
    }
    // Low CTR
    else if (ctr > 0 && ctr <= T.low) {
      alerts.push({
        id: `ctr-low-${app.ad_unit_id}-${now}`,
        title: `Low CTR (${fmt.pct(ctr)}) in ${app.ad_unit_name}`,
        appName: app.ad_unit_name,
        category: "ctr",
        severity: "low",
        metric: "CTR (%)",
        currentValue: ctr,
        currentFormatted: fmt.pct(ctr),
        expectedValue: T.low,
        expectedFormatted: `> ${fmt.pct(T.low)}`,
        changePct: ctr - T.low,
        direction: "threshold",
        reason: `CTR of ${fmt.pct(ctr)} is below the expected minimum, suggesting disengaged audiences or poor ad placement.`,
        suggestedAction: "Test different ad formats and placements to improve user engagement.",
        aiRecommendations: getRecommendations("ctr", "drop"),
        generatedAt: now,
      });
    }
  }

  return alerts;
}
