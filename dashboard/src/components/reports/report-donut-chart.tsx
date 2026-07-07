"use client";

import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

const COLORS = [
  "#818cf8", "#38bdf8", "#34d399", "#fbbf24", "#f87171",
  "#a78bfa", "#22d3ee", "#4ade80", "#fb923c", "#e879f9",
  "#67e8f9", "#fde68a", "#fca5a5", "#c4b5fd", "#86efac",
];

interface DataItem {
  name: string;
  value: number;
}

interface Props {
  title: string;
  description?: string;
  data: DataItem[];
  height?: number;
}

export function ReportDonutChart({ title, description, data, height = 350 }: Props) {
  const total = data.reduce((s, d) => s + d.value, 0);

  const renderLabel = ({ name, value, cx, cy, midAngle, innerRadius, outerRadius }: any) => {
    const RADIAN = Math.PI / 180;
    const radius = innerRadius + (outerRadius - innerRadius) * 1.2;
    const x = cx + radius * Math.cos(-midAngle * RADIAN);
    const y = cy + radius * Math.sin(-midAngle * RADIAN);
    const pct = total > 0 ? ((value / total) * 100).toFixed(1) : "0";
    if (Number(pct) < 3) return null; // hide tiny slices
    return (
      <text x={x} y={y} fill="#E5E7EB" textAnchor={x > cx ? "start" : "end"} dominantBaseline="central" fontSize={10}>
        {pct}%
      </text>
    );
  };

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent>
        <div style={{ width: "100%", height }}>
          <ResponsiveContainer>
            <PieChart>
              <Pie
                data={data}
                cx="50%"
                cy="50%"
                innerRadius={70}
                outerRadius={120}
                paddingAngle={2}
                dataKey="value"
                stroke="none"
                label={renderLabel}
              >
                {data.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{ backgroundColor: "#1F2937", borderColor: "#374151", borderRadius: 8, color: "#E5E7EB" }}
                formatter={(v: any, name: any) => {
                  const pct = total > 0 ? ((Number(v) / total) * 100).toFixed(1) : "0";
                  return [`$${Number(v).toFixed(4)} (${pct}%)`, String(name)];
                }}
              />
              <Legend
                wrapperStyle={{ color: "#E5E7EB", fontSize: 11 }}
                formatter={(value: string) => <span style={{ color: "#E5E7EB" }}>{value}</span>}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
