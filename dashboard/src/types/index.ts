export interface AppMetrics {
  ad_unit_name: string;
  ad_unit_id: string;
  revenue_usd: number;
  impressions: number;
  clicks: number;
  ad_requests: number;
  fill_rate_pct: number;
  ctr_pct: number;
  ecpm_usd: number;
  report_date: string;
  network_code: string;
}

export interface NetworkTotal {
  report_date: string;
  app_count: number;
  total_impressions: number;
  total_clicks: number;
  total_ad_requests: number;
  total_revenue_usd: number;
  avg_fill_rate: number | null;
  avg_ecpm: number;
  top_app_name: string;
  top_app_revenue: number;
}

export interface TrendDataPoint {
  report_date: string;
  revenue_usd: number;
  impressions: number;
  ecpm_usd: number;
}

export interface Anomaly {
  ad_unit_name: string;
  today_revenue: number;
  avg_revenue_7d: number;
  drop_pct: number;
  severity: "High" | "Medium" | "Low";
  confidence: number;
}

export interface ReportHistoryItem {
  id: string;
  name: string;
  date: string;
  status: "Queued" | "Running" | "Completed" | "Failed";
  rows: number;
}

export interface SystemAlert {
  id: string;
  title: string;
  timeString: string;
  metric: string;
  severity: "critical" | "warning" | "info";
  app_name: string;
}

// ── BI Report Types ──────────────────────────────────────────────────────────

export interface BISummaryKPI {
  label: string;
  value: number;
  formatted: string;
  previousValue: number;
  changePct: number;
  direction: "up" | "down" | "flat";
  sparkline: number[];
}

export interface BIAppRow {
  rank: number;
  ad_unit_name: string;
  ad_unit_id: string;
  revenue_usd: number;
  impressions: number;
  clicks: number;
  ad_requests: number;
  fill_rate_pct: number;
  ctr_pct: number;
  ecpm_usd: number;
  revenue_pct: number; // % contribution to total
}

export interface BIDailyPoint {
  report_date: string;
  revenue_usd: number;
  impressions: number;
  clicks: number;
  ecpm_usd: number;
  ad_requests: number;
}

export interface BIAnomaly {
  id: string;
  ad_unit_name: string;
  metric: string;
  currentValue: number;
  previousValue: number;
  changePct: number;
  severity: "High" | "Medium" | "Low";
  description: string;
}

export interface BIInsight {
  id: string;
  category: "revenue" | "performance" | "anomaly" | "recommendation";
  icon: string;
  title: string;
  description: string;
}

export interface BIReportData {
  startDate: string;
  endDate: string;
  summary: BISummaryKPI[];
  apps: BIAppRow[];
  dailyTrend: BIDailyPoint[];
  anomalies: BIAnomaly[];
  insights: BIInsight[];
}
