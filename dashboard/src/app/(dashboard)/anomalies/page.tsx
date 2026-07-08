"use client";

import { useEffect } from "react";
import { useLiveReport } from "@/contexts/DateContext";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { AlertTriangle, TrendingDown, TrendingUp, Zap } from "lucide-react";
import { format, parseISO } from "date-fns";
import { KPISkeleton } from "@/components/live/section-skeleton";

export default function AnomaliesPage() {
  const { startDate, endDate, anomalyData, isLoading, generateReport } = useLiveReport();

  useEffect(() => {
    if (!anomalyData) generateReport();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [startDate, endDate]);

  const anomalies = anomalyData?.anomalies || [];

  const displayRange =
    startDate === endDate
      ? format(parseISO(startDate), "MMM dd, yyyy")
      : `${format(parseISO(startDate), "MMM dd")} → ${format(parseISO(endDate), "MMM dd, yyyy")}`;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight flex items-center gap-2">
          <Zap className="h-5 w-5 text-indigo-500" />
          Anomaly Detection
        </h2>
        <p className="text-muted-foreground">
          Live comparison of current vs previous period • {displayRange}
        </p>
      </div>

      {isLoading && !anomalyData ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Array.from({ length: 4 }).map((_, i) => <KPISkeleton key={i} />)}
        </div>
      ) : anomalies.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="py-16 text-center">
            <AlertTriangle className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-lg font-medium mb-2">No Anomalies Detected</h3>
            <p className="text-sm text-muted-foreground">
              All metrics are within normal ranges for this period.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="border-amber-500/30 text-amber-600">
              {anomalies.length} anomalies detected
            </Badge>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {anomalies.map((anomaly: any) => (
              <Card
                key={anomaly.id}
                className={`border-l-4 ${
                  anomaly.severity === "High"
                    ? "border-l-rose-500"
                    : anomaly.severity === "Medium"
                    ? "border-l-amber-500"
                    : "border-l-sky-500"
                }`}
              >
                <CardContent className="pt-4 pb-3">
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center gap-2">
                      {anomaly.changePct < 0 ? (
                        <TrendingDown className="h-4 w-4 text-rose-500" />
                      ) : (
                        <TrendingUp className="h-4 w-4 text-emerald-500" />
                      )}
                      <span className="text-sm font-semibold truncate max-w-[200px]">
                        {anomaly.ad_unit_name}
                      </span>
                    </div>
                    <Badge
                      variant="outline"
                      className={`text-[10px] ${
                        anomaly.severity === "High"
                          ? "border-rose-500/30 text-rose-500"
                          : anomaly.severity === "Medium"
                          ? "border-amber-500/30 text-amber-500"
                          : "border-sky-500/30 text-sky-500"
                      }`}
                    >
                      {anomaly.severity}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground mb-2">{anomaly.description}</p>
                  <div className="flex items-center gap-4 text-xs">
                    <span className="text-muted-foreground">
                      {anomaly.metric}: {anomaly.changePct > 0 ? "+" : ""}{anomaly.changePct.toFixed(1)}%
                    </span>
                    <span className="text-muted-foreground">
                      ${typeof anomaly.previousValue === 'number' ? anomaly.previousValue.toFixed(4) : anomaly.previousValue} → ${typeof anomaly.currentValue === 'number' ? anomaly.currentValue.toFixed(4) : anomaly.currentValue}
                    </span>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
