"use client";

import { useEffect } from "react";
import {
  DollarSign,
  MousePointerClick,
  Eye,
  Activity,
  Percent,
  ArrowRightLeft,
  Trophy,
  ArrowRight,
  TrendingUp,
  TrendingDown,
  Zap,
  BarChart3,
  Users,
} from "lucide-react";
import { KPICard } from "@/components/cards/kpi-card";
import { TrendChart } from "@/components/charts/trend-chart";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useLiveReport } from "@/contexts/DateContext";
import { LiveProgressBar } from "@/components/live/live-progress-bar";
import { KPISkeleton, ChartSkeleton } from "@/components/live/section-skeleton";
import { format, parseISO } from "date-fns";
import Link from "next/link";

export default function DashboardOverview() {
  const {
    startDate,
    endDate,
    datePreset,
    summaryData,
    appsData,
    trendData,
    isLoading,
    progress,
    lastFetchedAt,
    generateReport,
  } = useLiveReport();

  // Auto-generate report on mount
  useEffect(() => {
    generateReport();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [startDate, endDate]);

  const displayRange =
    startDate === endDate
      ? format(parseISO(startDate), "MMM dd, yyyy")
      : `${format(parseISO(startDate), "MMM dd")} → ${format(parseISO(endDate), "MMM dd, yyyy")}`;

  // Extract values from summary
  const getKPI = (label: string) =>
    summaryData?.summary.find((s) => s.label === label);

  const totalRev = getKPI("Total Revenue");
  const totalImp = getKPI("Total Impressions");
  const totalClicks = getKPI("Total Clicks");
  const avgEcpm = getKPI("Average eCPM");
  const ctr = getKPI("CTR");
  const fillRate = getKPI("Fill Rate");
  const adRequests = getKPI("Ad Requests");
  const activeApps = getKPI("Active Apps");

  // Calculate DAU as Ad Requests / 5
  const dauValue = adRequests?.value ? Math.round(adRequests.value / 5) : 0;
  const dauFormatted = dauValue.toLocaleString();

  const topApps = (appsData?.apps || []).slice(0, 5);
  const maxAppRevenue =
    topApps.length > 0
      ? Math.max(...topApps.map((a) => a.revenue_usd))
      : 1;

  const trendPoints = (trendData?.trend || []).map(p => ({
    ...p,
    dau: Math.round((p.ad_requests || 0) / 5)
  }));

  const hasData = !!summaryData || !!appsData || !!trendData;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <Zap className="h-6 w-6 text-indigo-500" />
            Live Dashboard
          </h2>
          <p className="text-muted-foreground">
            Real-time network metrics from Google Ad Manager
            <span className="ml-2 text-xs font-medium text-indigo-500">
              • {displayRange}
            </span>
          </p>
        </div>
        {lastFetchedAt && (
          <Badge
            variant="outline"
            className="border-emerald-500/30 text-emerald-600 dark:text-emerald-400"
          >
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 mr-1.5 animate-pulse" />
            Live Data
          </Badge>
        )}
      </div>

      {/* Progress */}
      <LiveProgressBar progress={progress} isLoading={isLoading} />

      {/* Empty state - show prompt */}
      {!hasData && !isLoading && (
        <Card className="border-dashed">
          <CardContent className="py-16 text-center">
            <BarChart3 className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-lg font-medium mb-2">
              Ready to Fetch Live Data
            </h3>
            <p className="text-sm text-muted-foreground mb-4">
              Select a date range and click Refresh to fetch live data from
              Google Ad Manager.
            </p>
            <Button
              className="bg-indigo-600 hover:bg-indigo-700 text-white"
              onClick={() => generateReport()}
            >
              <Zap className="h-4 w-4 mr-2" />
              Generate Live Report
            </Button>
          </CardContent>
        </Card>
      )}

      {/* KPI Grid */}
      {(isLoading && !summaryData) ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <KPISkeleton key={i} />
          ))}
        </div>
      ) : summaryData ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <KPICard
            title="Total Revenue"
            value={totalRev?.formatted || "$0.00"}
            icon={<DollarSign className="h-4 w-4" />}
            loading={false}
          />
          <KPICard
            title="Impressions"
            value={totalImp?.formatted || "0"}
            icon={<Eye className="h-4 w-4" />}
            loading={false}
          />
          <KPICard
            title="Clicks"
            value={totalClicks?.formatted || "0"}
            icon={<MousePointerClick className="h-4 w-4" />}
            loading={false}
          />
          <KPICard
            title="Avg eCPM"
            value={avgEcpm?.formatted || "$0.00"}
            icon={<Activity className="h-4 w-4" />}
            loading={false}
          />
          <KPICard
            title="Daily Active Users"
            value={dauFormatted}
            icon={<Users className="h-4 w-4" />}
            loading={false}
          />
          <KPICard
            title="Fill Rate"
            value={fillRate?.formatted || "0.00%"}
            icon={<Percent className="h-4 w-4" />}
            loading={false}
          />
          <KPICard
            title="Ad Requests"
            value={adRequests?.formatted || "0"}
            icon={<ArrowRightLeft className="h-4 w-4" />}
            loading={false}
          />
          <KPICard
            title="Active Apps"
            value={activeApps?.formatted || "0"}
            icon={<Activity className="h-4 w-4" />}
            loading={false}
          />
        </div>
      ) : null}

      {/* Charts + Top Apps */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Left: Trend Charts */}
        <div className="lg:col-span-2 space-y-6">
          {(isLoading && !trendData) ? (
            <>
              <ChartSkeleton />
              <ChartSkeleton />
            </>
          ) : trendPoints.length > 0 ? (
            <>
              <TrendChart
                title="Revenue Trend"
                description={`Daily revenue (${displayRange})`}
                data={trendPoints}
                dataKey="revenue_usd"
                xAxisKey="report_date"
                valuePrefix="$"
                color="#818cf8"
              />
              <TrendChart
                title="Daily Active Users"
                description={`Estimated DAU (${displayRange})`}
                data={trendPoints}
                dataKey="dau"
                xAxisKey="report_date"
                color="#f59e0b"
              />
              <TrendChart
                title="Impressions Trend"
                description={`Daily impressions (${displayRange})`}
                data={trendPoints}
                dataKey="impressions"
                xAxisKey="report_date"
                color="#0ea5e9"
              />
              <TrendChart
                title="eCPM Trend"
                description={`Daily eCPM (${displayRange})`}
                data={trendPoints}
                dataKey="ecpm_usd"
                xAxisKey="report_date"
                valuePrefix="$"
                color="#2dd4bf"
              />
            </>
          ) : null}
        </div>

        {/* Right: Top Apps */}
        <div className="space-y-6">
          {(isLoading && !appsData) ? (
            <Card>
              <CardContent className="pt-6">
                <div className="space-y-4">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <div key={i} className="animate-pulse space-y-2">
                      <div className="h-4 bg-muted rounded w-3/4" />
                      <div className="h-2 bg-muted rounded w-full" />
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          ) : topApps.length > 0 ? (
            <Card className="h-fit">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Trophy className="h-5 w-5 text-amber-500" />
                    <CardTitle className="text-base">
                      Top Performing Apps
                    </CardTitle>
                  </div>
                  <Link
                    href="/applications"
                    className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1 transition-colors"
                  >
                    View all <ArrowRight className="h-3 w-3" />
                  </Link>
                </div>
                <CardDescription>By revenue • {displayRange}</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {topApps.map((app, idx) => {
                    const pct =
                      maxAppRevenue > 0
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

                    const fillRateVal = app.fill_rate_pct;
                    const healthLabel =
                      fillRateVal > 80
                        ? "Healthy"
                        : fillRateVal > 50
                        ? "Fair"
                        : "Low";
                    const healthClass =
                      fillRateVal > 80
                        ? "bg-emerald-500/10 text-emerald-500 border-emerald-500/20"
                        : fillRateVal > 50
                        ? "bg-amber-500/10 text-amber-500 border-amber-500/20"
                        : "bg-rose-500/10 text-rose-500 border-rose-500/20";

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

                        <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all duration-500 ${barColors[idx]}`}
                            style={{ width: `${pct}%` }}
                          />
                        </div>

                        <div className="flex items-center justify-between text-xs text-muted-foreground">
                          <div className="flex items-center gap-2">
                            <span>
                              {app.impressions.toLocaleString()} impr.
                            </span>
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
              </CardContent>
            </Card>
          ) : null}
        </div>
      </div>
    </div>
  );
}
