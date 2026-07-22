// ─── Alert Recommendations ────────────────────────────────────────────────────
// Static AI recommendation map.
// Maps (category, direction) → array of actionable recommendations.
// Extend this map to add more context-aware suggestions.

import type { AlertCategory, AlertDirection } from "./alert-types";

type RecommendationMap = Partial<
  Record<AlertCategory, Partial<Record<AlertDirection | "general", string[]>>>
>;

const RECOMMENDATIONS: RecommendationMap = {
  revenue: {
    drop: [
      "Review fill rate across affected ad units — a drop in fill rate directly reduces revenue.",
      "Check if any line items have paused, expired, or exhausted their budgets.",
      "Inspect advertiser demand: verify campaign flight dates and targeting are still active.",
      "Review floor prices — overly high floors can reduce auction participation.",
      "Check for any recent changes to ad unit configuration or targeting rules.",
    ],
    spike: [
      "Validate the revenue spike against your ad server reports to confirm accuracy.",
      "Check for any new high-value campaigns or programmatic deals that may have activated.",
      "Review eCPM trends — a sudden spike may indicate a one-time high-value event.",
      "Ensure data is not being double-counted due to reporting configuration changes.",
    ],
    zero: [
      "Check if GAM credentials are valid and the API is returning data.",
      "Verify ad units are correctly tagged and receiving traffic.",
      "Inspect line item delivery — all active campaigns may have paused or expired.",
      "Review network-level ad serving settings for any accidental blocks.",
    ],
  },
  impressions: {
    drop: [
      "Check if user traffic to the app has decreased — impressions follow DAU.",
      "Verify ad unit SDK integration is functioning correctly.",
      "Review ad refresh settings — reduced refresh rate lowers impression count.",
      "Check for any ad blockers or consent management changes reducing ad serving.",
      "Inspect fill rate — lower fill means fewer recorded impressions.",
    ],
    spike: [
      "Verify that a new ad unit or placement has not been double-tagged.",
      "Check for bot traffic or invalid traffic (IVT) patterns.",
      "Review ad refresh rate settings — a misconfiguration may inflate impressions.",
      "Confirm the spike correlates with a real user growth event.",
    ],
    zero: [
      "Confirm the ad SDK is initialized and ad requests are being made.",
      "Check for network connectivity issues in the app.",
      "Review GAM ad serving rules — ads may be blocked for policy reasons.",
    ],
  },
  ctr: {
    spike: [
      "Investigate for click fraud or invalid clicks from specific ad units.",
      "Review ad placement — accidental clicks from overlapping UI elements inflate CTR.",
      "Check if reward-based or interstitial ads are misclassified in the data.",
      "Report the anomaly to your GAM support contact if CTR exceeds 30%.",
      "Review the affected ad unit's creative format — some formats naturally have higher CTR.",
    ],
    drop: [
      "Review ad creative quality — stale or irrelevant ads reduce user engagement.",
      "Check if ad placement has changed — below-the-fold ads get lower CTR.",
      "Experiment with different ad sizes and formats to improve engagement.",
      "Review audience targeting — ads shown to uninterested audiences have low CTR.",
    ],
    threshold: [
      "Monitor this ad unit closely for click fraud patterns.",
      "Consider enabling invalid traffic filtering in your GAM settings.",
      "Compare this unit's CTR against industry benchmarks for the ad format.",
    ],
  },
  fill_rate: {
    drop: [
      "Review floor price settings — high floors reduce auction fill rate.",
      "Check open auction competition — fewer bidders means lower fill.",
      "Verify ad unit sizes match what buyers are targeting.",
      "Add additional demand partners or open bidding participants.",
      "Review frequency caps — overly strict caps reduce available inventory.",
    ],
    zero: [
      "Verify that ad requests are reaching GAM (check SDK logs).",
      "Check if all line items have expired or been paused network-wide.",
      "Ensure no misconfiguration in ad unit targeting is blocking all demand.",
      "Review your network's ad serving limits and quotas.",
    ],
    threshold: [
      "Set up additional header bidding or mediation demand sources.",
      "Review and optimize floor prices using historical eCPM data.",
      "Consider enabling unfilled ad request reporting to diagnose root cause.",
    ],
  },
  ecpm: {
    drop: [
      "Review auction competitiveness — fewer bidders lower eCPM.",
      "Check if any premium programmatic deals have expired or been paused.",
      "Inspect floor price settings — ensure they are set appropriately.",
      "Review advertiser competition by geography or app category.",
      "Check if the ad inventory quality has been affected by any policy changes.",
    ],
    spike: [
      "Confirm data accuracy — an eCPM spike may indicate a data aggregation issue.",
      "Check for a high-value programmatic deal that activated on this unit.",
      "Document the spike conditions so they can be replicated in future campaigns.",
    ],
    threshold: [
      "Review CPM floor prices to ensure they reflect market value.",
      "Add premium demand partners to increase auction competition.",
      "Test different ad formats — native and video typically command higher eCPMs.",
    ],
  },
  requests: {
    drop: [
      "Check user session data — fewer requests correlate with reduced app usage.",
      "Verify that the ad SDK is not crashing or failing silently.",
      "Review ad refresh frequency settings — they directly impact request volume.",
      "Check for any consent management changes that may be blocking ad requests.",
    ],
    spike: [
      "Verify the spike is not due to a bot or automated testing traffic.",
      "Review ad refresh settings — an accidental config change can multiply requests.",
      "Ensure the ad SDK version is not generating duplicate requests.",
    ],
    zero: [
      "Confirm the ad SDK is integrated and calling GAM correctly.",
      "Check app crash rates — if the app is crashing, ad requests stop.",
      "Review GAM network settings for any request blocking rules.",
    ],
  },
  clicks: {
    drop: [
      "Review ad creative quality and relevance to the target audience.",
      "Check placement visibility — ads that are not viewable get fewer clicks.",
      "Test different CTAs or creative formats to re-engage users.",
    ],
    spike: [
      "Investigate for click fraud — unusual click spikes can indicate invalid activity.",
      "Review ad placement for accidental click areas near interactive UI elements.",
      "Verify with Google's invalid click reporting in your Ad Manager account.",
    ],
    zero: [
      "Check if the ad unit is rendering correctly in the app.",
      "Verify that click tracking URLs are correctly configured.",
      "Review ad creative status — expired or disapproved creatives stop serving.",
    ],
  },
  match_rate: {
    drop: [
      "Review audience targeting — overly narrow targeting reduces match rates.",
      "Check consent signals — reduced user consent lowers data match availability.",
      "Verify that user identifiers (GAID/IDFA) are being passed correctly.",
    ],
    threshold: [
      "Audit your audience segment configurations in GAM.",
      "Review privacy consent flows — GDPR/CCPA compliance can reduce match rates.",
      "Consider expanding targeting criteria to increase available inventory.",
    ],
  },
  error: {
    general: [
      "Check the Render service logs for specific error details.",
      "Verify GAM API credentials are still valid and not expired.",
      "Ensure the GAM network code is correctly configured in Render environment variables.",
      "Check for Google Ad Manager API quota limits or rate limiting.",
      "Review the service status page at ads.google.com for any known outages.",
    ],
  },
};

/**
 * Returns 3–5 AI recommendations for a given alert category and direction.
 */
export function getRecommendations(
  category: AlertCategory,
  direction: AlertDirection
): string[] {
  const catRecs = RECOMMENDATIONS[category];
  if (!catRecs) return getDefaultRecommendations(category);

  const dirRecs = catRecs[direction] ?? catRecs["general"] ?? [];
  if (dirRecs.length === 0) return getDefaultRecommendations(category);

  return dirRecs.slice(0, 5);
}

function getDefaultRecommendations(category: AlertCategory): string[] {
  return [
    `Review the ${category.replace("_", " ")} metric in Google Ad Manager.`,
    "Compare current values against historical baselines in your reporting dashboard.",
    "Check for any recent changes to ad unit configuration or targeting.",
    "Contact your GAM support representative if the issue persists.",
  ];
}
