"use client";

import { useEffect, useState } from "react";
import {
  DollarSign,
  MousePointerClick,
  Eye,
  Activity,
  Percent,
  ArrowRightLeft,
  AlertCircle,
  Users,
  Trophy,
  ArrowRight,
  TrendingUp,
  TrendingDown,
} from "lucide-react";
import { KPICard } from "@/components/cards/kpi-card";
import { TrendChart } from "@/components/charts/trend-chart";
import { getNetworkTotal, getRevenueTrend, getRevenueByApp } from "@/services/api";
import { NetworkTotal, TrendDataPoint, AppMetrics } from "@/types";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useDateContext } from "@/contexts/DateContext";
import { format, parseISO } from "date-fns";
import Link from "next/link";

export default function DashboardOverview() {
  const { selectedDate, dateLoading, refreshKey } = useDateContext();
  const [total, setTotal] = useState<NetworkTotal | null>(null);
  const [trend, setTrend] = useState<TrendDataPoint[]>([]);
  const [topApps, setTopApps] = useState<AppMetrics[]>([]);
  const [loading, setLoading] = useState(true);
  const [noData, setNoData] = useState(false);

  useEffect(() => {
    if (dateLoading || !selectedDate) return;

    async function loadData() {
      setLoading(true);
      setNoData(false);

      const [totalData, trendData, appsData] = await Promise.all([
        getNetworkTotal(selectedDate!),
        getRevenueTrend(30),
        getRevenueByApp(selectedDate!),
      ]);

      if (!totalData) {
        setNoData(true);
      }

      setTotal(totalData);
      setTrend(trendData.reverse());
      setTopApps(appsData.slice(0, 5));
      setLoading(false);
    }
    loadData();
  }, [selectedDate, dateLoading, refreshKey]);

  const displayDate = selectedDate
    ? format(parseISO(selectedDate), "MMM dd, yyyy")
    : null;

  // Compute max revenue among top apps (for relative bar widths)
  const maxAppRevenue = topApps.length > 0
    ? Math.max(...topApps.map((a) => a.revenue_usd))
    : 1;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Overview</h2>
        <p className="text-muted-foreground">
          Monitor your network&apos;s high-level metrics and trends.
          {displayDate && (
            <span className="ml-2 text-xs font-medium text-emerald-600 dark:text-emerald-400">
              • Showing data for {displayDate}
            </span>
          )}
        </p>
      </div>

      {/* No data warning banner */}
      {noData && !loading && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>No data available for {displayDate}</AlertTitle>
          <AlertDescription>
            No revenue data was found in the database for this date.
            This typically means the GAM pipeline has not yet synced data for this day.
            Try selecting a different date using the date picker in the header.
          </AlertDescription>
        </Alert>
      )}

      {/* ── KPI Grid ─────────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KPICard
          title="Total Revenue"
          value={
            total
              ? `$${total.total_revenue_usd.toLocaleString(undefined, {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 6,
                })}`
              : noData ? "—" : "$0.00"
          }
          icon={<DollarSign className="h-4 w-4" />}
          loading={loading}
          subtitle={noData ? "No data for this date" : undefined}
        />
        <KPICard
          title="Impressions"
          value={total ? total.total_impressions.toLocaleString() : noData ? "—" : "0"}
          icon={<Eye className="h-4 w-4" />}
          loading={loading}
          subtitle={noData ? "No data for this date" : undefined}
        />
        {/* ── DAILY ACTIVE USERS (DAU) ── */}
        <KPICard
          title="Daily Active Users"
          value={
            total
              ? total.total_ad_requests > 0
                ? total.total_ad_requests.toLocaleString()
                : total.total_impressions > 0
                  ? total.total_impressions.toLocaleString()
                  : "—"
              : noData ? "—" : "0"
          }
          icon={<Users className="h-4 w-4" />}
          loading={loading}
          subtitle={
            noData
              ? "No data for this date"
              : total && total.total_ad_requests > 0
              ? "Based on ad requests"
              : total && total.total_impressions > 0
              ? "Based on impressions"
              : undefined
          }
        />
        <KPICard
          title="Avg eCPM"
          value={total ? `$${total.avg_ecpm.toFixed(6)}` : noData ? "—" : "$0.00"}
          icon={<Activity className="h-4 w-4" />}
          loading={loading}
          subtitle={noData ? "No data for this date" : undefined}
        />

        <KPICard
          title="Fill Rate"
          value={
            total
              ? total.avg_fill_rate !== null
                ? `${total.avg_fill_rate.toFixed(1)}%`
                : "N/A"
              : noData ? "—" : "N/A"
          }
          icon={<Percent className="h-4 w-4" />}
          loading={loading}
          subtitle={
            total && total.avg_fill_rate === null
              ? "No ad requests recorded for this date"
              : noData
              ? "No data for this date"
              : undefined
          }
        />
        <KPICard
          title="Clicks"
          value={total ? total.total_clicks.toLocaleString() : noData ? "—" : "0"}
          icon={<MousePointerClick className="h-4 w-4" />}
          loading={loading}
          subtitle={noData ? "No data for this date" : undefined}
        />
        <KPICard
          title="Ad Requests"
          value={total ? total.total_ad_requests.toLocaleString() : noData ? "—" : "0"}
          icon={<ArrowRightLeft className="h-4 w-4" />}
          loading={loading}
          subtitle={noData ? "No data for this date" : undefined}
        />
        <KPICard
          title="Active Apps"
          value={total ? total.app_count.toLocaleString() : noData ? "—" : "0"}
          icon={<Activity className="h-4 w-4" />}
          loading={loading}
          subtitle={noData ? "No data for this date" : "Ad units with revenue"}
        />
      </div>

      {/* ── Charts + Top Apps ─────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Left: Trend Charts */}
        <div className="lg:col-span-2 space-y-6">
          <TrendChart
            title="Revenue Trend (30 Days)"
            description="Daily total revenue in USD"
            data={trend}
            dataKey="revenue_usd"
            xAxisKey="report_date"
            valuePrefix="$"
            color="#818cf8"
          />
          <TrendChart
            title="Impressions Trend (30 Days)"
            description="Daily ad impressions"
            data={trend}
            dataKey="impressions"
            xAxisKey="report_date"
            color="#0ea5e9"
          />
          <TrendChart
            title="eCPM Trend (30 Days)"
            description="Average effective cost per mille"
            data={trend}
            dataKey="ecpm_usd"
            xAxisKey="report_date"
            valuePrefix="$"
            color="#2dd4bf"
          />
        </div>

        {/* Right: Top Performing Apps */}
        <div className="space-y-6">
          <Card className="h-fit">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Trophy className="h-5 w-5 text-amber-500" />
                  <CardTitle className="text-base">Top Performing Apps</CardTitle>
                </div>
                <Link
                  href="/applications"
                  className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1 transition-colors"
                >
                  View all <ArrowRight className="h-3 w-3" />
                </Link>
              </div>
              <CardDescription>
                By revenue {displayDate ? `on ${displayDate}` : ""}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="space-y-4">
                  {[...Array(5)].map((_, i) => (
                    <div key={i} className="animate-pulse space-y-2">
                      <div className="h-4 bg-muted rounded w-3/4" />
                      <div className="h-2 bg-muted rounded w-full" />
                    </div>
                  ))}
                </div>
              ) : topApps.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-8">
                  No app data for this date.
                </p>
              ) : (
                <div className="space-y-4">
                  {topApps.map((app, idx) => {
                    const pct = maxAppRevenue > 0
                      ? (app.revenue_usd / maxAppRevenue) * 100
                      : 0;
                    const rankColors = [
                      "text-amber-500",
                      "text-slate-400",
                      "text-orange-500",
                      "text-muted-foreground",
                      "text-muted-foreground",
                    ];
                    const barColors = [
                      "bg-indigo-500",
                      "bg-sky-500",
                      "bg-emerald-500",
                      "bg-violet-500",
                      "bg-rose-500",
                    ];

                    // Fill rate health badge
                    const fillRate = app.fill_rate_pct;
                    const healthLabel =
                      fillRate > 80
                        ? "Healthy"
                        : fillRate > 50
                        ? "Fair"
                        : "Low";
                    const healthClass =
                      fillRate > 80
                        ? "bg-emerald-500/10 text-emerald-500 border-emerald-500/20"
                        : fillRate > 50
                        ? "bg-amber-500/10 text-amber-500 border-amber-500/20"
                        : "bg-rose-500/10 text-rose-500 border-rose-500/20";

                    // Revenue trend icon (compare vs ecpm as proxy)
                    const isTrending = app.ecpm_usd > 0.003;

                    return (
                      <div key={app.ad_unit_id} className="space-y-1.5">
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex items-center gap-2 min-w-0">
                            <span
                              className={`text-sm font-bold shrink-0 w-5 ${rankColors[idx]}`}
                            >
                              #{idx + 1}
                            </span>
                            <span className="text-sm font-medium truncate text-foreground leading-tight">
                              {app.ad_unit_name}
                            </span>
                          </div>
                          <span className="text-sm font-semibold text-emerald-600 dark:text-emerald-400 shrink-0">
                            ${app.revenue_usd.toFixed(4)}
                          </span>
                        </div>

                        {/* Revenue bar */}
                        <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all duration-500 ${barColors[idx]}`}
                            style={{ width: `${pct}%` }}
                          />
                        </div>

                        {/* Meta row */}
                        <div className="flex items-center justify-between text-xs text-muted-foreground">
                          <div className="flex items-center gap-2">
                            <span>{app.impressions.toLocaleString()} impr.</span>
                            <span>•</span>
                            <span>eCPM ${app.ecpm_usd.toFixed(4)}</span>
                          </div>
                          <div className="flex items-center gap-1.5">
                            {isTrending ? (
                              <TrendingUp className="h-3 w-3 text-emerald-500" />
                            ) : (
                              <TrendingDown className="h-3 w-3 text-rose-500" />
                            )}
                            <span
                              className={`px-1.5 py-0.5 rounded text-[10px] font-medium border ${healthClass}`}
                            >
                              {healthLabel}
                            </span>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>

          {/* DAU Breakdown card */}
          {total && !noData && !loading && (
            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-center gap-2">
                  <Users className="h-5 w-5 text-sky-500" />
                  <CardTitle className="text-base">Daily Active Users</CardTitle>
                </div>
                <CardDescription>Ad engagement breakdown</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {[
                  {
                    label: "Total Ad Requests",
                    value: total.total_ad_requests.toLocaleString(),
                    pct: 100,
                    color: "bg-indigo-500",
                    sub: "Unique user sessions",
                  },
                  {
                    label: "Served Impressions",
                    value: total.total_impressions.toLocaleString(),
                    pct: total.total_ad_requests > 0
                      ? Math.round((total.total_impressions / total.total_ad_requests) * 100)
                      : total.avg_fill_rate ?? 0,
                    color: "bg-sky-500",
                    sub: `${total.avg_fill_rate?.toFixed(1) ?? "N/A"}% fill rate`,
                  },
                  {
                    label: "Clicks",
                    value: total.total_clicks.toLocaleString(),
                    pct: total.total_impressions > 0
                      ? Math.min(Math.round((total.total_clicks / total.total_impressions) * 10000) / 100, 100)
                      : 0,
                    color: "bg-emerald-500",
                    sub: "CTR engagement",
                  },
                ].map((row) => (
                  <div key={row.label} className="space-y-1.5">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">{row.label}</span>
                      <span className="font-semibold">{row.value}</span>
                    </div>
                    <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
                      <div
                        className={`h-full rounded-full ${row.color}`}
                        style={{ width: `${Math.min(row.pct, 100)}%` }}
                      />
                    </div>
                    <p className="text-[11px] text-muted-foreground">{row.sub}</p>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
