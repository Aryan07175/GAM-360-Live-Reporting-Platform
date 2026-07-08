"use client";

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Settings, Server, Zap } from "lucide-react";
import { useLiveReport } from "@/contexts/DateContext";

export default function SettingsPage() {
  const { lastFetchedAt, datePreset } = useLiveReport();

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight flex items-center gap-2">
          <Settings className="h-5 w-5 text-indigo-500" />
          Settings
        </h2>
        <p className="text-muted-foreground">
          Platform configuration and connection status.
        </p>
      </div>

      {/* GAM Connection */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Server className="h-5 w-5 text-indigo-500" />
            Google Ad Manager Connection
          </CardTitle>
          <CardDescription>Live connection to GAM SOAP API via MCP Server</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">Network Code</p>
              <p className="text-sm font-medium">22846411849</p>
            </div>
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">API Version</p>
              <p className="text-sm font-medium">v202602</p>
            </div>
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">MCP Server</p>
              <p className="text-sm font-medium">http://localhost:8000</p>
            </div>
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">Connection Status</p>
              <div className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-green-500" />
                <p className="text-sm font-medium text-green-600 dark:text-green-400">Connected</p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Platform Info */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Zap className="h-5 w-5 text-indigo-500" />
            Platform Information
          </CardTitle>
          <CardDescription>Live reporting platform configuration</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">Data Mode</p>
              <Badge className="bg-emerald-500/10 text-emerald-600 border-emerald-500/30">
                100% Live
              </Badge>
            </div>
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">Database</p>
              <Badge variant="outline">None — Zero Storage</Badge>
            </div>
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">Cache</p>
              <Badge variant="outline">Request Dedup Only (30s)</Badge>
            </div>
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">Last Fetch</p>
              <p className="text-sm font-medium">
                {lastFetchedAt
                  ? new Date(lastFetchedAt).toLocaleString()
                  : "No data fetched yet"}
              </p>
            </div>
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">Default Date Preset</p>
              <p className="text-sm font-medium capitalize">{datePreset}</p>
            </div>
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">Architecture</p>
              <p className="text-sm font-medium">Next.js → Server Actions → MCP → GAM SOAP</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
