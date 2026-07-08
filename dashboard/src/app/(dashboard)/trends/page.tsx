"use client";

import { useEffect } from "react";
import { useLiveReport } from "@/contexts/DateContext";
import { TrendChart } from "@/components/charts/trend-chart";
import { Card, CardContent } from "@/components/ui/card";
import { Zap, BarChart3 } from "lucide-react";
import { format, parseISO } from "date-fns";
import { ChartSkeleton } from "@/components/live/section-skeleton";

export default function TrendAnalysisPage() {
  const { startDate, endDate, trendData, isLoading, generateReport } = useLiveReport();

  useEffect(() => {
    if (!trendData) generateReport();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [startDate, endDate]);

  const trendPoints = trendData?.trend || [];

  const displayRange =
    startDate === endDate
      ? format(parseISO(startDate), "MMM dd, yyyy")
      : `${format(parseISO(startDate), "MMM dd")} → ${format(parseISO(endDate), "MMM dd, yyyy")}`;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight flex items-center gap-2">
          <Zap className="h-5 w-5 text-indigo-500" />
          Trend Analysis
        </h2>
        <p className="text-muted-foreground">
          Live daily performance trends • {displayRange}
        </p>
      </div>

      {isLoading && !trendData ? (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <ChartSkeleton />
          <ChartSkeleton />
          <ChartSkeleton />
          <ChartSkeleton />
        </div>
      ) : trendPoints.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="py-16 text-center">
            <BarChart3 className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-lg font-medium mb-2">No Trend Data</h3>
            <p className="text-sm text-muted-foreground">
              Select a multi-day date range to see trends.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <TrendChart
            title="Revenue Trend"
            description="Daily total revenue"
            data={trendPoints}
            dataKey="revenue_usd"
            xAxisKey="report_date"
            valuePrefix="$"
            color="#818cf8"
          />
          <TrendChart
            title="Impressions Trend"
            description="Daily ad impressions"
            data={trendPoints}
            dataKey="impressions"
            xAxisKey="report_date"
            color="#0ea5e9"
          />
          <TrendChart
            title="eCPM Trend"
            description="Daily effective CPM"
            data={trendPoints}
            dataKey="ecpm_usd"
            xAxisKey="report_date"
            valuePrefix="$"
            color="#2dd4bf"
          />
          <TrendChart
            title="Clicks Trend"
            description="Daily click volume"
            data={trendPoints}
            dataKey="clicks"
            xAxisKey="report_date"
            color="#f97316"
          />
        </div>
      )}
    </div>
  );
}
