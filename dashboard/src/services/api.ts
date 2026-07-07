"use server";

export const maxDuration = 60; // Set max duration to 60s for Vercel (Hobby limit is 60s max)
import {
  AppMetrics,
  NetworkTotal,
  TrendDataPoint,
  Anomaly,
  SystemAlert,
  ReportHistoryItem
} from "../types";
import { callMcpTool } from "../lib/mcp/client";

export async function getNetworkTotal(date: string): Promise<NetworkTotal | null> {
  try {
    const result = await callMcpTool("getExecutiveSummary", { date });
    if (!result || result.status === "error") return null;

    return {
      report_date: result.date || date,
      app_count: result.app_count || 0,
      total_impressions: result.total_impressions || 0,
      total_clicks: 0, 
      total_ad_requests: 0,
      total_revenue_usd: result.total_revenue_usd || 0,
      avg_fill_rate: null,
      avg_ecpm: result.average_ecpm || 0,
      top_app_name: result.top_app_name || "N/A",
      top_app_revenue: result.top_app_revenue || 0,
      cached_at: result.cached_at,
    } as NetworkTotal & { cached_at?: string };
  } catch (error) {
    console.error("Failed to fetch network total from MCP:", error);
    return null;
  }
}

export async function getRevenueByApp(date: string): Promise<AppMetrics[]> {
  try {
    const result = await callMcpTool("getRevenueByApplication", { date });
    if (!result || result.status === "error" || !result.apps) return [];

    return result.apps.map((r: any) => ({
      ad_unit_name: r.ad_unit_name,
      ad_unit_id: r.ad_unit_id,
      revenue_usd: Number(r.ad_server_cpm_and_cpc_revenue || 0),
      impressions: Number(r.ad_server_impressions || 0),
      clicks: Number(r.ad_server_clicks || 0),
      ad_requests: Number(r.ad_server_ad_requests || 0),
      fill_rate_pct: Number(r.ad_server_fill_rate || 0),
      ctr_pct: Number(r.ad_server_ctr || 0),
      ecpm_usd: Number(r.ad_server_without_cpd_average_ecpm || 0),
      report_date: date,
      network_code: "",
    }));
  } catch (error) {
    console.error("Failed to fetch revenue by app from MCP:", error);
    return [];
  }
}

export async function getRevenueTrend(days: number = 30): Promise<TrendDataPoint[]> {
  try {
    const result = await callMcpTool("getRevenueTrend", { app_name: "", days });
    if (!result || result.status === "error" || !result.trend) return [];

    return result.trend.map((r: any) => ({
      report_date: r.date,
      revenue_usd: Number(r.revenue || 0),
      impressions: 0,
      ecpm_usd: 0,
    }));
  } catch (error) {
    console.error("Failed to fetch revenue trend from MCP:", error);
    return [];
  }
}

export async function getAnomalies(date: string): Promise<Anomaly[]> {
  try {
    const result = await callMcpTool("getAnomalies", { date, threshold_pct: 20 });
    if (!result || result.status === "error" || !result.anomalies) return [];

    return result.anomalies.map((a: any) => ({
      ad_unit_name: a.ad_unit_name,
      today_revenue: Number(a.today_revenue || 0),
      avg_revenue_7d: Number(a.avg_revenue_7d || 0),
      drop_pct: Number(a.drop_pct || 0),
      severity: "Medium",
      confidence: 0.9,
    }));
  } catch (error) {
    console.error("Failed to fetch anomalies from MCP:", error);
    return [];
  }
}

export async function getSystemAlerts(date: string): Promise<SystemAlert[]> {
  const alerts: SystemAlert[] = [];
  try {
    const apps = await getRevenueByApp(date);
    let idCounter = 1;

    for (const app of apps) {
      if (app.impressions > 0 && app.impressions < 1000) {
        alerts.push({
          id: `alert-${idCounter++}`,
          title: `Low impression volume detected in ${app.ad_unit_name}`,
          timeString: "Detected today",
          metric: "Impressions",
          severity: "warning",
          app_name: app.ad_unit_name,
        });
      }
      
      if (app.revenue_usd > 0 && app.revenue_usd < 0.5) {
        alerts.push({
          id: `alert-${idCounter++}`,
          title: `Revenue dropped below $0.50 in ${app.ad_unit_name}`,
          timeString: "Detected today",
          metric: "Revenue",
          severity: "critical",
          app_name: app.ad_unit_name,
        });
      }
    }
    return alerts;
  } catch (error) {
    console.error("Error generating system alerts:", error);
    return [];
  }
}

// -------------------------------------------------------------------
// IN MEMORY CACHE FOR REPORT HISTORY (Replaces PostgreSQL table)
// -------------------------------------------------------------------
const inMemoryReports: ReportHistoryItem[] = [];

export async function getReportHistory(): Promise<ReportHistoryItem[]> {
  // Simulate completing queued reports
  for (const report of inMemoryReports) {
    if (report.status === "Queued") {
      report.status = "Running";
    } else if (report.status === "Running") {
      report.status = "Completed";
      report.rows = Math.floor(Math.random() * 5000 + 100);
    }
  }
  return [...inMemoryReports].reverse();
}

export async function triggerReportGeneration(
  config: {
    datePreset?: string;
    startDate?: string;
    endDate?: string;
    dimensions?: string;
  }
): Promise<{ id: string; status: string }> {
  const today = new Date().toISOString().split("T")[0];
  const startDate = config.startDate || today;
  const endDate = config.endDate || today;

  const presetLabels: Record<string, string> = {
    yesterday: "Yesterday",
    last7days: "Last 7 Days",
    last30days: "Last 30 Days",
    thismonth: "This Month",
    custom: `${startDate} to ${endDate}`,
  };
  const rangeLabel = config.datePreset && presetLabels[config.datePreset]
    ? presetLabels[config.datePreset]
    : `${startDate} to ${endDate}`;
  const dimLabel = config.dimensions ? ` [${config.dimensions.toUpperCase()}]` : "";
  const reportName = `GAM Report – ${rangeLabel}${dimLabel}`;

  const newId = Math.random().toString(36).substring(7);
  inMemoryReports.push({
    id: newId,
    name: reportName,
    date: startDate,
    status: "Queued",
    rows: 0,
  });

  return { id: newId, status: "Queued" };
}
