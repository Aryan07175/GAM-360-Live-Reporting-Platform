"use server";

export const maxDuration = 60; // Set max duration to 60s for Vercel
import {
  BISummaryKPI,
  BIAppRow,
  BIDailyPoint,
  BIAnomaly,
  BIInsight,
} from "../types";
import { callMcpTool } from "../lib/mcp/client";

// Helper for formatting
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

export async function getBIExecutiveSummary(date: string): Promise<{ summary: BISummaryKPI[], cached_at: string } | null> {
  try {
    const res = await callMcpTool("getExecutiveSummary", { date });
    if (!res || res.status === "error") return null;

    const rev = Number(res.total_revenue_usd || 0);
    const imp = Number(res.total_impressions || 0);
    const ecpm = Number(res.average_ecpm || 0);

    const summary: BISummaryKPI[] = [
      { label: "Total Revenue", value: rev, formatted: fmtUSD(rev), previousValue: 0, changePct: 0, direction: "flat", sparkline: [] },
      { label: "Total Impressions", value: imp, formatted: fmtNum(imp), previousValue: 0, changePct: 0, direction: "flat", sparkline: [] },
      { label: "Average eCPM", value: ecpm, formatted: fmtUSD(ecpm), previousValue: 0, changePct: 0, direction: "flat", sparkline: [] },
    ];
    return { summary, cached_at: res.cached_at };
  } catch (e) {
    console.error(e);
    return null;
  }
}

export async function getBIApps(date: string): Promise<{ apps: BIAppRow[], cached_at: string } | null> {
  try {
    const res = await callMcpTool("getRevenueByApplication", { date });
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
      revenue_pct: 0, // we will calculate on client
    }));
    return { apps, cached_at: res.cached_at };
  } catch (e) {
    console.error(e);
    return null;
  }
}

export async function getBITrend(date: string, days: number = 7): Promise<{ trend: BIDailyPoint[], cached_at: string } | null> {
  try {
    const res = await callMcpTool("getRevenueTrend", { app_name: "", days });
    if (!res || res.status === "error" || !res.trend) return null;

    const trend: BIDailyPoint[] = res.trend.map((t: any) => ({
      report_date: t.date,
      revenue_usd: Number(t.revenue || 0),
      impressions: 0,
      clicks: 0,
      ecpm_usd: 0,
      ad_requests: 0,
    }));
    return { trend, cached_at: res.cached_at };
  } catch (e) {
    console.error(e);
    return null;
  }
}

export async function getBIAnomalies(date: string): Promise<{ anomalies: BIAnomaly[], cached_at: string } | null> {
  try {
    const res = await callMcpTool("getAnomalies", { date });
    if (!res || res.status === "error" || !res.anomalies) return null;

    return { anomalies: res.anomalies, cached_at: res.cached_at };
  } catch (e) {
    console.error(e);
    return null;
  }
}
