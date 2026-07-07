"use client";

import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, Legend,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

const AXIS_TICK = { fill: "#E5E7EB", fontSize: 11 };
const AXIS_LINE = { stroke: "#6B7280" };
const TICK_LINE = { stroke: "#6B7280" };
const GRID = "#374151";

const COLORS = [
  "#818cf8", "#38bdf8", "#34d399", "#fbbf24", "#f87171",
  "#a78bfa", "#22d3ee", "#4ade80", "#fb923c", "#e879f9",
];

interface DataItem {
  name: string;
  value: number;
  [key: string]: any;
}

interface Props {
  title: string;
  description?: string;
  data: DataItem[];
  dataKey?: string;
  nameKey?: string;
  layout?: "horizontal" | "vertical";
  color?: string;
  highlightMax?: boolean;
  highlightMin?: boolean;
  valuePrefix?: string;
  valueSuffix?: string;
  height?: number;
  showLegend?: boolean;
}

export function ReportBarChart({
  title,
  description,
  data,
  dataKey = "value",
  nameKey = "name",
  layout = "vertical",
  color = "#818cf8",
  highlightMax = true,
  highlightMin = true,
  valuePrefix = "",
  valueSuffix = "",
  height = 400,
  showLegend = false,
}: Props) {
  const maxVal = Math.max(...data.map((d) => d[dataKey]));
  const minVal = Math.min(...data.map((d) => d[dataKey]));

  const fmt = (v: number) => `${valuePrefix}${v.toLocaleString(undefined, { maximumFractionDigits: 4 })}${valueSuffix}`;

  if (layout === "horizontal") {
    return (
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">{title}</CardTitle>
          {description && <CardDescription>{description}</CardDescription>}
        </CardHeader>
        <CardContent>
          <div style={{ width: "100%", height }}>
            <ResponsiveContainer>
              <BarChart data={data} layout="vertical" margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                <CartesianGrid stroke={GRID} strokeDasharray="4 4" horizontal={false} />
                <XAxis type="number" tick={AXIS_TICK} axisLine={AXIS_LINE} tickLine={TICK_LINE} tickFormatter={fmt} />
                <YAxis type="category" dataKey={nameKey} tick={AXIS_TICK} axisLine={AXIS_LINE} tickLine={TICK_LINE} width={160} fontSize={10} />
                <Tooltip
                  contentStyle={{ backgroundColor: "#1F2937", borderColor: "#374151", borderRadius: 8, color: "#E5E7EB" }}
                  formatter={(v: any) => [fmt(v), title]}
                  labelStyle={{ color: "#9CA3AF" }}
                />
                <Bar dataKey={dataKey} radius={[0, 4, 4, 0]}>
                  {data.map((entry, i) => {
                    let fill = color;
                    if (highlightMax && entry[dataKey] === maxVal) fill = "#10b981";
                    else if (highlightMin && entry[dataKey] === minVal) fill = "#f43f5e";
                    return <Cell key={i} fill={fill} />;
                  })}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent>
        <div style={{ width: "100%", height }}>
          <ResponsiveContainer>
            <BarChart data={data} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
              <CartesianGrid stroke={GRID} strokeDasharray="4 4" vertical={false} />
              <XAxis dataKey={nameKey} tick={AXIS_TICK} axisLine={AXIS_LINE} tickLine={TICK_LINE} interval={0} angle={-45} textAnchor="end" height={80} fontSize={9} />
              <YAxis tick={AXIS_TICK} axisLine={AXIS_LINE} tickLine={TICK_LINE} tickFormatter={fmt} />
              <Tooltip
                contentStyle={{ backgroundColor: "#1F2937", borderColor: "#374151", borderRadius: 8, color: "#E5E7EB" }}
                formatter={(v: any) => [fmt(v), title]}
                labelStyle={{ color: "#9CA3AF" }}
              />
              <Bar dataKey={dataKey} radius={[4, 4, 0, 0]}>
                {data.map((entry, i) => {
                  let fill = color;
                  if (highlightMax && entry[dataKey] === maxVal) fill = "#10b981";
                  else if (highlightMin && entry[dataKey] === minVal) fill = "#f43f5e";
                  return <Cell key={i} fill={fill} />;
                })}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
