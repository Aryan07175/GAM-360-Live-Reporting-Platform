"use client";

import { BIInsight } from "@/types";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { BrainCircuit } from "lucide-react";

interface Props {
  insights: BIInsight[];
}

export function ReportInsights({ insights }: Props) {
  if (insights.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <BrainCircuit className="h-5 w-5 text-violet-500" />
            AI Insights & Recommendations
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground text-center py-6">
            Generate a report to see AI-powered insights.
          </p>
        </CardContent>
      </Card>
    );
  }

  const categoryColors: Record<string, string> = {
    revenue: "border-l-emerald-500",
    performance: "border-l-sky-500",
    anomaly: "border-l-rose-500",
    recommendation: "border-l-violet-500",
  };

  const categoryLabels: Record<string, string> = {
    revenue: "Revenue",
    performance: "Performance",
    anomaly: "Anomaly",
    recommendation: "Recommendation",
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base flex items-center gap-2">
          <BrainCircuit className="h-5 w-5 text-violet-500" />
          AI Insights & Recommendations
        </CardTitle>
        <CardDescription>{insights.length} insights generated from your data</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {insights.map((insight) => (
            <div
              key={insight.id}
              className={`p-4 rounded-lg border border-l-4 bg-muted/20 hover:bg-muted/40 transition-colors ${
                categoryColors[insight.category] || "border-l-slate-500"
              }`}
            >
              <div className="flex items-center gap-2 mb-1.5">
                <span className="text-lg">{insight.icon}</span>
                <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  {categoryLabels[insight.category] || insight.category}
                </span>
              </div>
              <h4 className="text-sm font-semibold text-foreground mb-1">{insight.title}</h4>
              <p className="text-xs text-muted-foreground leading-relaxed">{insight.description}</p>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
