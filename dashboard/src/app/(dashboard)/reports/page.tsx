"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { getBIReportData } from "@/services/report-api";
import { getReportHistory, triggerReportGeneration } from "@/services/api";
import { BIReportData, ReportHistoryItem } from "@/types";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import {
  Play, Download, Trash2, CheckCircle2, XCircle, Clock,
  Loader2, RefreshCw, CalendarDays, Database, BarChart3,
} from "lucide-react";
import { useDateContext } from "@/contexts/DateContext";
import { format, subDays, parseISO, startOfMonth, subMonths, endOfMonth } from "date-fns";

// BI Components
import { ReportKPICard } from "@/components/reports/report-kpi-card";
import { ReportBarChart } from "@/components/reports/report-bar-chart";
import { ReportDonutChart } from "@/components/reports/report-donut-chart";
import { ReportLineChart } from "@/components/reports/report-line-chart";
import { ReportDataTable } from "@/components/reports/report-data-table";
import { ReportAnomalyCard } from "@/components/reports/report-anomaly-card";
import { ReportInsights } from "@/components/reports/report-insights";
import { ReportExportBar } from "@/components/reports/report-export-bar";

export default function ReportsPage() {
  const { selectedDate, latestDate, refreshKey } = useDateContext();

  // Existing state
  const [history, setHistory] = useState<ReportHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  // Report config
  const [datePreset, setDatePreset] = useState("last30days");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [dimensions, setDimensions] = useState("app");

  // BI Report state
  const [biData, setBiData] = useState<BIReportData | null>(null);
  const [biLoading, setBiLoading] = useState(false);
  const [biError, setBiError] = useState<string | null>(null);

  // Derive start/end from preset
  useEffect(() => {
    if (datePreset === "custom") return;

    const referenceDate = latestDate ? parseISO(latestDate) : new Date();
    let start: string = format(referenceDate, "yyyy-MM-dd");
    let end: string = format(referenceDate, "yyyy-MM-dd");

    switch (datePreset) {
      case "today":
        start = format(referenceDate, "yyyy-MM-dd");
        end = format(referenceDate, "yyyy-MM-dd");
        break;
      case "yesterday":
        start = format(subDays(referenceDate, 1), "yyyy-MM-dd");
        end = format(subDays(referenceDate, 1), "yyyy-MM-dd");
        break;
      case "last7days":
        start = format(subDays(referenceDate, 6), "yyyy-MM-dd");
        break;
      case "last30days":
        start = format(subDays(referenceDate, 29), "yyyy-MM-dd");
        break;
      case "thismonth":
        start = format(startOfMonth(referenceDate), "yyyy-MM-dd");
        break;
      case "lastmonth": {
        const prevMonth = subMonths(referenceDate, 1);
        start = format(startOfMonth(prevMonth), "yyyy-MM-dd");
        end = format(endOfMonth(prevMonth), "yyyy-MM-dd");
        break;
      }
      default:
        return;
    }

    setStartDate(start);
    setEndDate(end);
  }, [datePreset, latestDate]);

  // Load report history
  const loadHistory = useCallback(async () => {
    const data = await getReportHistory();
    setHistory(data);
    setLoading(false);
  }, []);

  useEffect(() => {
    loadHistory();
  }, [loadHistory, refreshKey]);

  // Poll while jobs are active
  useEffect(() => {
    const hasActive = history.some(
      (h) => h.status === "Queued" || h.status === "Running"
    );
    if (!hasActive) return;
    const interval = setInterval(loadHistory, 2000);
    return () => clearInterval(interval);
  }, [history, loadHistory]);

  // Generate BI report
  const handleGenerate = async () => {
    if (!startDate || !endDate) {
      alert("Please select a date range before generating a report.");
      return;
    }

    setGenerating(true);
    setBiLoading(true);
    setBiError(null);

    try {
      // Trigger history item AND fetch BI data in parallel
      const [_, biResult] = await Promise.all([
        triggerReportGeneration({ datePreset, startDate, endDate, dimensions }),
        getBIReportData(startDate, endDate),
      ]);

      setBiData(biResult);
      await loadHistory();
    } catch (err) {
      setBiError("Failed to generate report. Please try again.");
      console.error(err);
    } finally {
      setGenerating(false);
      setBiLoading(false);
    }
  };

  const handleDownload = (item: ReportHistoryItem) => {
    const url = `/api/export?date=${item.date}`;
    window.location.href = url;
  };

  const handleDelete = async (item: ReportHistoryItem) => {
    setDeletingId(item.id);
    try {
      await fetch(`/api/reports/${item.id}`, { method: "DELETE" });
    } catch {}
    setHistory((prev) => prev.filter((h) => h.id !== item.id));
    setDeletingId(null);
  };

  const StatusIcon = ({ status }: { status: string }) => {
    switch (status) {
      case "Completed": return <CheckCircle2 className="h-4 w-4 text-emerald-500 mr-2" />;
      case "Failed": return <XCircle className="h-4 w-4 text-red-500 mr-2" />;
      case "Running": return <Loader2 className="h-4 w-4 text-blue-500 animate-spin mr-2" />;
      default: return <Clock className="h-4 w-4 text-muted-foreground mr-2" />;
    }
  };

  const statusColor = (status: string) => {
    switch (status) {
      case "Completed": return "text-emerald-500";
      case "Failed": return "text-red-500";
      case "Running": return "text-blue-500";
      default: return "text-muted-foreground";
    }
  };

  // ── Computed chart data from biData ────────────────────────────────────────
  const revenueByApp = useMemo(() => {
    if (!biData) return [];
    return biData.apps.map((a) => ({ name: a.ad_unit_name.length > 25 ? a.ad_unit_name.substring(0, 25) + "…" : a.ad_unit_name, value: a.revenue_usd, fullName: a.ad_unit_name }));
  }, [biData]);

  const top10 = useMemo(() => revenueByApp.slice(0, 10), [revenueByApp]);
  const bottom10 = useMemo(() => [...revenueByApp].reverse().slice(0, 10), [revenueByApp]);

  const impressionsByApp = useMemo(() => {
    if (!biData) return [];
    return biData.apps.slice(0, 20).map((a) => ({ name: a.ad_unit_name.length > 20 ? a.ad_unit_name.substring(0, 20) + "…" : a.ad_unit_name, value: a.impressions }));
  }, [biData]);

  const clicksByApp = useMemo(() => {
    if (!biData) return [];
    return biData.apps.filter((a) => a.clicks > 0).slice(0, 20).map((a) => ({ name: a.ad_unit_name.length > 20 ? a.ad_unit_name.substring(0, 20) + "…" : a.ad_unit_name, value: a.clicks }));
  }, [biData]);

  const ecpmByApp = useMemo(() => {
    if (!biData) return [];
    return [...biData.apps].sort((a, b) => b.ecpm_usd - a.ecpm_usd).slice(0, 20).map((a) => ({ name: a.ad_unit_name.length > 25 ? a.ad_unit_name.substring(0, 25) + "…" : a.ad_unit_name, value: a.ecpm_usd }));
  }, [biData]);

  const fillRateByApp = useMemo(() => {
    if (!biData) return [];
    return [...biData.apps].sort((a, b) => b.fill_rate_pct - a.fill_rate_pct).slice(0, 20).map((a) => ({ name: a.ad_unit_name.length > 20 ? a.ad_unit_name.substring(0, 20) + "…" : a.ad_unit_name, value: a.fill_rate_pct }));
  }, [biData]);

  const adRequestsByApp = useMemo(() => {
    if (!biData) return [];
    return [...biData.apps].sort((a, b) => b.ad_requests - a.ad_requests).slice(0, 20).map((a) => ({ name: a.ad_unit_name.length > 20 ? a.ad_unit_name.substring(0, 20) + "…" : a.ad_unit_name, value: a.ad_requests }));
  }, [biData]);

  const ctrByApp = useMemo(() => {
    if (!biData) return [];
    return [...biData.apps].filter((a) => a.ctr_pct > 0).sort((a, b) => b.ctr_pct - a.ctr_pct).slice(0, 20).map((a) => ({ name: a.ad_unit_name.length > 20 ? a.ad_unit_name.substring(0, 20) + "…" : a.ad_unit_name, value: a.ctr_pct }));
  }, [biData]);

  const donutData = useMemo(() => {
    if (!biData) return [];
    const topN = biData.apps.slice(0, 8);
    const rest = biData.apps.slice(8);
    const restTotal = rest.reduce((s, a) => s + a.revenue_usd, 0);
    const items = topN.map((a) => ({ name: a.ad_unit_name.length > 20 ? a.ad_unit_name.substring(0, 20) + "…" : a.ad_unit_name, value: a.revenue_usd }));
    if (restTotal > 0) items.push({ name: `Others (${rest.length})`, value: restTotal });
    return items;
  }, [biData]);

  // Daily comparison (last 2 days)
  const dailyComparison = useMemo(() => {
    if (!biData || biData.dailyTrend.length < 2) return [];
    const trend = biData.dailyTrend;
    const today = trend[trend.length - 1];
    const yesterday = trend[trend.length - 2];
    return [
      { name: "Revenue", today: today.revenue_usd, yesterday: yesterday.revenue_usd, diff: today.revenue_usd - yesterday.revenue_usd },
      { name: "Impressions", today: today.impressions, yesterday: yesterday.impressions, diff: today.impressions - yesterday.impressions },
      { name: "Clicks", today: today.clicks, yesterday: yesterday.clicks, diff: today.clicks - yesterday.clicks },
    ];
  }, [biData]);

  // Revenue contribution table
  const contributionTable = useMemo(() => {
    if (!biData) return [];
    return biData.apps.slice(0, 20);
  }, [biData]);

  return (
    <div className="space-y-6 print:space-y-4">
      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <BarChart3 className="h-6 w-6 text-indigo-500" />
            Executive BI Report
          </h2>
          <p className="text-muted-foreground">
            Comprehensive analytics powered by Google Ad Manager 360 data.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {biData && <ReportExportBar data={biData} />}
          <Button variant="outline" size="sm" onClick={loadHistory} disabled={loading} className="gap-2">
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>
      </div>

      {/* ── Filter Bar ──────────────────────────────────────────────────────── */}
      <Card className="print:hidden">
        <CardContent className="pt-5 pb-4">
          <div className="flex flex-wrap items-end gap-4">
            {/* Date Preset */}
            <div className="space-y-1.5">
              <Label className="text-xs">Date Range</Label>
              <Select value={datePreset} onValueChange={(val) => setDatePreset(val || "last30days")}>
                <SelectTrigger className="w-[160px]">
                  <SelectValue placeholder="Select preset" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="today">Today</SelectItem>
                  <SelectItem value="yesterday">Yesterday</SelectItem>
                  <SelectItem value="last7days">Last 7 Days</SelectItem>
                  <SelectItem value="last30days">Last 30 Days</SelectItem>
                  <SelectItem value="thismonth">This Month</SelectItem>
                  <SelectItem value="lastmonth">Last Month</SelectItem>
                  <SelectItem value="custom">Custom Range…</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Start Date */}
            <div className="space-y-1.5">
              <Label className="text-xs">Start</Label>
              <input
                type="date"
                className="w-[140px] rounded-md border bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring"
                value={startDate}
                max={latestDate || undefined}
                onChange={(e) => { setStartDate(e.target.value); setDatePreset("custom"); }}
              />
            </div>

            {/* End Date */}
            <div className="space-y-1.5">
              <Label className="text-xs">End</Label>
              <input
                type="date"
                className="w-[140px] rounded-md border bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring"
                value={endDate}
                max={latestDate || undefined}
                onChange={(e) => { setEndDate(e.target.value); setDatePreset("custom"); }}
              />
            </div>

            {/* Date Range Label */}
            {startDate && endDate && (
              <span className="text-xs text-muted-foreground bg-muted/50 rounded-md px-3 py-2 self-end">
                📅 {format(parseISO(startDate), "MMM dd")} → {format(parseISO(endDate), "MMM dd, yyyy")}
              </span>
            )}

            {/* Generate */}
            <Button
              className="bg-indigo-600 hover:bg-indigo-700 text-white self-end"
              onClick={handleGenerate}
              disabled={generating || !startDate || !endDate}
            >
              {generating ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Play className="h-4 w-4 mr-2" />}
              {generating ? "Generating…" : "Generate Report"}
            </Button>

            {/* Quick CSV Export */}
            {selectedDate && (
              <Button
                variant="outline"
                size="sm"
                className="self-end"
                onClick={() => { window.location.href = `/api/export?date=${selectedDate}`; }}
              >
                <Download className="h-4 w-4 mr-1" />
                CSV ({format(parseISO(selectedDate), "MMM dd")})
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* ── Loading State ───────────────────────────────────────────────────── */}
      {biLoading && (
        <div className="flex items-center justify-center py-20">
          <div className="text-center space-y-4">
            <Loader2 className="h-10 w-10 animate-spin text-indigo-500 mx-auto" />
            <p className="text-sm text-muted-foreground">Generating your executive report…</p>
            <p className="text-xs text-muted-foreground">Querying {startDate} to {endDate}</p>
          </div>
        </div>
      )}

      {/* ── Error State ─────────────────────────────────────────────────────── */}
      {biError && (
        <Card className="border-rose-500/30">
          <CardContent className="py-8 text-center">
            <p className="text-rose-500 font-medium">{biError}</p>
          </CardContent>
        </Card>
      )}

      {/* ═══════════════════════════════════════════════════════════════════════
          BI REPORT SECTIONS
          ═══════════════════════════════════════════════════════════════════════ */}
      {biData && !biLoading && biData.apps.length > 0 && (
        <>
          {/* ── 1. Executive Summary KPIs ─────────────────────────────────── */}
          <div>
            <h3 className="text-lg font-semibold mb-3">Executive Summary</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {biData.summary.map((kpi) => (
                <ReportKPICard key={kpi.label} kpi={kpi} />
              ))}
            </div>
          </div>

          {/* ── 2. Revenue by Application + Contribution Table ────────────── */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2">
              <ReportBarChart
                title="Revenue by Application"
                description="Sorted by revenue (descending). Green = highest, Red = lowest."
                data={revenueByApp.slice(0, 20)}
                layout="horizontal"
                valuePrefix="$"
                height={Math.max(300, revenueByApp.slice(0, 20).length * 28)}
              />
            </div>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Revenue Contribution</CardTitle>
                <CardDescription>Top 20 apps by share</CardDescription>
              </CardHeader>
              <CardContent className="px-0">
                <div className="overflow-y-auto max-h-[500px]">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="pl-4">#</TableHead>
                        <TableHead>Application</TableHead>
                        <TableHead className="text-right">Revenue</TableHead>
                        <TableHead className="text-right pr-4">Share</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {contributionTable.map((app) => (
                        <TableRow key={app.ad_unit_id}>
                          <TableCell className="pl-4 text-muted-foreground">{app.rank}</TableCell>
                          <TableCell className="text-xs font-medium max-w-[140px] truncate">{app.ad_unit_name}</TableCell>
                          <TableCell className="text-right text-emerald-500 text-xs">${app.revenue_usd.toFixed(4)}</TableCell>
                          <TableCell className="text-right pr-4">
                            <div className="flex items-center justify-end gap-2">
                              <div className="w-16 h-1.5 bg-muted rounded-full overflow-hidden">
                                <div className="h-full bg-indigo-500 rounded-full" style={{ width: `${app.revenue_pct}%` }} />
                              </div>
                              <span className="text-xs text-muted-foreground w-10 text-right">{app.revenue_pct.toFixed(1)}%</span>
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* ── 4. Revenue Distribution Donut ─────────────────────────────── */}
          <ReportDonutChart
            title="Revenue Distribution"
            description="Application-wise revenue share"
            data={donutData}
          />

          {/* ── 5 & 6. Top 10 / Bottom 10 ─────────────────────────────────── */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <ReportBarChart title="Top 10 Applications" description="By revenue" data={top10} valuePrefix="$" color="#10b981" highlightMax={false} highlightMin={false} />
            <ReportBarChart title="Bottom 10 Applications" description="By revenue" data={bottom10} valuePrefix="$" color="#f43f5e" highlightMax={false} highlightMin={false} />
          </div>

          {/* ── 7 & 8. Impression + Click Analysis ─────────────────────────── */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <ReportBarChart title="Impression Analysis" description="Impressions by application" data={impressionsByApp} color="#38bdf8" />
            <ReportBarChart title="Click Analysis" description="Clicks by application" data={clicksByApp} color="#fbbf24" />
          </div>

          {/* ── 9 & 10. eCPM + Fill Rate ───────────────────────────────────── */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <ReportBarChart title="eCPM Analysis" description="Average eCPM by application" data={ecpmByApp} layout="horizontal" valuePrefix="$" color="#a78bfa" height={Math.max(300, ecpmByApp.length * 28)} />
            <ReportBarChart title="Fill Rate Analysis" description="Fill rate by application" data={fillRateByApp} valueSuffix="%" color="#34d399" />
          </div>

          {/* ── 11 & 12. Ad Requests + CTR ─────────────────────────────────── */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <ReportBarChart title="Ad Request Analysis" description="Ad requests by application" data={adRequestsByApp} color="#22d3ee" />
            <ReportBarChart title="CTR Analysis" description="Click-through rate by application" data={ctrByApp} valueSuffix="%" color="#fb923c" />
          </div>

          {/* ── 13-16. Trend Charts ────────────────────────────────────────── */}
          <div>
            <h3 className="text-lg font-semibold mb-3">Trend Analysis</h3>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <ReportLineChart title="Revenue Trend" data={biData.dailyTrend} dataKey="revenue_usd" valuePrefix="$" color="#818cf8" />
              <ReportLineChart title="Impression Trend" data={biData.dailyTrend} dataKey="impressions" color="#38bdf8" />
              <ReportLineChart title="Click Trend" data={biData.dailyTrend} dataKey="clicks" color="#fbbf24" />
              <ReportLineChart title="eCPM Trend" data={biData.dailyTrend} dataKey="ecpm_usd" valuePrefix="$" color="#10b981" />
            </div>
          </div>

          {/* ── 17. Daily Comparison ───────────────────────────────────────── */}
          {dailyComparison.length > 0 && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Daily Comparison</CardTitle>
                <CardDescription>Last two days in the selected range</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {dailyComparison.map((row) => (
                    <div key={row.name} className="p-4 rounded-lg border bg-muted/20">
                      <p className="text-xs text-muted-foreground uppercase tracking-wider mb-2">{row.name}</p>
                      <div className="flex items-end justify-between">
                        <div>
                          <p className="text-xs text-muted-foreground">Yesterday</p>
                          <p className="text-lg font-bold">{row.yesterday.toLocaleString(undefined, { maximumFractionDigits: 4 })}</p>
                        </div>
                        <div className="text-right">
                          <p className="text-xs text-muted-foreground">Today</p>
                          <p className="text-lg font-bold">{row.today.toLocaleString(undefined, { maximumFractionDigits: 4 })}</p>
                        </div>
                      </div>
                      <div className={`mt-2 text-xs font-semibold ${row.diff >= 0 ? "text-emerald-500" : "text-rose-500"}`}>
                        {row.diff >= 0 ? "↑" : "↓"} {Math.abs(row.diff).toLocaleString(undefined, { maximumFractionDigits: 4 })}
                        {row.yesterday > 0 && ` (${((row.diff / row.yesterday) * 100).toFixed(1)}%)`}
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* ── 18. App Performance Scorecard ──────────────────────────────── */}
          <ReportDataTable data={biData.apps} />

          {/* ── 19. Anomaly Detection ──────────────────────────────────────── */}
          <ReportAnomalyCard anomalies={biData.anomalies} />

          {/* ── 20 & 21. AI Insights & Recommendations ────────────────────── */}
          <ReportInsights insights={biData.insights} />
        </>
      )}

      {/* Empty state */}
      {biData && !biLoading && biData.apps.length === 0 && (
        <Card>
          <CardContent className="py-16 text-center">
            <BarChart3 className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-lg font-medium mb-2">No Data Available</h3>
            <p className="text-sm text-muted-foreground">
              No revenue data found for {startDate} to {endDate}.
              Try selecting a different date range.
            </p>
          </CardContent>
        </Card>
      )}

      {/* ── Report History (Preserved) ──────────────────────────────────────── */}
      <Card className="print:hidden">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Database className="h-5 w-5 text-indigo-500" />
                Report History
              </CardTitle>
              <CardDescription>Recently generated reports.</CardDescription>
            </div>
            {history.some((h) => h.status === "Queued" || h.status === "Running") && (
              <Badge variant="outline" className="border-blue-400 text-blue-500 animate-pulse">
                <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                Processing…
              </Badge>
            )}
          </div>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Report Name</TableHead>
                <TableHead>Date</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Rows</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={5} className="h-32 text-center">
                    <Loader2 className="h-6 w-6 animate-spin mx-auto text-muted-foreground" />
                  </TableCell>
                </TableRow>
              ) : history.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} className="h-20 text-center text-muted-foreground">
                    No reports yet. Generate your first report above.
                  </TableCell>
                </TableRow>
              ) : (
                history.map((item) => (
                  <TableRow key={item.id} className="group">
                    <TableCell className="font-medium">{item.name}</TableCell>
                    <TableCell className="text-muted-foreground text-sm">{item.date}</TableCell>
                    <TableCell>
                      <div className="flex items-center">
                        <StatusIcon status={item.status} />
                        <span className={statusColor(item.status)}>{item.status}</span>
                      </div>
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {item.status === "Completed" ? item.rows.toLocaleString() : "—"}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-1 opacity-60 group-hover:opacity-100 transition-opacity">
                        <Button variant="ghost" size="icon" className="h-8 w-8 text-emerald-600" disabled={item.status !== "Completed"} onClick={() => handleDownload(item)}>
                          <Download className="h-4 w-4" />
                        </Button>
                        <Button variant="ghost" size="icon" className="h-8 w-8 text-red-500" onClick={() => handleDelete(item)} disabled={deletingId === item.id}>
                          {deletingId === item.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
