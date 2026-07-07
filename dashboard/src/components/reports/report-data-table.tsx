"use client";

import { useState, useMemo } from "react";
import { BIAppRow } from "@/types";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ArrowUpDown, Search, ChevronLeft, ChevronRight } from "lucide-react";

interface Props {
  data: BIAppRow[];
  title?: string;
}

type SortKey = keyof BIAppRow;
type SortDir = "asc" | "desc";

const PAGE_SIZE = 15;

export function ReportDataTable({ data, title = "App Performance Scorecard" }: Props) {
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("rank");
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [page, setPage] = useState(0);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
    setPage(0);
  };

  const filtered = useMemo(() => {
    let items = [...data];
    if (search) {
      const q = search.toLowerCase();
      items = items.filter((r) => r.ad_unit_name.toLowerCase().includes(q));
    }
    items.sort((a, b) => {
      const aVal = a[sortKey];
      const bVal = b[sortKey];
      if (typeof aVal === "number" && typeof bVal === "number") {
        return sortDir === "asc" ? aVal - bVal : bVal - aVal;
      }
      return sortDir === "asc"
        ? String(aVal).localeCompare(String(bVal))
        : String(bVal).localeCompare(String(aVal));
    });
    return items;
  }, [data, search, sortKey, sortDir]);

  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);
  const pageData = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  const SortHeader = ({ label, field }: { label: string; field: SortKey }) => (
    <Button
      variant="ghost"
      size="sm"
      className="font-semibold text-xs px-1 -ml-1"
      onClick={() => handleSort(field)}
    >
      {label}
      <ArrowUpDown className="ml-1 h-3 w-3" />
    </Button>
  );

  const getStatus = (row: BIAppRow) => {
    if (row.fill_rate_pct > 80 && row.ecpm_usd > 0.003) return { label: "Healthy", class: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20" };
    if (row.fill_rate_pct > 50) return { label: "Fair", class: "bg-amber-500/10 text-amber-500 border-amber-500/20" };
    return { label: "Low", class: "bg-rose-500/10 text-rose-500 border-rose-500/20" };
  };

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-base">{title}</CardTitle>
            <CardDescription>{filtered.length} applications</CardDescription>
          </div>
          <div className="relative w-56">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              type="search"
              placeholder="Search apps..."
              className="pl-8 h-9 text-sm"
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(0); }}
            />
          </div>
        </div>
      </CardHeader>
      <CardContent className="px-0">
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-12 pl-4"><SortHeader label="#" field="rank" /></TableHead>
                <TableHead><SortHeader label="Application" field="ad_unit_name" /></TableHead>
                <TableHead className="text-right"><SortHeader label="Revenue" field="revenue_usd" /></TableHead>
                <TableHead className="text-right"><SortHeader label="Impressions" field="impressions" /></TableHead>
                <TableHead className="text-right"><SortHeader label="Clicks" field="clicks" /></TableHead>
                <TableHead className="text-right"><SortHeader label="CTR" field="ctr_pct" /></TableHead>
                <TableHead className="text-right"><SortHeader label="eCPM" field="ecpm_usd" /></TableHead>
                <TableHead className="text-right"><SortHeader label="Fill Rate" field="fill_rate_pct" /></TableHead>
                <TableHead className="text-right"><SortHeader label="Ad Req" field="ad_requests" /></TableHead>
                <TableHead className="text-right pr-4">Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {pageData.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={10} className="h-24 text-center text-muted-foreground">
                    {search ? `No apps match "${search}"` : "No data available."}
                  </TableCell>
                </TableRow>
              ) : (
                pageData.map((row) => {
                  const status = getStatus(row);
                  return (
                    <TableRow key={row.ad_unit_id} className="group">
                      <TableCell className="font-medium text-muted-foreground pl-4">{row.rank}</TableCell>
                      <TableCell className="font-medium max-w-[200px] truncate">{row.ad_unit_name}</TableCell>
                      <TableCell className="text-right text-emerald-500 font-semibold">${row.revenue_usd.toFixed(6)}</TableCell>
                      <TableCell className="text-right">{row.impressions.toLocaleString()}</TableCell>
                      <TableCell className="text-right">{row.clicks.toLocaleString()}</TableCell>
                      <TableCell className="text-right">{row.ctr_pct.toFixed(2)}%</TableCell>
                      <TableCell className="text-right">${row.ecpm_usd.toFixed(6)}</TableCell>
                      <TableCell className="text-right">{row.fill_rate_pct.toFixed(1)}%</TableCell>
                      <TableCell className="text-right">{row.ad_requests.toLocaleString()}</TableCell>
                      <TableCell className="text-right pr-4">
                        <span className={`text-[10px] font-medium px-2 py-0.5 rounded border ${status.class}`}>
                          {status.label}
                        </span>
                      </TableCell>
                    </TableRow>
                  );
                })
              )}
            </TableBody>
          </Table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-4 pt-4">
            <p className="text-xs text-muted-foreground">
              Page {page + 1} of {totalPages}
            </p>
            <div className="flex items-center gap-1">
              <Button variant="outline" size="icon" className="h-7 w-7" disabled={page === 0} onClick={() => setPage(page - 1)}>
                <ChevronLeft className="h-3.5 w-3.5" />
              </Button>
              <Button variant="outline" size="icon" className="h-7 w-7" disabled={page >= totalPages - 1} onClick={() => setPage(page + 1)}>
                <ChevronRight className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
