"use client";

import { BIAnomaly } from "@/types";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { AlertTriangle, TrendingDown, TrendingUp } from "lucide-react";

interface Props {
  anomalies: BIAnomaly[];
}

export function ReportAnomalyCard({ anomalies }: Props) {
  if (anomalies.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-emerald-500" />
            Anomaly Detection
          </CardTitle>
          <CardDescription>No anomalies detected in the selected period.</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground text-center py-6">
            ✅ All metrics are within expected ranges.
          </p>
        </CardContent>
      </Card>
    );
  }

  const severityColor = (s: string) => {
    switch (s) {
      case "High": return "bg-rose-500/10 text-rose-500 border-rose-500/20";
      case "Medium": return "bg-amber-500/10 text-amber-500 border-amber-500/20";
      default: return "bg-sky-500/10 text-sky-500 border-sky-500/20";
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base flex items-center gap-2">
          <AlertTriangle className="h-5 w-5 text-amber-500" />
          Anomaly Detection
        </CardTitle>
        <CardDescription>{anomalies.length} anomalies detected</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {anomalies.map((a) => (
            <div
              key={a.id}
              className="p-3 rounded-lg border bg-muted/30 flex items-start gap-3 hover:bg-muted/50 transition-colors"
            >
              {a.changePct < 0 ? (
                <TrendingDown className="h-5 w-5 text-rose-500 mt-0.5 shrink-0" />
              ) : (
                <TrendingUp className="h-5 w-5 text-amber-500 mt-0.5 shrink-0" />
              )}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-sm font-medium text-foreground">{a.metric}</span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded border font-medium ${severityColor(a.severity)}`}>
                    {a.severity}
                  </span>
                  <span className={`text-xs font-semibold ${a.changePct < 0 ? "text-rose-500" : "text-amber-500"}`}>
                    {a.changePct > 0 ? "+" : ""}{a.changePct.toFixed(1)}%
                  </span>
                </div>
                <p className="text-xs text-muted-foreground leading-relaxed">{a.description}</p>
                <p className="text-[10px] text-muted-foreground mt-1">
                  {a.ad_unit_name}
                </p>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
