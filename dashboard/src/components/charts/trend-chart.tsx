"use client";

import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  CartesianGrid,
} from "recharts";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";

interface TrendChartProps {
  title: string;
  description?: string;
  data: any[];
  dataKey: string;
  xAxisKey: string;
  color?: string;
  valuePrefix?: string;
  valueSuffix?: string;
}

// Slate-400 — readable on both dark and light card backgrounds
const TICK_COLOR = "#94a3b8";
const TICK_STYLE = { fill: TICK_COLOR, fontSize: 11, fontWeight: 500 };

// Shorten "2026-06-30" → "06/30" for compact X-axis labels
function formatDate(dateStr: string): string {
  if (!dateStr) return "";
  const parts = String(dateStr).split("-");
  if (parts.length === 3) return `${parts[1]}/${parts[2]}`;
  return dateStr;
}

export function TrendChart({
  title,
  description,
  data,
  dataKey,
  xAxisKey,
  color = "#4f46e5",
  valuePrefix = "",
  valueSuffix = "",
}: TrendChartProps) {
  return (
    <Card className="col-span-1">
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent>
        <div className="h-[300px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart
              data={data}
              margin={{ top: 10, right: 12, left: 8, bottom: 0 }}
            >
              <defs>
                <linearGradient id={`color-${dataKey}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor={color} stopOpacity={0.35} />
                  <stop offset="95%" stopColor={color} stopOpacity={0} />
                </linearGradient>
              </defs>

              {/* Subtle grid lines — visible but not distracting */}
              <CartesianGrid
                strokeDasharray="3 3"
                vertical={false}
                stroke="rgba(148,163,184,0.15)"
              />

              {/* X Axis — tick.fill controls label text color */}
              <XAxis
                dataKey={xAxisKey}
                tickLine={false}
                axisLine={false}
                dy={8}
                tick={TICK_STYLE}
                tickFormatter={formatDate}
                interval="preserveStartEnd"
              />

              {/* Y Axis — tick.fill controls label text color */}
              <YAxis
                tickLine={false}
                axisLine={false}
                tick={TICK_STYLE}
                width={62}
                dx={-4}
                tickFormatter={(value) =>
                  `${valuePrefix}${Number(value).toLocaleString()}${valueSuffix}`
                }
              />

              <Tooltip
                contentStyle={{
                  backgroundColor: "hsl(var(--popover))",
                  borderColor: "hsl(var(--border))",
                  borderRadius: "8px",
                  boxShadow: "0 8px 30px rgba(0,0,0,0.35)",
                  padding: "10px 14px",
                }}
                labelStyle={{ color: TICK_COLOR, fontSize: 12, marginBottom: 4 }}
                itemStyle={{ color: color, fontWeight: 600, fontSize: 13 }}
                labelFormatter={(label) => formatDate(label)}
                formatter={(value: any) => [
                  `${valuePrefix}${Number(value).toLocaleString(undefined, {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 6,
                  })}${valueSuffix}`,
                  title,
                ]}
              />

              <Area
                type="monotone"
                dataKey={dataKey}
                stroke={color}
                strokeWidth={2}
                fillOpacity={1}
                fill={`url(#color-${dataKey})`}
                dot={false}
                activeDot={{ r: 5, strokeWidth: 0, fill: color }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
