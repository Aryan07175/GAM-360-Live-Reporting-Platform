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

// ── Shared axis styles for dark theme visibility ──────────────────────────────
const AXIS_TICK = { fill: "#E5E7EB", fontSize: 12 };          // light gray labels
const AXIS_LINE = { stroke: "#6B7280" };                       // medium gray axis line
const TICK_LINE = { stroke: "#6B7280" };                       // medium gray tick marks
const GRID_STROKE = "#374151";                                 // dark gray grid lines
const GRID_DASH = "4 4";

// Shorten "2026-06-30" → "06/30"
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
  color = "#818cf8",
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
              margin={{ top: 10, right: 12, left: 12, bottom: 0 }}
            >
              <defs>
                <linearGradient id={`color-${dataKey}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor={color} stopOpacity={0.55} />
                  <stop offset="95%" stopColor={color} stopOpacity={0.02} />
                </linearGradient>
              </defs>

              {/* Grid: dark gray dashed lines, both directions */}
              <CartesianGrid
                stroke={GRID_STROKE}
                strokeDasharray={GRID_DASH}
                vertical={true}
              />

              {/* X Axis: light gray date labels + visible axis/tick lines */}
              <XAxis
                dataKey={xAxisKey}
                tick={AXIS_TICK}
                axisLine={AXIS_LINE}
                tickLine={TICK_LINE}
                tickFormatter={formatDate}
                interval="preserveStartEnd"
                dy={4}
              />

              {/* Y Axis: light gray value labels + visible axis/tick lines */}
              <YAxis
                tick={AXIS_TICK}
                axisLine={AXIS_LINE}
                tickLine={TICK_LINE}
                width={68}
                tickFormatter={(value) =>
                  `${valuePrefix}${Number(value).toLocaleString()}${valueSuffix}`
                }
              />

              <Tooltip
                contentStyle={{
                  backgroundColor: "#1F2937",
                  borderColor: "#374151",
                  borderRadius: "8px",
                  boxShadow: "0 8px 30px rgba(0,0,0,0.5)",
                  padding: "10px 14px",
                  color: "#E5E7EB",
                }}
                labelStyle={{ color: "#9CA3AF", fontSize: 12, marginBottom: 4 }}
                itemStyle={{ color: color, fontWeight: 700, fontSize: 13 }}
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
                strokeWidth={2.5}
                fillOpacity={1}
                fill={`url(#color-${dataKey})`}
                dot={{ r: 2.5, fill: color, strokeWidth: 0, fillOpacity: 0.85 }}
                activeDot={{
                  r: 6,
                  strokeWidth: 2,
                  stroke: color,
                  fill: "#111827",
                  strokeOpacity: 0.9,
                }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
