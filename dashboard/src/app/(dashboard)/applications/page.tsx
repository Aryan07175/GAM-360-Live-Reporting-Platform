"use client";

import { useEffect, useState } from "react";
import { useLiveReport } from "@/contexts/DateContext";
import type { BIAppRow } from "@/types";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Loader2, Search, ArrowUpDown, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";
import { format, parseISO } from "date-fns";
import { TableSkeleton } from "@/components/live/section-skeleton";

type SortConfig = {
  key: keyof BIAppRow;
  direction: "asc" | "desc";
} | null;

export default function ApplicationsPage() {
  const { startDate, endDate, appsData, isLoading, generateReport } = useLiveReport();
  const [search, setSearch] = useState("");
  const [sortConfig, setSortConfig] = useState<SortConfig>({ key: "revenue_usd", direction: "desc" });

  useEffect(() => {
    if (!appsData) generateReport();
  }, [appsData, generateReport]);

  const apps = appsData?.apps || [];

  const handleSort = (key: keyof BIAppRow) => {
    let direction: "asc" | "desc" = "desc";
    if (sortConfig && sortConfig.key === key && sortConfig.direction === "desc") {
      direction = "asc";
    }
    setSortConfig({ key, direction });
  };

  const filteredAndSortedApps = [...apps]
    .filter((app) => app.ad_unit_name.toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => {
      if (!sortConfig) return 0;
      const { key, direction } = sortConfig;
      if (a[key] < b[key]) return direction === "asc" ? -1 : 1;
      if (a[key] > b[key]) return direction === "asc" ? 1 : -1;
      return 0;
    });

  const displayRange =
    startDate === endDate
      ? format(parseISO(startDate), "MMM dd, yyyy")
      : `${format(parseISO(startDate), "MMM dd")} → ${format(parseISO(endDate), "MMM dd, yyyy")}`;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight flex items-center gap-2">
          <Zap className="h-5 w-5 text-indigo-500" />
          Applications Analytics
        </h2>
        <p className="text-muted-foreground">
          Live performance breakdown by application • {displayRange}
        </p>
      </div>

      {(isLoading && !appsData) ? (
        <TableSkeleton rows={10} />
      ) : (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>All Applications</CardTitle>
                <CardDescription>
                  Live data • {filteredAndSortedApps.length} app{filteredAndSortedApps.length !== 1 ? "s" : ""}
                </CardDescription>
              </div>
              <div className="relative w-64">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  type="search"
                  placeholder="Search apps..."
                  className="pl-8"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>
                      <Button variant="ghost" onClick={() => handleSort("ad_unit_name")} className="font-semibold">
                        App Name <ArrowUpDown className="ml-2 h-4 w-4" />
                      </Button>
                    </TableHead>
                    <TableHead className="text-right">
                      <Button variant="ghost" onClick={() => handleSort("revenue_usd")} className="font-semibold">
                        Revenue <ArrowUpDown className="ml-2 h-4 w-4" />
                      </Button>
                    </TableHead>
                    <TableHead className="text-right">
                      <Button variant="ghost" onClick={() => handleSort("impressions")} className="font-semibold">
                        Impressions <ArrowUpDown className="ml-2 h-4 w-4" />
                      </Button>
                    </TableHead>
                    <TableHead className="text-right">
                      <Button variant="ghost" onClick={() => handleSort("ecpm_usd")} className="font-semibold">
                        eCPM <ArrowUpDown className="ml-2 h-4 w-4" />
                      </Button>
                    </TableHead>
                    <TableHead className="text-right">
                      <Button variant="ghost" onClick={() => handleSort("fill_rate_pct")} className="font-semibold">
                        Fill Rate <ArrowUpDown className="ml-2 h-4 w-4" />
                      </Button>
                    </TableHead>
                    <TableHead className="text-right">
                      <Button variant="ghost" onClick={() => handleSort("ctr_pct")} className="font-semibold">
                        CTR <ArrowUpDown className="ml-2 h-4 w-4" />
                      </Button>
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredAndSortedApps.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={6} className="h-24 text-center text-muted-foreground">
                        {search ? `No apps match "${search}"` : "No data available."}
                      </TableCell>
                    </TableRow>
                  ) : (
                    filteredAndSortedApps.map((app) => (
                      <TableRow key={app.ad_unit_id}>
                        <TableCell className="font-medium px-4">{app.ad_unit_name}</TableCell>
                        <TableCell className="text-right px-4 text-emerald-600 dark:text-emerald-400 font-medium">
                          ${app.revenue_usd.toFixed(6)}
                        </TableCell>
                        <TableCell className="text-right px-4">{app.impressions.toLocaleString()}</TableCell>
                        <TableCell className="text-right px-4">${app.ecpm_usd.toFixed(6)}</TableCell>
                        <TableCell className="text-right px-4">{app.fill_rate_pct.toFixed(1)}%</TableCell>
                        <TableCell className="text-right px-4">{app.ctr_pct.toFixed(2)}%</TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
