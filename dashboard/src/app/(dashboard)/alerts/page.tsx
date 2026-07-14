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
      if (app.ad_requests > 500 && app.impressions === 0) {
        result.push({
          id: `alert-${id++}`,
          title: `Zero Fill Rate in ${app.ad_unit_name}`,
          timeString: "Detected from live data",
          metric: "Fill Rate",
          severity: "critical",
          value: "0%",
          icon: AlertTriangle,
        });
      } else if (app.ad_requests > 1000 && app.fill_rate_pct > 0 && app.fill_rate_pct < 30) {
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

      if (app.impressions > 1000 && app.ctr_pct > 15) {
        result.push({
          id: `alert-${id++}`,
          title: `Suspiciously high CTR (${app.ctr_pct.toFixed(1)}%) in ${app.ad_unit_name}`,
          timeString: "Detected from live data",
          metric: "CTR",
          severity: "warning",
          value: `${app.ctr_pct.toFixed(1)}%`,
          icon: Eye,
        });
      }

      if (app.impressions > 5000 && app.ecpm_usd > 0 && app.ecpm_usd < 0.10) {
        result.push({
          id: `alert-${id++}`,
          title: `Extremely low eCPM ($${app.ecpm_usd.toFixed(2)}) in ${app.ad_unit_name}`,
          timeString: "Detected from live data",
          metric: "eCPM",
          severity: "warning",
          value: `$${app.ecpm_usd.toFixed(2)}`,
          icon: DollarSign,
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
