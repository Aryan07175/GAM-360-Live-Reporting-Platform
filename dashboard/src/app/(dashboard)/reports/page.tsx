"use client";

import { useEffect, useMemo } from "react";
import { useLiveReport } from "@/contexts/DateContext";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import {
  Play, Loader2, RefreshCw, BarChart3, Zap, AlertTriangle,
  Lightbulb, Award, TrendingUp, TrendingDown,
} from "lucide-react";
import { format, parseISO } from "date-fns";
import { LiveProgressBar } from "@/components/live/live-progress-bar";
import { KPISkeleton, ChartSkeleton, TableSkeleton } from "@/components/live/section-skeleton";
import { ReportKPICard } from "@/components/reports/report-kpi-card";
import { ReportBarChart } from "@/components/reports/report-bar-chart";
import { ReportDonutChart } from "@/components/reports/report-donut-chart";
import { ReportLineChart } from "@/components/reports/report-line-chart";
import { ReportDataTable } from "@/components/reports/report-data-table";
import { ReportAnomalyCard } from "@/components/reports/report-anomaly-card";
import { ReportInsights } from "@/components/reports/report-insights";
import { ReportExportBar } from "@/components/reports/report-export-bar";
import type { DatePreset } from "@/types";

const DATE_PRESETS: { value: DatePreset; label: string }[] = [
  { value: "today", label: "Today" },
  { value: "yesterday", label: "Yesterday" },
  { value: "last7days", label: "Last 7 Days" },
  { value: "last30days", label: "Last 30 Days" },
  { value: "thisMonth", label: "This Month" },
  { value: "lastMonth", label: "Last Month" },
];

export default function ReportsPage() {
  const {
    datePreset,
    startDate,
    endDate,
    setDatePreset,
    setCustomRange,
    summaryData,
    appsData,
    trendData,
    anomalyData,
    recommendationData,
    rankingData,
    reportData,
    isLoading,
    progress,
    lastFetchedAt,
    generateReport,
    refresh,
  } = useLiveReport();

  // Auto-generate on mount
  useEffect(() => {
    if (!reportData) {
      generateReport();
    }
  }, [reportData, generateReport]);

  const displayRange =
    startDate === endDate
      ? format(parseISO(startDate), "MMM dd, yyyy")
      : `${format(parseISO(startDate), "MMM dd")} → ${format(parseISO(endDate), "MMM dd, yyyy")}`;

  // ── Computed chart data ──
  const revenueByApp = useMemo(() => {
    if (!appsData) return [];
    return appsData.apps.map((a) => ({
      name: a.ad_unit_name.length > 25 ? a.ad_unit_name.substring(0, 25) + "…" : a.ad_unit_name,
      value: a.revenue_usd,
      fullName: a.ad_unit_name,
    }));
  }, [appsData]);

  const top10 = useMemo(() => revenueByApp.slice(0, 10), [revenueByApp]);
  const bottom10 = useMemo(() => [...revenueByApp].reverse().slice(0, 10), [revenueByApp]);

  const impressionsByApp = useMemo(() => {
    if (!appsData) return [];
    return appsData.apps.slice(0, 20).map((a) => ({
      name: a.ad_unit_name.length > 20 ? a.ad_unit_name.substring(0, 20) + "…" : a.ad_unit_name,
      value: a.impressions,
    }));
  }, [appsData]);

  const ecpmByApp = useMemo(() => {
    if (!appsData) return [];
    return [...appsData.apps].sort((a, b) => b.ecpm_usd - a.ecpm_usd).slice(0, 20).map((a) => ({
      name: a.ad_unit_name.length > 25 ? a.ad_unit_name.substring(0, 25) + "…" : a.ad_unit_name,
      value: a.ecpm_usd,
    }));
  }, [appsData]);

  const fillRateByApp = useMemo(() => {
    if (!appsData) return [];
    return [...appsData.apps].sort((a, b) => b.fill_rate_pct - a.fill_rate_pct).slice(0, 20).map((a) => ({
      name: a.ad_unit_name.length > 20 ? a.ad_unit_name.substring(0, 20) + "…" : a.ad_unit_name,
      value: a.fill_rate_pct,
    }));
  }, [appsData]);

  const ctrByApp = useMemo(() => {
    if (!appsData) return [];
    return [...appsData.apps].filter((a) => a.ctr_pct > 0).sort((a, b) => b.ctr_pct - a.ctr_pct).slice(0, 20).map((a) => ({
      name: a.ad_unit_name.length > 20 ? a.ad_unit_name.substring(0, 20) + "…" : a.ad_unit_name,
      value: a.ctr_pct,
    }));
  }, [appsData]);

  const adRequestsByApp = useMemo(() => {
    if (!appsData) return [];
    return [...appsData.apps].sort((a, b) => b.ad_requests - a.ad_requests).slice(0, 20).map((a) => ({
      name: a.ad_unit_name.length > 20 ? a.ad_unit_name.substring(0, 20) + "…" : a.ad_unit_name,
      value: a.ad_requests,
    }));
  }, [appsData]);

  const donutData = useMemo(() => {
    if (!appsData) return [];
    const topN = appsData.apps.slice(0, 8);
    const rest = appsData.apps.slice(8);
    const restTotal = rest.reduce((s, a) => s + a.revenue_usd, 0);
    const items = topN.map((a) => ({
      name: a.ad_unit_name.length > 20 ? a.ad_unit_name.substring(0, 20) + "…" : a.ad_unit_name,
      value: a.revenue_usd,
    }));
    if (restTotal > 0) items.push({ name: `Others (${rest.length})`, value: restTotal });
    return items;
  }, [appsData]);

  const contributionTable = useMemo(() => {
    if (!appsData || !summaryData) return [];
    const totalRev = summaryData.summary.find((s) => s.label === "Total Revenue")?.value || 1;
    return appsData.apps.slice(0, 20).map((a) => ({
      ...a,
      revenue_pct: (a.revenue_usd / totalRev) * 100,
    }));
  }, [appsData, summaryData]);

  return (
    <div className="space-y-6 print:space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <BarChart3 className="h-6 w-6 text-indigo-500" />
            Live Executive Report
          </h2>
          <p className="text-muted-foreground">
            Comprehensive analytics powered by live Google Ad Manager data • {displayRange}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {reportData && <ReportExportBar data={reportData} />}
          <Button
            variant="outline"
            size="sm"
            onClick={() => refresh()}
            disabled={isLoading}
            className="gap-2"
          >
            <RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Date Preset Quick Selector */}
      <Card className="print:hidden">
        <CardContent className="pt-5 pb-4">
          <div className="flex flex-wrap items-end gap-3">
            {/* Preset Buttons */}
            <div className="flex flex-wrap gap-1.5">
              {DATE_PRESETS.map((p) => (
                <Button
                  key={p.value}
                  variant={datePreset === p.value ? "default" : "outline"}
                  size="sm"
                  className={`h-8 text-xs ${
                    datePreset === p.value
                      ? "bg-indigo-600 hover:bg-indigo-700 text-white"
                      : ""
                  }`}
                  onClick={() => setDatePreset(p.value)}
                >
                  {p.label}
                </Button>
              ))}
            </div>

            {/* Custom Range */}
            <div className="flex items-center gap-2">
              <input
                type="date"
                className="h-8 rounded-md border bg-background px-2 py-1 text-xs ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring"
                value={startDate}
                onChange={(e) => {
                  if (e.target.value) setCustomRange(e.target.value, endDate);
                }}
              />
              <span className="text-xs text-muted-foreground">→</span>
              <input
                type="date"
                className="h-8 rounded-md border bg-background px-2 py-1 text-xs ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring"
                value={endDate}
                onChange={(e) => {
                  if (e.target.value) setCustomRange(startDate, e.target.value);
                }}
              />
            </div>

            {/* Generate */}
            <Button
              className="bg-indigo-600 hover:bg-indigo-700 text-white h-8 text-xs"
              onClick={() => generateReport(true)}
              disabled={isLoading}
            >
              {isLoading ? (
                <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
              ) : (
                <Zap className="h-3.5 w-3.5 mr-1.5" />
              )}
              {isLoading ? "Generating..." : "Generate Live Report"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Progress */}
      <LiveProgressBar progress={progress} isLoading={isLoading} />

      {/* ═══════════════════ REPORT SECTIONS ═══════════════════ */}

      {/* 1. Executive Summary KPIs */}
      {(isLoading && !summaryData) ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 8 }).map((_, i) => <KPISkeleton key={i} />)}
        </div>
      ) : summaryData && summaryData.summary.length > 0 ? (
        <div>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-lg font-semibold">Executive Summary</h3>
            <span className="text-xs text-muted-foreground">
              Fetched at {new Date(summaryData.fetchedAt).toLocaleTimeString()}
            </span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {summaryData.summary.map((kpi) => (
              <ReportKPICard key={kpi.label} kpi={kpi} />
            ))}
          </div>
        </div>
      ) : null}

      {/* 2. Revenue by Application + Contribution Table */}
      {(isLoading && !appsData) ? (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-6">
          <div className="lg:col-span-2"><ChartSkeleton height={400} /></div>
          <TableSkeleton rows={10} />
        </div>
      ) : appsData && appsData.apps.length > 0 ? (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-6">
          <div className="lg:col-span-2">
            <ReportBarChart
              title="Revenue by Application"
              description="Sorted by revenue (descending)"
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
      ) : null}

      {/* 3. Revenue Distribution Donut */}
      {appsData && appsData.apps.length > 0 && (
        <div className="mt-6">
          <ReportDonutChart title="Revenue Distribution" description="Application-wise revenue share" data={donutData} />
        </div>
      )}

      {/* 4. Top 10 / Bottom 10 */}
      {appsData && appsData.apps.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
          <ReportBarChart title="Top 10 Applications" description="By revenue" data={top10} valuePrefix="$" color="#10b981" highlightMax={false} highlightMin={false} />
          <ReportBarChart title="Bottom 10 Applications" description="By revenue" data={bottom10} valuePrefix="$" color="#f43f5e" highlightMax={false} highlightMin={false} />
        </div>
      )}

      {/* 5. Impressions / Clicks / CTR / Fill Rate / eCPM / Ad Requests */}
      {appsData && appsData.apps.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
          <ReportBarChart title="Impressions by Application" description="Top 20 by impressions" data={impressionsByApp} color="#38bdf8" />
          <ReportBarChart title="eCPM by Application" description="Top 20 by eCPM" data={ecpmByApp} valuePrefix="$" color="#a78bfa" />
          <ReportBarChart title="Fill Rate by Application" description="Top 20 by fill rate" data={fillRateByApp} valueSuffix="%" color="#34d399" />
          <ReportBarChart title="CTR by Application" description="Apps with clicks" data={ctrByApp} valueSuffix="%" color="#fb923c" />
          <ReportBarChart title="Ad Requests by Application" description="Top 20 by volume" data={adRequestsByApp} color="#f472b6" />
        </div>
      )}

      {/* 6. Trend Charts */}
      {(isLoading && !trendData) ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
          <ChartSkeleton />
          <ChartSkeleton />
        </div>
      ) : trendData && trendData.trend.length > 0 ? (
        <div className="mt-6">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-lg font-semibold">Trend Analysis</h3>
            <span className="text-xs text-muted-foreground">
              Fetched at {new Date(trendData.fetchedAt).toLocaleTimeString()}
            </span>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <ReportLineChart title="Revenue Trend" data={trendData.trend} dataKey="revenue_usd" valuePrefix="$" color="#818cf8" />
            <ReportLineChart title="Impression Trend" data={trendData.trend} dataKey="impressions" color="#38bdf8" />
          </div>
        </div>
      ) : null}

      {/* 7. Performance Scorecard */}
      {appsData && appsData.apps.length > 0 && (
        <div className="mt-6">
          <ReportDataTable data={appsData.apps} />
        </div>
      )}

      {/* 8. Anomaly Detection */}
      {anomalyData && anomalyData.anomalies.length > 0 && (
        <div className="mt-6">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-lg font-semibold flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-amber-500" />
              Anomaly Detection
            </h3>
            <span className="text-xs text-muted-foreground">
              Compared to previous period
            </span>
          </div>
          <ReportAnomalyCard anomalies={anomalyData.anomalies} />
        </div>
      )}

      {/* 9. Recommendations */}
      {recommendationData && recommendationData.recommendations.length > 0 && (
        <div className="mt-6">
          <h3 className="text-lg font-semibold flex items-center gap-2 mb-3">
            <Lightbulb className="h-5 w-5 text-amber-500" />
            AI Recommendations
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {recommendationData.recommendations.map((rec: any) => (
              <Card key={rec.id} className="border-l-4 border-l-indigo-500">
                <CardContent className="pt-4 pb-3">
                  <div className="flex items-start gap-3">
                    <span className="text-2xl">{rec.icon}</span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <p className="text-sm font-semibold">{rec.title}</p>
                        <Badge
                          variant="outline"
                          className={`text-[10px] ${
                            rec.priority === "High"
                              ? "border-rose-500/30 text-rose-500"
                              : rec.priority === "Medium"
                              ? "border-amber-500/30 text-amber-500"
                              : "border-emerald-500/30 text-emerald-500"
                          }`}
                        >
                          {rec.priority}
                        </Badge>
                      </div>
                      <p className="text-xs text-muted-foreground leading-relaxed">
                        {rec.description}
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* 10. Performance Rankings */}
      {rankingData && rankingData.rankings.length > 0 && (
        <div className="mt-6">
          <h3 className="text-lg font-semibold flex items-center gap-2 mb-3">
            <Award className="h-5 w-5 text-indigo-500" />
            Performance Ranking
          </h3>
          <Card>
            <CardContent className="pt-4">
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-12">#</TableHead>
                      <TableHead>Application</TableHead>
                      <TableHead className="text-right">Revenue</TableHead>
                      <TableHead className="text-right">Impressions</TableHead>
                      <TableHead className="text-right">eCPM</TableHead>
                      <TableHead className="text-right">Fill Rate</TableHead>
                      <TableHead className="text-right">Score</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {rankingData.rankings.slice(0, 20).map((r) => (
                      <TableRow key={r.ad_unit_id}>
                        <TableCell className="font-bold text-indigo-500">{r.rank}</TableCell>
                        <TableCell className="font-medium text-sm max-w-[200px] truncate">{r.ad_unit_name}</TableCell>
                        <TableCell className="text-right text-emerald-500 text-xs">${r.revenue_usd.toFixed(4)}</TableCell>
                        <TableCell className="text-right text-xs">{r.impressions.toLocaleString()}</TableCell>
                        <TableCell className="text-right text-xs">${r.ecpm_usd.toFixed(4)}</TableCell>
                        <TableCell className="text-right text-xs">{r.fill_rate_pct.toFixed(1)}%</TableCell>
                        <TableCell className="text-right">
                          <div className="flex items-center justify-end gap-2">
                            <div className="w-12 h-1.5 bg-muted rounded-full overflow-hidden">
                              <div
                                className="h-full bg-indigo-500 rounded-full"
                                style={{ width: `${r.score}%` }}
                              />
                            </div>
                            <span className="text-xs font-medium w-8 text-right">{r.score.toFixed(0)}</span>
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
      )}

      {/* Empty state */}
      {!isLoading && appsData && appsData.apps.length === 0 && (
        <Card>
          <CardContent className="py-16 text-center">
            <BarChart3 className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-lg font-medium mb-2">No Data Available</h3>
            <p className="text-sm text-muted-foreground">
              No revenue data found for {displayRange}. Try selecting a different date range.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
