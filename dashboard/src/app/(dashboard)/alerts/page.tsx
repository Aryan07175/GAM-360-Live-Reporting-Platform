"use client";

import { useEffect, useState } from "react";
import { getSystemAlerts, getLatestReportDate } from "@/services/api";
import { SystemAlert } from "@/types";
import { Loader2, Bell, AlertTriangle, AlertCircle, Info, Settings2 } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<SystemAlert[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      const latestDate = await getLatestReportDate();
      const dateToQuery = latestDate || new Date().toISOString().split("T")[0];
      const data = await getSystemAlerts(dateToQuery);
      setAlerts(data);
      setLoading(false);
    }
    load();
  }, []);

  const getAlertIcon = (severity: string) => {
    switch (severity) {
      case "critical":
        return (
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-red-500/10 dark:bg-red-500/20">
            <AlertTriangle className="h-5 w-5 text-red-600 dark:text-red-400" />
          </div>
        );
      case "warning":
        return (
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-orange-500/10 dark:bg-orange-500/20">
            <AlertCircle className="h-5 w-5 text-orange-600 dark:text-orange-400" />
          </div>
        );
      case "info":
        return (
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-blue-500/10 dark:bg-blue-500/20">
            <Info className="h-5 w-5 text-blue-600 dark:text-blue-400" />
          </div>
        );
      default:
        return (
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-gray-500/10 dark:bg-gray-500/20">
            <Bell className="h-5 w-5 text-gray-600 dark:text-gray-400" />
          </div>
        );
    }
  };

  return (
    <div className="space-y-8 pb-10">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">System Alerts</h2>
          <p className="text-muted-foreground mt-1">
            AI-detected anomalies and critical system warnings.
          </p>
        </div>
        <div className="flex items-center text-sm font-medium text-emerald-600 dark:text-emerald-500 bg-emerald-50 dark:bg-emerald-500/10 px-3 py-1.5 rounded-full border border-emerald-200 dark:border-emerald-900/50">
          <span className="relative flex h-2 w-2 mr-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
          </span>
          Live from local server
        </div>
      </div>

      <div className="rounded-xl border bg-card/50 shadow-sm backdrop-blur-sm overflow-hidden">
        <div className="flex items-center justify-between border-b px-6 py-4 bg-muted/30">
          <div className="flex items-center space-x-2">
            <Bell className="h-5 w-5 text-indigo-500" />
            <h3 className="text-lg font-semibold">Active Alerts ({alerts.length})</h3>
          </div>
          <Button variant="ghost" size="icon" className="h-8 w-8 rounded-full hover:bg-muted">
            <Settings2 className="h-4 w-4" />
          </Button>
        </div>
        
        <div className="px-6 py-2 bg-muted/10">
          <p className="text-sm text-muted-foreground">Items requiring immediate attention</p>
        </div>

        <div className="divide-y divide-border/50">
          {loading ? (
            <div className="flex h-40 items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : alerts.length === 0 ? (
            <div className="flex h-40 items-center justify-center flex-col text-muted-foreground">
              <Bell className="h-10 w-10 mb-4 opacity-20" />
              <p>No active alerts at this time.</p>
            </div>
          ) : (
            alerts.map((alert) => (
              <div 
                key={alert.id} 
                className="group flex flex-col sm:flex-row sm:items-center justify-between p-6 transition-colors hover:bg-muted/50"
              >
                <div className="flex items-start space-x-4">
                  {getAlertIcon(alert.severity)}
                  <div>
                    <h4 className="text-base font-semibold leading-none mb-2">{alert.title}</h4>
                    <p className="text-sm text-muted-foreground flex items-center">
                      {alert.timeString}
                      <span className="mx-2 opacity-50">•</span>
                      Metric: <span className="text-foreground ml-1 font-medium">{alert.metric}</span>
                    </p>
                  </div>
                </div>
                <div className="mt-4 sm:mt-0 flex items-center space-x-3 sm:ml-4 opacity-100 sm:opacity-0 sm:group-hover:opacity-100 transition-opacity">
                  <Button variant="outline" size="sm" className="h-9 px-4">
                    Dismiss
                  </Button>
                  <Button size="sm" className="h-9 px-4 bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm">
                    Investigate
                  </Button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
