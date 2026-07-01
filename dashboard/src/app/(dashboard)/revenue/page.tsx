"use client";

import { useEffect, useState } from "react";
import { getRevenueByApp, getRevenueTrend, getLatestReportDate } from "@/services/api";
import { AppMetrics, TrendDataPoint } from "@/types";
import { TrendChart } from "@/components/charts/trend-chart";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Loader2 } from "lucide-react";

export default function RevenueAnalyticsPage() {
  const [apps, setApps] = useState<AppMetrics[]>([]);
  const [trend, setTrend] = useState<TrendDataPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [dataDate, setDataDate] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      setLoading(true);
      const latestDate = await getLatestReportDate();
      const dateToQuery = latestDate || new Date().toISOString().split("T")[0];
      setDataDate(latestDate);

      const [appData, trendData] = await Promise.all([
        getRevenueByApp(dateToQuery),
        getRevenueTrend(30),
      ]);
      
      setApps(appData);
      setTrend(trendData.reverse());
      setLoading(false);
    }
    load();
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Revenue Analytics</h2>
        <p className="text-muted-foreground">
          Deep dive into your monetization performance and yield.
        </p>
      </div>

      {loading ? (
        <div className="flex h-[400px] items-center justify-center rounded-lg border border-dashed">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <TrendChart
              title="Revenue Trend (30 Days)"
              description="Daily network revenue in USD"
              data={trend}
              dataKey="revenue_usd"
              xAxisKey="report_date"
              valuePrefix="$"
              color="#4f46e5"
            />
            <TrendChart
              title="eCPM Trend (30 Days)"
              description="Average effective cost per mille"
              data={trend}
              dataKey="ecpm_usd"
              xAxisKey="report_date"
              valuePrefix="$"
              color="#10b981"
            />
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Top Earning Applications</CardTitle>
              <CardDescription>
                Highest yielding ad units {dataDate ? `for ${dataDate}` : "today"}
              </CardDescription>
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
                          <TableCell className="font-medium">
                            {app.ad_unit_name}
                          </TableCell>
                          <TableCell className="text-right font-medium text-emerald-600 dark:text-emerald-400">
                            ${app.revenue_usd.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 6 })}
                          </TableCell>
                          <TableCell className="text-right">
                            {app.impressions.toLocaleString()}
                          </TableCell>
                          <TableCell className="text-right">
                            ${app.ecpm_usd.toFixed(6)}
                          </TableCell>
                          <TableCell className="text-right">
                            {app.fill_rate_pct !== null && app.fill_rate_pct !== undefined ? `${app.fill_rate_pct.toFixed(1)}%` : "N/A"}
                          </TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
