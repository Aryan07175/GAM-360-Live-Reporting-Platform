/**
 * Report Actions — Server Actions for Live GAM Data
 *
 * "use server" functions that call MCP tools.
 * These run on the Next.js server, never expose credentials to the browser.
 * Every call fetches LIVE data from Google Ad Manager.
 */
"use server";

import { callMcpTool, McpToolArgs } from "@/lib/mcp/client";
import type {
  BISummaryKPI,
  BIAppRow,
  BIDailyPoint,
  BIAnomaly,
  BIInsight,
  Recommendation,
  PerformanceRanking,
  LiveReportData,
} from "@/types";

// ─── Helpers ─────────────────────────────────────────────────────────────────

function fmtUSD(v: number): string {
  if (v >= 1000) return `$${(v / 1000).toFixed(2)}K`;
  if (v >= 1) return `$${v.toFixed(2)}`;
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

function baseArgs(
  startDate: string,
  endDate: string,
  startTime: string = "00:00",
  endTime: string = "23:59",
  demandChannel: string = "all",
  forceRefresh: boolean = false
): McpToolArgs {
  return { startDate, endDate, startTime, endTime, demand_channel: demandChannel, force_refresh: forceRefresh };
}

// ─── Executive Summary ──────────────────────────────────────────────────────

export async function fetchExecutiveSummary(
  startDate: string,
  endDate: string,
  startTime: string = "00:00",
  endTime: string = "23:59",
  demandChannel: string = "all",
  forceRefresh: boolean = false
): Promise<{ summary: BISummaryKPI[]; fetchedAt: string } | null> {
  try {
    const res = await callMcpTool(
      "getExecutiveSummary",
      baseArgs(startDate, endDate, startTime, endTime, demandChannel, forceRefresh)
    );
    if (!res || res.status === "error") return null;

    // Backend returns data nested under res.metrics — read from there.
    // Key names also differ from what was previously expected:
    //   avg_ecpm_usd  (not average_ecpm)
    //   avg_ctr_pct   (not average_ctr)
    //   fill_rate_pct (not average_fill_rate)
    //   active_apps   (not app_count)
    //   daily_active_users (field directly available from backend)
    const m = res.metrics || res; // fallback to flat if backend shape changes

    const rev        = Number(m.total_revenue_usd  ?? res.total_revenue_usd  ?? 0);
    const imp        = Number(m.total_impressions   ?? res.total_impressions   ?? 0);
    const clicks     = Number(m.total_clicks        ?? res.total_clicks        ?? 0);
    const ctr        = Number(m.avg_ctr_pct         ?? res.average_ctr         ?? 0);
    const fillRate   = Number(m.fill_rate_pct       ?? res.average_fill_rate   ?? 0);
    const ecpm       = Number(m.avg_ecpm_usd        ?? res.average_ecpm        ?? 0);
    const adRequests = Number(m.total_ad_requests   ?? res.total_ad_requests   ?? 0);
    const appCount   = Number(m.active_apps         ?? res.app_count           ?? 0);
    const dau        = Number(m.daily_active_users  ?? (adRequests > 0 ? Math.round(adRequests / 5) : 0));

    const summary: BISummaryKPI[] = [
      {
        label: "Total Revenue",
        value: rev,
        formatted: fmtUSD(rev),
        previousValue: 0,
        changePct: 0,
        direction: "flat",
        sparkline: [],
      },
      {
        label: "Total Impressions",
        value: imp,
        formatted: fmtNum(imp),
        previousValue: 0,
        changePct: 0,
        direction: "flat",
        sparkline: [],
      },
      {
        label: "Total Clicks",
        value: clicks,
        formatted: fmtNum(clicks),
        previousValue: 0,
        changePct: 0,
        direction: "flat",
        sparkline: [],
      },
      {
        label: "Average eCPM",
        value: ecpm,
        formatted: fmtUSD(ecpm),
        previousValue: 0,
        changePct: 0,
        direction: "flat",
        sparkline: [],
      },
      {
        label: "CTR",
        value: ctr,
        formatted: fmtPct(ctr),
        previousValue: 0,
        changePct: 0,
        direction: "flat",
        sparkline: [],
      },
      {
        label: "Fill Rate",
        value: fillRate,
        formatted: fmtPct(fillRate),
        previousValue: 0,
        changePct: 0,
        direction: "flat",
        sparkline: [],
      },
      {
        label: "Ad Requests",
        value: adRequests,
        formatted: fmtNum(adRequests),
        previousValue: 0,
        changePct: 0,
        direction: "flat",
        sparkline: [],
      },
      {
        label: "Active Apps",
        value: appCount,
        formatted: appCount.toString(),
        previousValue: 0,
        changePct: 0,
        direction: "flat",
        sparkline: [],
      },
      {
        label: "Daily Active Users",
        value: dau,
        formatted: fmtNum(dau),
        previousValue: 0,
        changePct: 0,
        direction: "flat",
        sparkline: [],
      },
    ];

    return { summary, fetchedAt: res.fetched_at };
  } catch (e) {
    console.error("fetchExecutiveSummary failed:", e);
    return null;
  }
}


// ─── Revenue by Application ──────────────────────────────────────────────────

export async function fetchRevenueByApplication(
  startDate: string,
  endDate: string,
  startTime: string = "00:00",
  endTime: string = "23:59",
  demandChannel: string = "all",
  forceRefresh: boolean = false
): Promise<{ apps: BIAppRow[]; fetchedAt: string } | null> {
  try {
    const res = await callMcpTool(
      "getRevenueByApplication",
      baseArgs(startDate, endDate, startTime, endTime, demandChannel, forceRefresh)
    );
    if (!res || res.status === "error" || !res.apps) return null;

    const apps: BIAppRow[] = res.apps.map((a: any, i: number) => ({
      rank: i + 1,
      ad_unit_name: a.ad_unit_name,
      ad_unit_id: a.ad_unit_id,
      revenue_usd: Number(a.ad_server_cpm_and_cpc_revenue || 0),
      impressions: Number(a.ad_server_impressions || 0),
      clicks: Number(a.ad_server_clicks || 0),
      ad_requests: Number(a.ad_server_ad_requests || 0),
      fill_rate_pct: Number(a.ad_server_fill_rate || 0),
      ctr_pct: Number(a.ad_server_ctr || 0),
      ecpm_usd: Number(a.ad_server_without_cpd_average_ecpm || 0),
      revenue_pct: 0, // computed on client
    }));

    return { apps, fetchedAt: res.fetched_at };
  } catch (e) {
    console.error("fetchRevenueByApplication failed:", e);
    return null;
  }
}

// ─── Revenue Trend ───────────────────────────────────────────────────────────

export async function fetchRevenueTrend(
  startDate: string,
  endDate: string,
  startTime: string = "00:00",
  endTime: string = "23:59",
  demandChannel: string = "all",
  forceRefresh: boolean = false
): Promise<{ trend: BIDailyPoint[]; fetchedAt: string } | null> {
  try {
    const res = await callMcpTool(
      "getRevenueTrend",
      baseArgs(startDate, endDate, startTime, endTime, demandChannel, forceRefresh)
    );
    if (!res || res.status === "error" || !res.trend) return null;

    const trend: BIDailyPoint[] = res.trend.map((t: any) => ({
      report_date: t.report_date || t.date,
      revenue_usd: Number(t.revenue_usd || t.revenue || 0),
      impressions: Number(t.impressions || 0),
      clicks: Number(t.clicks || 0),
      ecpm_usd: Number(t.ecpm_usd || 0),
      ad_requests: Number(t.ad_requests || 0),
    }));

    return { trend, fetchedAt: res.fetched_at };
  } catch (e) {
    console.error("fetchRevenueTrend failed:", e);
    return null;
  }
}

// ─── Anomalies ───────────────────────────────────────────────────────────────

export async function fetchAnomalies(
  startDate: string,
  endDate: string,
  startTime: string = "00:00",
  endTime: string = "23:59",
  demandChannel: string = "all",
  forceRefresh: boolean = false
): Promise<{ anomalies: BIAnomaly[]; fetchedAt: string } | null> {
  try {
    const res = await callMcpTool("getAnomalies", {
      ...baseArgs(startDate, endDate, startTime, endTime, demandChannel, forceRefresh),
      threshold_pct: 20,
    });
    if (!res || res.status === "error") return null;

    return {
      anomalies: res.anomalies || [],
      fetchedAt: res.fetched_at,
    };
  } catch (e) {
    console.error("fetchAnomalies failed:", e);
    return null;
  }
}

// ─── Recommendations ─────────────────────────────────────────────────────────

export async function fetchRecommendations(
  startDate: string,
  endDate: string,
  startTime: string = "00:00",
  endTime: string = "23:59",
  demandChannel: string = "all",
  forceRefresh: boolean = false
): Promise<{ recommendations: Recommendation[]; fetchedAt: string } | null> {
  try {
    const res = await callMcpTool(
      "getRecommendations",
      baseArgs(startDate, endDate, startTime, endTime, demandChannel, forceRefresh)
    );
    if (!res || res.status === "error") return null;

    return {
      recommendations: res.recommendations || [],
      fetchedAt: res.fetched_at,
    };
  } catch (e) {
    console.error("fetchRecommendations failed:", e);
    return null;
  }
}

// ─── Performance Ranking ─────────────────────────────────────────────────────

export async function fetchPerformanceRanking(
  startDate: string,
  endDate: string,
  startTime: string = "00:00",
  endTime: string = "23:59",
  demandChannel: string = "all",
  forceRefresh: boolean = false
): Promise<{ rankings: PerformanceRanking[]; fetchedAt: string } | null> {
  try {
    const res = await callMcpTool(
      "getPerformanceRanking",
      baseArgs(startDate, endDate, startTime, endTime, demandChannel, forceRefresh)
    );
    if (!res || res.status === "error") return null;

    return {
      rankings: (res.rankings || []).map((r: any) => ({
        rank: r.rank,
        ad_unit_name: r.ad_unit_name,
        ad_unit_id: r.ad_unit_id,
        revenue_usd: Number(r.ad_server_cpm_and_cpc_revenue || 0),
        impressions: Number(r.ad_server_impressions || 0),
        clicks: Number(r.ad_server_clicks || 0),
        fill_rate_pct: Number(r.ad_server_fill_rate || 0),
        ctr_pct: Number(r.ad_server_ctr || 0),
        ecpm_usd: Number(r.ad_server_without_cpd_average_ecpm || 0),
        score: Number(r.score || 0),
      })),
      fetchedAt: res.fetched_at,
    };
  } catch (e) {
    console.error("fetchPerformanceRanking failed:", e);
    return null;
  }
}

// ─── Full Report ─────────────────────────────────────────────────────────────

export async function fetchFullReport(
  startDate: string,
  endDate: string,
  startTime: string = "00:00",
  endTime: string = "23:59",
  demandChannel: string = "all",
  forceRefresh: boolean = false
): Promise<LiveReportData | null> {
  const MCP_URL =
    process.env.NEXT_PUBLIC_MCP_SERVER_URL ||
    process.env.MCP_SERVER_URL ||
    "https://gam-360-live-reporting-platform.onrender.com";
  console.log(`[fetchFullReport] Using backend: ${MCP_URL} | dates: ${startDate} → ${endDate} | channel: ${demandChannel}`);

  try {
    const res = await callMcpTool(
      "generateFullReport",
      baseArgs(startDate, endDate, startTime, endTime, demandChannel, forceRefresh)
    );

    console.log(`[fetchFullReport] Response received, status: ${res?.status}`);

    if (!res) {
      throw new Error("Backend returned an empty response. Check Render logs for errors.");
    }
    if (res.status === "error") {
      throw new Error(res.error || "Unknown backend error");
    }

    const summaryData = res.summary || {};
    const appsRaw = res.apps || [];
    const trendRaw = res.trend || [];
    const topAppsRaw = res.topApps || [];
    const bottomAppsRaw = res.bottomApps || [];

    const totalRev = summaryData.total_revenue_usd || 0;

    const mapApp = (a: any, i: number): BIAppRow => ({
      rank: i + 1,
      ad_unit_name: a.ad_unit_name || "",
      ad_unit_id: a.ad_unit_id || "",
      revenue_usd: Number(a.ad_server_cpm_and_cpc_revenue || 0),
      impressions: Number(a.ad_server_impressions || 0),
      clicks: Number(a.ad_server_clicks || 0),
      ad_requests: Number(a.ad_server_ad_requests || 0),
      fill_rate_pct: Number(a.ad_server_fill_rate || 0),
      ctr_pct: Number(a.ad_server_ctr || 0),
      ecpm_usd: Number(a.ad_server_without_cpd_average_ecpm || 0),
      revenue_pct:
        totalRev > 0
          ? (Number(a.ad_server_cpm_and_cpc_revenue || 0) / totalRev) * 100
          : 0,
    });

    const mapTrend = (t: any): BIDailyPoint => ({
      report_date: t.report_date || t.date || "",
      revenue_usd: Number(t.revenue_usd || t.revenue || 0),
      impressions: Number(t.impressions || 0),
      clicks: Number(t.clicks || 0),
      ecpm_usd: Number(t.ecpm_usd || 0),
      ad_requests: Number(t.ad_requests || 0),
    });

    return {
      startDate,
      endDate,
      fetchedAt: res.fetched_at || new Date().toISOString(),
      summary: (() => {
        // generateFullReport returns summary = { period, metrics:{...}, revenue_trend, top_apps, all_apps }
        // The KPIs live in summaryData.metrics — fall back to flat if shape changes.
        const m = summaryData?.metrics || summaryData || {};
        const adReq = Number(m.total_ad_requests ?? 0);
        const dau   = Number(m.daily_active_users ?? (adReq > 0 ? Math.round(adReq / 5) : 0));
        return [
          { label: "Total Revenue",      value: Number(m.total_revenue_usd ?? 0), formatted: fmtUSD(Number(m.total_revenue_usd ?? 0)),   previousValue: 0, changePct: 0, direction: "flat" as const, sparkline: [] },
          { label: "Total Impressions",  value: Number(m.total_impressions ?? 0), formatted: fmtNum(Number(m.total_impressions ?? 0)),    previousValue: 0, changePct: 0, direction: "flat" as const, sparkline: [] },
          { label: "Total Clicks",       value: Number(m.total_clicks ?? 0),      formatted: fmtNum(Number(m.total_clicks ?? 0)),         previousValue: 0, changePct: 0, direction: "flat" as const, sparkline: [] },
          { label: "Average eCPM",       value: Number(m.avg_ecpm_usd ?? 0),      formatted: fmtUSD(Number(m.avg_ecpm_usd ?? 0)),         previousValue: 0, changePct: 0, direction: "flat" as const, sparkline: [] },
          { label: "CTR",                value: Number(m.avg_ctr_pct ?? 0),       formatted: fmtPct(Number(m.avg_ctr_pct ?? 0)),          previousValue: 0, changePct: 0, direction: "flat" as const, sparkline: [] },
          { label: "Fill Rate",          value: Number(m.fill_rate_pct ?? 0),     formatted: fmtPct(Number(m.fill_rate_pct ?? 0)),        previousValue: 0, changePct: 0, direction: "flat" as const, sparkline: [] },
          { label: "Ad Requests",        value: adReq,                            formatted: fmtNum(adReq),                               previousValue: 0, changePct: 0, direction: "flat" as const, sparkline: [] },
          { label: "Active Apps",        value: Number(m.active_apps ?? 0),       formatted: String(Number(m.active_apps ?? 0)),          previousValue: 0, changePct: 0, direction: "flat" as const, sparkline: [] },
          { label: "Daily Active Users", value: dau,                              formatted: fmtNum(dau),                                 previousValue: 0, changePct: 0, direction: "flat" as const, sparkline: [] },
        ];
      })(),
      apps: appsRaw.map(mapApp),
      topApps: topAppsRaw.map(mapApp),
      bottomApps: bottomAppsRaw.map(mapApp),
      dailyTrend: trendRaw.map(mapTrend),
      anomalies: res.anomalies || [],
      insights: res.insights || [],
      recommendations: res.recommendations || [],
      rankings: (res.rankings || []).map((r: any) => ({
        rank: r.rank,
        ad_unit_name: r.ad_unit_name,
        ad_unit_id: r.ad_unit_id,
        revenue_usd: Number(r.ad_server_cpm_and_cpc_revenue || 0),
        impressions: Number(r.ad_server_impressions || 0),
        clicks: Number(r.ad_server_clicks || 0),
        fill_rate_pct: Number(r.ad_server_fill_rate || 0),
        ctr_pct: Number(r.ad_server_ctr || 0),
        ecpm_usd: Number(r.ad_server_without_cpd_average_ecpm || 0),
        score: Number(r.score || 0),
      })),
    };
  } catch (e) {
    console.error("fetchFullReport failed:", e);
    return null;
  }
}
