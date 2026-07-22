"use client";

import { AlertTriangle, DollarSign, Activity, TrendingDown } from "lucide-react";
import type { AlertSummary } from "@/lib/alerts/alert-types";

interface AlertSummaryBarProps {
  summary: AlertSummary;
}

export function AlertSummaryBar({ summary }: AlertSummaryBarProps) {
  const performanceCount =
    (summary.byCategory.ctr ?? 0) +
    (summary.byCategory.fill_rate ?? 0) +
    (summary.byCategory.ecpm ?? 0) +
    (summary.byCategory.impressions ?? 0);

  const cards = [
    {
      label: "Critical",
      count: summary.critical,
      icon: AlertTriangle,
      color: "text-rose-500",
      bg: "bg-rose-500/10",
      border: "border-rose-500/20",
      valueColor: "text-rose-600",
    },
    {
      label: "High",
      count: summary.high,
      icon: TrendingDown,
      color: "text-orange-500",
      bg: "bg-orange-500/10",
      border: "border-orange-500/20",
      valueColor: "text-orange-600",
    },
    {
      label: "Revenue",
      count: summary.byCategory.revenue ?? 0,
      icon: DollarSign,
      color: "text-amber-500",
      bg: "bg-amber-500/10",
      border: "border-amber-500/20",
      valueColor: "text-amber-600",
    },
    {
      label: "Performance",
      count: performanceCount,
      icon: Activity,
      color: "text-blue-500",
      bg: "bg-blue-500/10",
      border: "border-blue-500/20",
      valueColor: "text-blue-600",
    },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
      {cards.map((card) => {
        const Icon = card.icon;
        return (
          <div
            key={card.label}
            className={`rounded-xl border ${card.border} ${card.bg} p-4 flex items-center gap-3`}
          >
            <div className={`rounded-lg p-2 ${card.bg}`}>
              <Icon className={`h-5 w-5 ${card.color}`} />
            </div>
            <div>
              <p className="text-xs text-muted-foreground font-medium">{card.label} Alerts</p>
              <p className={`text-2xl font-bold ${card.valueColor}`}>{card.count}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
