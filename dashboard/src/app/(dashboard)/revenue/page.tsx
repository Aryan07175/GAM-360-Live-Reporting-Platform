"use client";

import { useEffect } from "react";
import { useLiveReport } from "@/contexts/DateContext";
import { TrendChart } from "@/components/charts/trend-chart";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Loader2, Zap } from "lucide-react";
import { format, parseISO } from "date-fns";
import { ChartSkeleton, TableSkeleton } from "@/components/live/section-skeleton";

export default function RevenueAnalyticsPage() {
  const { startDate, endDate, appsData, trendData, isLoading, generateReport } = useLiveReport();

  useEffect(() => {
    if (!appsData) generateReport();
  }, [appsData, generateReport]);

  const displayRange =
    startDate === endDate
      ? format(parseISO(startDate), "MMM dd, yyyy")
      : `${format(parseISO(startDate), "MMM dd")} → ${format(parseISO(endDate), "MMM dd, yyyy")}`;

  const apps = appsData?.apps || [];
  const trendPoints = trendData?.trend || [];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight flex items-center gap-2">
          <Zap className="h-5 w-5 text-indigo-500" />
          Revenue Analytics
        </h2>
        <p className="text-muted-foreground">
          Live monetization performance • {displayRange}
        </p>
      </div>

      {(isLoading && !trendData) ? (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <ChartSkeleton />
          <ChartSkeleton />
        </div>
      ) : trendPoints.length > 0 ? (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <TrendChart
            title="Revenue Trend"
            description="Daily network revenue in USD"
            data={trendPoints}
            dataKey="revenue_usd"
            xAxisKey="report_date"
            valuePrefix="$"
            color="#4f46e5"
          />
          <TrendChart
            title="eCPM Trend"
            description="Average effective cost per mille"
            data={trendPoints}
            dataKey="ecpm_usd"
            xAxisKey="report_date"
            valuePrefix="$"
            color="#10b981"
          />
        </div>
      ) : null}

      {(isLoading && !appsData) ? (
        <TableSkeleton rows={10} />
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Top Earning Applications</CardTitle>
            <CardDescription>Live data • {displayRange}</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>App Name</TableHead>
                    <TableHead className="text-right">Revenue</TableHead>
                    <TableHead className="text-right">Impressions</TableHead>
                    <TableHead className="text-right">eCPM</TableHead>
                    <TableHead className="text-right">Fill Rate</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {apps.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={5} className="h-24 text-center text-muted-foreground">
                        No revenue data available.
                      </TableCell>
                    </TableRow>
                  ) : (
                    apps.slice(0, 10).map((app) => (
                      <TableRow key={app.ad_unit_id}>
                        <TableCell className="font-medium">{app.ad_unit_name}</TableCell>
                        <TableCell className="text-right font-medium text-emerald-600 dark:text-emerald-400">
                          ${app.revenue_usd.toFixed(6)}
                        </TableCell>
                        <TableCell className="text-right">{app.impressions.toLocaleString()}</TableCell>
                        <TableCell className="text-right">${app.ecpm_usd.toFixed(6)}</TableCell>
                        <TableCell className="text-right">{app.fill_rate_pct.toFixed(1)}%</TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
