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

// ── Color constants ────────────────────────────────────────────────────────────
const X_TICK_COLOR = "#94a3b8"; // slate-400  — date labels on X axis
const Y_TICK_COLOR = "#60a5fa"; // blue-400   — value labels on Y axis (bright blue)

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
  // ── Render functions (closures) — guaranteed to capture the right vars ──────
  // Recharts calls these as functions and passes x, y, payload automatically.

  const renderXTick = ({ x, y, payload }: any) => (
    <text
      x={x}
      y={y + 14}
      textAnchor="middle"
      fill={X_TICK_COLOR}
      fontSize={11}
      fontWeight={500}
      fontFamily="inherit"
    >
      {formatDate(String(payload?.value ?? ""))}
    </text>
  );

  const renderYTick = ({ x, y, payload }: any) => (
    <text
      x={x - 6}
      y={y + 4}
      textAnchor="end"
      fill={Y_TICK_COLOR}       // ← blue-400, always visible on dark bg
      fontSize={11}
      fontWeight={700}
      fontFamily="inherit"
    >
      {`${valuePrefix}${Number(payload?.value ?? 0).toLocaleString()}${valueSuffix}`}
    </text>
  );

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

              {/* Grid: blue-tinted dashed lines, both horizontal and vertical */}
              <CartesianGrid
                strokeDasharray="4 4"
                stroke="rgba(96, 165, 250, 0.18)"
                vertical={true}
              />

              {/* X Axis: date labels in slate-400 */}
              <XAxis
                dataKey={xAxisKey}
                tickLine={false}
                axisLine={false}
                interval="preserveStartEnd"
                tick={renderXTick}
              />

              {/* Y Axis: value labels in bright blue-400 via render function */}
              <YAxis
                tickLine={false}
                axisLine={false}
                width={68}
                tick={renderYTick}
              />

              <Tooltip
                contentStyle={{
                  backgroundColor: "hsl(var(--popover))",
                  borderColor: "hsl(var(--border))",
                  borderRadius: "8px",
                  boxShadow: "0 8px 30px rgba(0,0,0,0.4)",
                  padding: "10px 14px",
                }}
                labelStyle={{ color: X_TICK_COLOR, fontSize: 12, marginBottom: 4 }}
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
                  fill: "hsl(var(--background))",
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
