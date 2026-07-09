"use client";

import { useEffect, useMemo } from "react";
import { useLiveReport } from "@/contexts/DateContext";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Bell, AlertTriangle, TrendingDown, Eye, DollarSign, Zap } from "lucide-react";
import { format, parseISO } from "date-fns";
import { KPISkeleton } from "@/components/live/section-skeleton";

export default function AlertsPage() {
  const { startDate, endDate, appsData, isLoading, generateReport } = useLiveReport();

  useEffect(() => {
    if (!appsData) generateReport();
  }, [appsData, generateReport]);

  const displayRange =
    startDate === endDate
      ? format(parseISO(startDate), "MMM dd, yyyy")
      : `${format(parseISO(startDate), "MMM dd")} → ${format(parseISO(endDate), "MMM dd, yyyy")}`;

  // Generate alerts from live data
  const alerts = useMemo(() => {
    if (!appsData) return [];
    const result: any[] = [];
    let id = 1;

    for (const app of appsData.apps) {
      if (app.impressions > 0 && app.impressions < 1000) {
        result.push({
          id: `alert-${id++}`,
          title: `Low impression volume in ${app.ad_unit_name}`,
          timeString: "Detected from live data",
          metric: "Impressions",
          severity: "warning",
          value: app.impressions,
          icon: Eye,
        });
      }
      if (app.revenue_usd > 0 && app.revenue_usd < 0.5) {
        result.push({
          id: `alert-${id++}`,
          title: `Revenue below $0.50 in ${app.ad_unit_name}`,
          timeString: "Detected from live data",
          metric: "Revenue",
          severity: "critical",
          value: `$${app.revenue_usd.toFixed(4)}`,
          icon: DollarSign,
        });
      }
      if (app.fill_rate_pct > 0 && app.fill_rate_pct < 30) {
        result.push({
          id: `alert-${id++}`,
          title: `Very low fill rate (${app.fill_rate_pct.toFixed(1)}%) in ${app.ad_unit_name}`,
          timeString: "Detected from live data",
          metric: "Fill Rate",
          severity: "warning",
          value: `${app.fill_rate_pct.toFixed(1)}%`,
          icon: TrendingDown,
        });
      }
    }

    return result;
  }, [appsData]);

  const criticalCount = alerts.filter((a) => a.severity === "critical").length;
  const warningCount = alerts.filter((a) => a.severity === "warning").length;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight flex items-center gap-2">
          <Zap className="h-5 w-5 text-indigo-500" />
          Live Alerts
        </h2>
        <p className="text-muted-foreground">
          Real-time alerts generated from live GAM data • {displayRange}
        </p>
      </div>

      {isLoading && !appsData ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Array.from({ length: 4 }).map((_, i) => <KPISkeleton key={i} />)}
        </div>
      ) : alerts.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="py-16 text-center">
            <Bell className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-lg font-medium mb-2">All Clear</h3>
            <p className="text-sm text-muted-foreground">
              No alerts detected. All metrics are within healthy ranges.
            </p>
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="flex items-center gap-3">
            {criticalCount > 0 && (
              <Badge className="bg-rose-500/10 text-rose-600 border-rose-500/30 hover:bg-rose-500/20">
                {criticalCount} Critical
              </Badge>
            )}
            {warningCount > 0 && (
              <Badge className="bg-amber-500/10 text-amber-600 border-amber-500/30 hover:bg-amber-500/20">
                {warningCount} Warning
              </Badge>
            )}
          </div>

          <div className="space-y-3">
            {alerts.map((alert) => {
              const Icon = alert.icon;
              return (
                <Card
                  key={alert.id}
                  className={`border-l-4 ${
                    alert.severity === "critical"
                      ? "border-l-rose-500"
                      : "border-l-amber-500"
                  }`}
                >
                  <CardContent className="py-4">
                    <div className="flex items-start gap-3">
                      <div className={`p-2 rounded-lg ${
                        alert.severity === "critical"
                          ? "bg-rose-500/10"
                          : "bg-amber-500/10"
                      }`}>
                        <Icon className={`h-4 w-4 ${
                          alert.severity === "critical"
                            ? "text-rose-500"
                            : "text-amber-500"
                        }`} />
                      </div>
                      <div className="flex-1">
                        <p className="text-sm font-medium">{alert.title}</p>
                        <p className="text-xs text-muted-foreground mt-0.5">{alert.timeString}</p>
                      </div>
                      <Badge variant="outline" className="text-[10px]">
                        {alert.metric}
                      </Badge>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
