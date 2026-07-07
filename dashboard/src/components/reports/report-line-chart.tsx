"use client";

import {
  Area, AreaChart, Line, LineChart, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Legend,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

const AXIS_TICK = { fill: "#E5E7EB", fontSize: 11 };
const AXIS_LINE = { stroke: "#6B7280" };
const TICK_LINE = { stroke: "#6B7280" };
const GRID = "#374151";

function formatDate(dateStr: string): string {
  if (!dateStr) return "";
  const parts = String(dateStr).split("-");
  if (parts.length === 3) return `${parts[1]}/${parts[2]}`;
  return dateStr;
}

interface Props {
  title: string;
  description?: string;
  data: any[];
  dataKey: string;
  xAxisKey?: string;
  color?: string;
  valuePrefix?: string;
  valueSuffix?: string;
  height?: number;
  type?: "area" | "line";
}

export function ReportLineChart({
  title,
  description,
  data,
  dataKey,
  xAxisKey = "report_date",
  color = "#818cf8",
  valuePrefix = "",
  valueSuffix = "",
  height = 280,
  type = "area",
}: Props) {
  const fmt = (v: number) => `${valuePrefix}${Number(v).toLocaleString(undefined, { maximumFractionDigits: 4 })}${valueSuffix}`;

  const ChartComponent = type === "area" ? AreaChart : LineChart;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">{title}</CardTitle>
        {description && <CardDescription className="text-xs">{description}</CardDescription>}
      </CardHeader>
      <CardContent>
        <div style={{ width: "100%", height }}>
          <ResponsiveContainer>
            <ChartComponent data={data} margin={{ top: 10, right: 12, left: 8, bottom: 0 }}>
              <defs>
                <linearGradient id={`grad-${dataKey}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={color} stopOpacity={0.4} />
                  <stop offset="95%" stopColor={color} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke={GRID} strokeDasharray="4 4" vertical={true} />
              <XAxis
                dataKey={xAxisKey}
                tick={AXIS_TICK}
                axisLine={AXIS_LINE}
                tickLine={TICK_LINE}
                tickFormatter={formatDate}
                interval="preserveStartEnd"
              />
              <YAxis
                tick={AXIS_TICK}
                axisLine={AXIS_LINE}
                tickLine={TICK_LINE}
                width={65}
                tickFormatter={fmt}
              />
              <Tooltip
                contentStyle={{ backgroundColor: "#1F2937", borderColor: "#374151", borderRadius: 8, color: "#E5E7EB" }}
                labelStyle={{ color: "#9CA3AF" }}
                labelFormatter={formatDate}
                formatter={(v: any) => [fmt(v), title]}
              />
              {type === "area" ? (
                <Area
                  type="monotone"
                  dataKey={dataKey}
                  stroke={color}
                  strokeWidth={2}
                  fillOpacity={1}
                  fill={`url(#grad-${dataKey})`}
                  dot={false}
                  activeDot={{ r: 5, strokeWidth: 2, stroke: color, fill: "#111827" }}
                />
              ) : (
                <Line
                  type="monotone"
                  dataKey={dataKey}
                  stroke={color}
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 5, strokeWidth: 2, stroke: color, fill: "#111827" }}
                />
              )}
            </ChartComponent>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
