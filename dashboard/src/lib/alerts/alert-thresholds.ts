// ─── Alert Threshold Configuration ───────────────────────────────────────────
// Single source of truth for all alert thresholds.
// Adjust these values to tune alert sensitivity.

export const THRESHOLDS = {
  revenue: {
    /** Alert if revenue drops more than this % vs expected */
    dropPct: 20,
    /** Alert if revenue spikes more than this % vs expected */
    spikePct: 100,
    /** Minimum revenue ($) for an app to be considered active */
    minRevenue: 0.01,
  },

  impressions: {
    /** Alert if impressions drop more than this % */
    dropPct: 30,
    /** Alert if impressions spike more than this % */
    spikePct: 200,
    /** Minimum impressions for app to be considered active */
    minImpressions: 100,
  },

  ctr: {
    /** CTR above this % → high alert (suspiciously high) */
    high: 15,
    /** CTR above this % → critical alert */
    veryHigh: 30,
    /** CTR below this % → medium alert (very low) */
    low: 0.5,
    /** CTR below this % → high alert (critically low) */
    veryLow: 0.1,
    /** Minimum impressions required before firing CTR alert */
    minImpressions: 500,
  },

  fillRate: {
    /** Fill rate below this % → medium alert */
    low: 70,
    /** Fill rate below this % → high alert */
    critical: 30,
    /** Minimum ad requests before fill rate alert fires */
    minRequests: 200,
  },

  ecpm: {
    /** eCPM below this value ($) → high alert */
    low: 0.10,
    /** eCPM below this value ($) → critical alert */
    veryLow: 0.02,
    /** eCPM drop more than this % → alert */
    dropPct: 40,
    /** eCPM spike more than this % → medium alert */
    spikePct: 200,
    /** Minimum impressions before eCPM alert fires */
    minImpressions: 500,
  },

  requests: {
    /** Ad requests drop more than this % → alert */
    dropPct: 25,
    /** Ad requests spike more than this % → medium alert */
    spikePct: 200,
  },

  clicks: {
    /** Click count drop more than this % → alert */
    dropPct: 40,
    /** Click spike more than this % → medium alert */
    spikePct: 300,
    /** Minimum impressions before click alert fires */
    minImpressions: 500,
  },

  matchRate: {
    /** Match rate below this % → medium alert */
    low: 50,
    /** Match rate below this % → high alert */
    critical: 20,
    /** Match rate drop more than this % → alert */
    dropPct: 30,
  },
} as const;

export type Thresholds = typeof THRESHOLDS;
