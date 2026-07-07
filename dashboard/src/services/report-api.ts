"use server";

import postgres from "postgres";
import {
  BIReportData,
  BISummaryKPI,
  BIAppRow,
  BIDailyPoint,
  BIAnomaly,
  BIInsight,
} from "../types";

const sql = postgres(process.env.DATABASE_URL || "", { ssl: "require" });
const isConfigured = !!process.env.DATABASE_URL;

// ── Helper: format currency ──────────────────────────────────────────────────
function fmtUSD(v: number): string {
  if (v >= 1000) return `$${(v / 1000).toFixed(2)}K`;
  return `$${v.toFixed(6)}`;
}
function fmtNum(v: number): string {
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `${(v / 1_000).toFixed(1)}K`;
  return v.toLocaleString();
}
function fmtPct(v: number): string {
  return `${v.toFixed(2)}%`;
}

// ── Master BI report function ────────────────────────────────────────────────
export async function getBIReportData(
  startDate: string,
  endDate: string
): Promise<BIReportData> {
  if (!isConfigured) {
    return getEmptyReport(startDate, endDate);
  }

  try {
    // Calculate previous period (same duration, immediately before)
    const start = new Date(startDate);
    const end = new Date(endDate);
    const durationMs = end.getTime() - start.getTime();
    const prevEnd = new Date(start.getTime() - 86400000); // day before start
    const prevStart = new Date(prevEnd.getTime() - durationMs);
    const prevStartStr = prevStart.toISOString().split("T")[0];
    const prevEndStr = prevEnd.toISOString().split("T")[0];

    // Run all queries in parallel for performance
    const [currentApps, prevTotals, dailyTrend] = await Promise.all([
      // 1. All app data for current period (aggregated across date range)
      sql`
        SELECT
          ad_unit_name,
          ad_unit_id,
          COALESCE(SUM(revenue_usd), 0) AS revenue_usd,
          COALESCE(SUM(impressions), 0) AS impressions,
          COALESCE(SUM(clicks), 0) AS clicks,
          COALESCE(SUM(ad_requests), 0) AS ad_requests,
          CASE WHEN COALESCE(SUM(ad_requests), 0) > 0
            THEN ROUND(CAST(SUM(impressions) AS NUMERIC) / SUM(ad_requests) * 100, 2)
            ELSE 0
          END AS fill_rate_pct,
          CASE WHEN COALESCE(SUM(impressions), 0) > 0
            THEN ROUND(CAST(SUM(clicks) AS NUMERIC) / SUM(impressions) * 100, 4)
            ELSE 0
          END AS ctr_pct,
          CASE WHEN COALESCE(SUM(impressions), 0) > 0
            THEN ROUND(CAST(SUM(revenue_usd) AS NUMERIC) / SUM(impressions) * 1000, 6)
            ELSE 0
          END AS ecpm_usd
        FROM gam_revenue
        WHERE report_date >= ${startDate} AND report_date <= ${endDate}
        GROUP BY ad_unit_name, ad_unit_id
        ORDER BY revenue_usd DESC
      `,

      // 2. Previous period totals for comparison
      sql`
        SELECT
          COALESCE(SUM(revenue_usd), 0) AS total_revenue,
          COALESCE(SUM(impressions), 0) AS total_impressions,
          COALESCE(SUM(clicks), 0) AS total_clicks,
          COALESCE(SUM(ad_requests), 0) AS total_ad_requests,
          COUNT(DISTINCT ad_unit_name) AS app_count,
          CASE WHEN COALESCE(SUM(ad_requests), 0) > 0
            THEN ROUND(CAST(SUM(impressions) AS NUMERIC) / SUM(ad_requests) * 100, 2)
            ELSE 0
          END AS fill_rate,
          CASE WHEN COALESCE(SUM(impressions), 0) > 0
            THEN ROUND(CAST(SUM(revenue_usd) AS NUMERIC) / SUM(impressions) * 1000, 6)
            ELSE 0
          END AS ecpm,
          CASE WHEN COALESCE(SUM(impressions), 0) > 0
            THEN ROUND(CAST(SUM(clicks) AS NUMERIC) / SUM(impressions) * 100, 4)
            ELSE 0
          END AS ctr
        FROM gam_revenue
        WHERE report_date >= ${prevStartStr} AND report_date <= ${prevEndStr}
      `,

      // 3. Daily trend for line charts
      sql`
        SELECT
          report_date,
          COALESCE(SUM(revenue_usd), 0) AS revenue_usd,
          COALESCE(SUM(impressions), 0) AS impressions,
          COALESCE(SUM(clicks), 0) AS clicks,
          AVG(ecpm_usd) AS ecpm_usd,
          COALESCE(SUM(ad_requests), 0) AS ad_requests
        FROM gam_revenue
        WHERE report_date >= ${startDate} AND report_date <= ${endDate}
        GROUP BY report_date
        ORDER BY report_date ASC
      `,
    ]);

    // ── Build totals ─────────────────────────────────────────────────────
    const totalRevenue = currentApps.reduce((s, r) => s + Number(r.revenue_usd), 0);
    const totalImpressions = currentApps.reduce((s, r) => s + Number(r.impressions), 0);
    const totalClicks = currentApps.reduce((s, r) => s + Number(r.clicks), 0);
    const totalAdRequests = currentApps.reduce((s, r) => s + Number(r.ad_requests), 0);
    const appCount = currentApps.length;
    const avgEcpm = totalImpressions > 0 ? (totalRevenue / totalImpressions) * 1000 : 0;
    const avgFillRate = totalAdRequests > 0 ? (totalImpressions / totalAdRequests) * 100 : 0;
    const avgCtr = totalImpressions > 0 ? (totalClicks / totalImpressions) * 100 : 0;

    const prev = prevTotals[0] || {};
    const prevRevenue = Number(prev.total_revenue || 0);
    const prevImpressions = Number(prev.total_impressions || 0);
    const prevClicks = Number(prev.total_clicks || 0);
    const prevAdRequests = Number(prev.total_ad_requests || 0);
    const prevEcpm = Number(prev.ecpm || 0);
    const prevFillRate = Number(prev.fill_rate || 0);
    const prevCtr = Number(prev.ctr || 0);
    const prevAppCount = Number(prev.app_count || 0);

    // ── Sparkline data (last 7 daily values) ─────────────────────────────
    const revenueSparkline = dailyTrend.slice(-7).map((d: any) => Number(d.revenue_usd));
    const impressionSparkline = dailyTrend.slice(-7).map((d: any) => Number(d.impressions));
    const clickSparkline = dailyTrend.slice(-7).map((d: any) => Number(d.clicks));
    const ecpmSparkline = dailyTrend.slice(-7).map((d: any) => Number(d.ecpm_usd));

    function calcChange(curr: number, prev: number): { changePct: number; direction: "up" | "down" | "flat" } {
      if (prev === 0) return { changePct: curr > 0 ? 100 : 0, direction: curr > 0 ? "up" : "flat" };
      const pct = ((curr - prev) / prev) * 100;
      return { changePct: Math.round(pct * 100) / 100, direction: pct > 0.5 ? "up" : pct < -0.5 ? "down" : "flat" };
    }

    // ── Summary KPIs ─────────────────────────────────────────────────────
    const summary: BISummaryKPI[] = [
      { label: "Total Revenue", value: totalRevenue, formatted: fmtUSD(totalRevenue), previousValue: prevRevenue, ...calcChange(totalRevenue, prevRevenue), sparkline: revenueSparkline },
      { label: "Total Impressions", value: totalImpressions, formatted: fmtNum(totalImpressions), previousValue: prevImpressions, ...calcChange(totalImpressions, prevImpressions), sparkline: impressionSparkline },
      { label: "Total Clicks", value: totalClicks, formatted: fmtNum(totalClicks), previousValue: prevClicks, ...calcChange(totalClicks, prevClicks), sparkline: clickSparkline },
      { label: "Average eCPM", value: avgEcpm, formatted: fmtUSD(avgEcpm), previousValue: prevEcpm, ...calcChange(avgEcpm, prevEcpm), sparkline: ecpmSparkline },
      { label: "Fill Rate", value: avgFillRate, formatted: fmtPct(avgFillRate), previousValue: prevFillRate, ...calcChange(avgFillRate, prevFillRate), sparkline: [] },
      { label: "Total Ad Requests", value: totalAdRequests, formatted: fmtNum(totalAdRequests), previousValue: prevAdRequests, ...calcChange(totalAdRequests, prevAdRequests), sparkline: [] },
      { label: "Active Applications", value: appCount, formatted: String(appCount), previousValue: prevAppCount, ...calcChange(appCount, prevAppCount), sparkline: [] },
      { label: "Average CTR", value: avgCtr, formatted: fmtPct(avgCtr), previousValue: prevCtr, ...calcChange(avgCtr, prevCtr), sparkline: [] },
    ];

    // ── Apps with rank + contribution ────────────────────────────────────
    const apps: BIAppRow[] = currentApps.map((r: any, i: number) => ({
      rank: i + 1,
      ad_unit_name: r.ad_unit_name,
      ad_unit_id: r.ad_unit_id,
      revenue_usd: Number(r.revenue_usd),
      impressions: Number(r.impressions),
      clicks: Number(r.clicks),
      ad_requests: Number(r.ad_requests),
      fill_rate_pct: Number(r.fill_rate_pct),
      ctr_pct: Number(r.ctr_pct),
      ecpm_usd: Number(r.ecpm_usd),
      revenue_pct: totalRevenue > 0 ? Math.round((Number(r.revenue_usd) / totalRevenue) * 10000) / 100 : 0,
    }));

    // ── Daily trend ──────────────────────────────────────────────────────
    const daily: BIDailyPoint[] = dailyTrend.map((r: any) => ({
      report_date: new Date(r.report_date).toISOString().split("T")[0],
      revenue_usd: Number(r.revenue_usd),
      impressions: Number(r.impressions),
      clicks: Number(r.clicks),
      ecpm_usd: Number(r.ecpm_usd),
      ad_requests: Number(r.ad_requests),
    }));

    // ── Anomaly detection ────────────────────────────────────────────────
    const anomalies: BIAnomaly[] = [];
    // Compare last day in range to the average of the rest
    if (daily.length >= 2) {
      const lastDay = daily[daily.length - 1];
      const restAvg = {
        revenue: daily.slice(0, -1).reduce((s, d) => s + d.revenue_usd, 0) / (daily.length - 1),
        impressions: daily.slice(0, -1).reduce((s, d) => s + d.impressions, 0) / (daily.length - 1),
        clicks: daily.slice(0, -1).reduce((s, d) => s + d.clicks, 0) / (daily.length - 1),
      };

      const checkAnomaly = (metric: string, current: number, avg: number) => {
        if (avg === 0) return;
        const changePct = ((current - avg) / avg) * 100;
        if (Math.abs(changePct) > 20) {
          anomalies.push({
            id: `anomaly-${metric}-${lastDay.report_date}`,
            ad_unit_name: "Network-wide",
            metric,
            currentValue: current,
            previousValue: avg,
            changePct: Math.round(changePct * 100) / 100,
            severity: Math.abs(changePct) > 50 ? "High" : Math.abs(changePct) > 30 ? "Medium" : "Low",
            description: `${metric} ${changePct > 0 ? "spiked" : "dropped"} ${Math.abs(changePct).toFixed(1)}% on ${lastDay.report_date} compared to the period average.`,
          });
        }
      };

      checkAnomaly("Revenue", lastDay.revenue_usd, restAvg.revenue);
      checkAnomaly("Impressions", lastDay.impressions, restAvg.impressions);
      checkAnomaly("Clicks", lastDay.clicks, restAvg.clicks);
    }

    // Per-app anomalies: apps with revenue < 20% of average app revenue
    const avgAppRevenue = totalRevenue / (appCount || 1);
    for (const app of apps) {
      if (avgAppRevenue > 0 && app.revenue_usd < avgAppRevenue * 0.2 && app.revenue_usd > 0) {
        anomalies.push({
          id: `anomaly-app-${app.ad_unit_id}`,
          ad_unit_name: app.ad_unit_name,
          metric: "Revenue",
          currentValue: app.revenue_usd,
          previousValue: avgAppRevenue,
          changePct: Math.round(((app.revenue_usd - avgAppRevenue) / avgAppRevenue) * 10000) / 100,
          severity: app.revenue_usd < avgAppRevenue * 0.1 ? "High" : "Medium",
          description: `${app.ad_unit_name} is earning ${fmtUSD(app.revenue_usd)} — significantly below the average of ${fmtUSD(avgAppRevenue)} per app.`,
        });
      }
    }

    // ── AI insights ──────────────────────────────────────────────────────
    const insights: BIInsight[] = generateInsights(apps, summary, daily, anomalies);

    return { startDate, endDate, summary, apps, dailyTrend: daily, anomalies, insights };
  } catch (error) {
    console.error("BI Report query failed:", error);
    return getEmptyReport(startDate, endDate);
  }
}

// ── Insight generator ────────────────────────────────────────────────────────
function generateInsights(
  apps: BIAppRow[],
  summary: BISummaryKPI[],
  daily: BIDailyPoint[],
  anomalies: BIAnomaly[]
): BIInsight[] {
  const insights: BIInsight[] = [];
  let id = 0;

  if (apps.length === 0) return insights;

  const top = apps[0];
  const bottom = apps[apps.length - 1];

  // Revenue insights
  insights.push({
    id: `insight-${id++}`, category: "revenue", icon: "🏆",
    title: `Highest Earning: ${top.ad_unit_name}`,
    description: `Generated ${fmtUSD(top.revenue_usd)} (${top.revenue_pct.toFixed(1)}% of total revenue) with ${fmtNum(top.impressions)} impressions and eCPM of ${fmtUSD(top.ecpm_usd)}.`,
  });
  insights.push({
    id: `insight-${id++}`, category: "revenue", icon: "📉",
    title: `Lowest Earning: ${bottom.ad_unit_name}`,
    description: `Generated only ${fmtUSD(bottom.revenue_usd)} (${bottom.revenue_pct.toFixed(1)}% of total). Consider investigating traffic quality or demand setup.`,
  });

  // Revenue growth/decline
  const revKPI = summary.find(s => s.label === "Total Revenue");
  if (revKPI && revKPI.changePct !== 0) {
    insights.push({
      id: `insight-${id++}`, category: "revenue", icon: revKPI.direction === "up" ? "📈" : "📉",
      title: `Revenue ${revKPI.direction === "up" ? "Growth" : "Decline"}: ${Math.abs(revKPI.changePct).toFixed(1)}%`,
      description: `Total revenue ${revKPI.direction === "up" ? "increased" : "decreased"} from ${fmtUSD(revKPI.previousValue)} to ${fmtUSD(revKPI.value)} compared to the previous period.`,
    });
  }

  // eCPM insights
  const sortedByEcpm = [...apps].sort((a, b) => b.ecpm_usd - a.ecpm_usd);
  const highEcpm = sortedByEcpm[0];
  const lowEcpm = sortedByEcpm[sortedByEcpm.length - 1];
  if (highEcpm) {
    insights.push({
      id: `insight-${id++}`, category: "performance", icon: "💰",
      title: `Highest eCPM: ${highEcpm.ad_unit_name}`,
      description: `eCPM of ${fmtUSD(highEcpm.ecpm_usd)} — the most valuable inventory. Consider increasing traffic here.`,
    });
  }
  if (lowEcpm && lowEcpm.ecpm_usd > 0) {
    insights.push({
      id: `insight-${id++}`, category: "performance", icon: "⚠️",
      title: `Lowest eCPM: ${lowEcpm.ad_unit_name}`,
      description: `eCPM of ${fmtUSD(lowEcpm.ecpm_usd)} — review demand configuration or consider ad format changes.`,
    });
  }

  // CTR insights
  const sortedByCtr = [...apps].filter(a => a.ctr_pct > 0).sort((a, b) => b.ctr_pct - a.ctr_pct);
  if (sortedByCtr.length > 0) {
    insights.push({
      id: `insight-${id++}`, category: "performance", icon: "🎯",
      title: `Highest CTR: ${sortedByCtr[0].ad_unit_name}`,
      description: `CTR of ${sortedByCtr[0].ctr_pct.toFixed(2)}% — strong user engagement.`,
    });
  }

  // Fill rate insights
  const lowFillApps = apps.filter(a => a.fill_rate_pct > 0 && a.fill_rate_pct < 50);
  if (lowFillApps.length > 0) {
    insights.push({
      id: `insight-${id++}`, category: "performance", icon: "🔻",
      title: `${lowFillApps.length} Apps Below 50% Fill Rate`,
      description: `Apps with low fill rates are leaving ad revenue on the table. Consider adding more demand partners.`,
    });
  }

  // Anomaly insights
  if (anomalies.length > 0) {
    const highSeverity = anomalies.filter(a => a.severity === "High");
    insights.push({
      id: `insight-${id++}`, category: "anomaly", icon: "🚨",
      title: `${anomalies.length} Anomalies Detected (${highSeverity.length} High Severity)`,
      description: `Automated analysis flagged ${anomalies.length} unusual patterns in the selected period. Review the Anomaly Detection section below.`,
    });
  }

  // Recommendations
  if (highEcpm && highEcpm.impressions < apps.reduce((s, a) => s + a.impressions, 0) / apps.length) {
    insights.push({
      id: `insight-${id++}`, category: "recommendation", icon: "💡",
      title: `Increase Traffic to ${highEcpm.ad_unit_name}`,
      description: `This app has the highest eCPM (${fmtUSD(highEcpm.ecpm_usd)}) but below-average impressions. Driving more traffic here could significantly boost revenue.`,
    });
  }
  if (lowEcpm && lowEcpm.ecpm_usd > 0 && lowEcpm.impressions > apps.reduce((s, a) => s + a.impressions, 0) / apps.length) {
    insights.push({
      id: `insight-${id++}`, category: "recommendation", icon: "🔧",
      title: `Optimize Demand for ${lowEcpm.ad_unit_name}`,
      description: `High traffic but lowest eCPM (${fmtUSD(lowEcpm.ecpm_usd)}). Adding premium demand partners or adjusting floor prices could improve monetization.`,
    });
  }

  return insights;
}

// ── Empty report ─────────────────────────────────────────────────────────────
function getEmptyReport(startDate: string, endDate: string): BIReportData {
  return {
    startDate,
    endDate,
    summary: [],
    apps: [],
    dailyTrend: [],
    anomalies: [],
    insights: [],
  };
}
