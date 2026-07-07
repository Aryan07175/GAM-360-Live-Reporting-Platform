"use client";

import { BISummaryKPI } from "@/types";
import { Card, CardContent } from "@/components/ui/card";
import { ArrowUpRight, ArrowDownRight, Minus } from "lucide-react";

const AXIS_TICK = { fill: "#E5E7EB", fontSize: 12 };

interface Props {
  kpi: BISummaryKPI;
}

export function ReportKPICard({ kpi }: Props) {
  const isUp = kpi.direction === "up";
  const isDown = kpi.direction === "down";

  // Mini sparkline via SVG polyline
  const sparklineWidth = 80;
  const sparklineHeight = 24;
  let sparklinePath = "";
  if (kpi.sparkline.length > 1) {
    const max = Math.max(...kpi.sparkline);
    const min = Math.min(...kpi.sparkline);
    const range = max - min || 1;
    const points = kpi.sparkline.map((v, i) => {
      const x = (i / (kpi.sparkline.length - 1)) * sparklineWidth;
      const y = sparklineHeight - ((v - min) / range) * sparklineHeight;
      return `${x},${y}`;
    });
    sparklinePath = points.join(" ");
  }

  return (
    <Card className="group hover:border-indigo-500/30 transition-all duration-300 hover:shadow-lg hover:shadow-indigo-500/5">
      <CardContent className="pt-5 pb-4 px-5">
        <div className="flex items-start justify-between">
          <div className="space-y-1 flex-1">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              {kpi.label}
            </p>
            <p className="text-2xl font-bold tracking-tight text-foreground">
              {kpi.formatted}
            </p>
            <div className="flex items-center gap-1.5">
              {isUp && (
                <>
                  <ArrowUpRight className="h-3.5 w-3.5 text-emerald-500" />
                  <span className="text-xs font-semibold text-emerald-500">
                    +{Math.abs(kpi.changePct).toFixed(1)}%
                  </span>
                </>
              )}
              {isDown && (
                <>
                  <ArrowDownRight className="h-3.5 w-3.5 text-rose-500" />
                  <span className="text-xs font-semibold text-rose-500">
                    {kpi.changePct.toFixed(1)}%
                  </span>
                </>
              )}
              {!isUp && !isDown && (
                <>
                  <Minus className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="text-xs font-semibold text-muted-foreground">
                    0%
                  </span>
                </>
              )}
              <span className="text-[10px] text-muted-foreground">vs prev period</span>
            </div>
          </div>

          {/* Sparkline */}
          {sparklinePath && (
            <svg
              width={sparklineWidth}
              height={sparklineHeight}
              className="ml-3 mt-1 opacity-60 group-hover:opacity-100 transition-opacity"
            >
              <polyline
                points={sparklinePath}
                fill="none"
                stroke={isDown ? "#f43f5e" : "#10b981"}
                strokeWidth={1.5}
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
