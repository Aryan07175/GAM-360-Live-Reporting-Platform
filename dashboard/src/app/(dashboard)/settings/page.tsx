"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Settings, Server, Zap, Mail, Trash2, Plus, CheckCircle2, AlertCircle } from "lucide-react";
import { useLiveReport } from "@/contexts/DateContext";
import { getRecipientsData, addRecipient, removeRecipient, updatePreferences } from "@/actions/recipients";

export default function SettingsPage() {
  const { lastFetchedAt, datePreset } = useLiveReport();
  
  const [recipients, setRecipients] = useState<any[]>([]);
  const [prefs, setPrefs] = useState({ daily_report: true, critical_alerts: true, warning_alerts: false });
  const [email, setEmail] = useState("");
  const [label, setLabel] = useState("");
  const [loading, setLoading] = useState(true);
  
  const [message, setMessage] = useState<{type: "success" | "error", text: string} | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    setLoading(true);
    try {
      const data = await getRecipientsData();
      setRecipients(data.recipients || []);
      if (data.preferences) setPrefs(data.preferences);
    } catch (err) {
      console.error(err);
    }
    setLoading(false);
  }

  function showMessage(type: "success" | "error", text: string) {
    setMessage({ type, text });
    setTimeout(() => setMessage(null), 4000);
  }

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!email) return;
    
    const res = await addRecipient(email, label);
    if (res.success) {
      showMessage("success", "Recipient added successfully.");
      setEmail("");
      setLabel("");
      loadData();
    } else {
      showMessage("error", res.error || "Failed to add recipient.");
    }
  }

  async function handleRemove(id: string) {
    const res = await removeRecipient(id);
    if (res.success) {
      showMessage("success", "Recipient removed.");
      loadData();
    } else {
      showMessage("error", res.error || "Failed to remove recipient.");
    }
  }

  async function handleToggle(key: string, value: boolean) {
    const newPrefs = { ...prefs, [key]: value };
    setPrefs(newPrefs);
    const res = await updatePreferences(newPrefs);
    if (res.success) {
      showMessage("success", "Preferences saved.");
    } else {
      showMessage("error", res.error || "Failed to save preferences.");
      setPrefs(prefs); // revert
    }
  }

  const ToggleSwitch = ({ checked, onChange, label, desc }: any) => (
    <div className="flex items-center justify-between">
      <div className="space-y-0.5">
        <p className="text-sm font-medium">{label}</p>
        <p className="text-xs text-muted-foreground">{desc}</p>
      </div>
      <button
        type="button"
        onClick={() => onChange(!checked)}
        className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer items-center justify-center rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background ${
          checked ? "bg-indigo-600" : "bg-zinc-700"
        }`}
      >
        <span
          className={`pointer-events-none block h-4 w-4 rounded-full bg-white shadow-lg ring-0 transition-transform ${
            checked ? "translate-x-4" : "translate-x-0"
          }`}
        />
      </button>
    </div>
  );

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

      {/* Email Notifications */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Mail className="h-5 w-5 text-indigo-500" />
            Email Notifications
          </CardTitle>
          <CardDescription>Manage Gmail recipients and alert triggers</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          
          {/* Notification Message (Toast fallback) */}
          {message && (
            <div className={`p-3 rounded-md flex items-center gap-2 text-sm ${
              message.type === 'success' 
                ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20' 
                : 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20'
            }`}>
              {message.type === 'success' ? <CheckCircle2 className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
              {message.text}
            </div>
          )}

          {/* Add Recipient */}
          <form onSubmit={handleAdd} className="flex gap-2 items-end">
            <div className="space-y-1 flex-1">
              <label className="text-xs text-muted-foreground">Gmail Address</label>
              <input 
                type="email" 
                required 
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="user@gmail.com"
                className="w-full flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              />
            </div>
            <div className="space-y-1 flex-1">
              <label className="text-xs text-muted-foreground">Label (Optional)</label>
              <input 
                type="text"
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                placeholder="e.g. Manager"
                className="w-full flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              />
            </div>
            <button 
              type="submit"
              className="inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 bg-indigo-600 text-white shadow hover:bg-indigo-600/90 h-9 px-4 py-2"
            >
              <Plus className="h-4 w-4 mr-2" />
              Add
            </button>
          </form>

          {/* Recipients List */}
          <div className="space-y-2">
            <label className="text-xs text-muted-foreground">Current Recipients</label>
            {loading ? (
              <div className="text-sm text-muted-foreground py-2">Loading recipients...</div>
            ) : recipients.length === 0 ? (
              <div className="text-sm text-muted-foreground py-4 text-center rounded-md border border-dashed">
                No email recipients added — add one above to start receiving alerts and daily reports.
              </div>
            ) : (
              <div className="grid gap-2">
                {recipients.map((rec) => (
                  <div key={rec.id} className="flex items-center justify-between rounded-md border px-4 py-2 bg-muted/40">
                    <div className="flex items-center gap-3">
                      <Mail className="h-4 w-4 text-muted-foreground" />
                      <div>
                        <p className="text-sm font-medium">{rec.email}</p>
                        {rec.label && <p className="text-xs text-muted-foreground">{rec.label}</p>}
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleRemove(rec.id)}
                      className="inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors hover:bg-muted hover:text-rose-500 h-8 w-8"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Toggles */}
          <div className="space-y-4 pt-4 border-t">
            <ToggleSwitch 
              label="Daily report emails" 
              desc="Receive a full executive HTML report every day."
              checked={prefs.daily_report}
              onChange={(val: boolean) => handleToggle('daily_report', val)}
            />
            <ToggleSwitch 
              label="Critical alert emails" 
              desc="Receive instant emails for critical alerts (e.g. zero revenue)."
              checked={prefs.critical_alerts}
              onChange={(val: boolean) => handleToggle('critical_alerts', val)}
            />
            <ToggleSwitch 
              label="Warning alert emails" 
              desc="Receive instant emails for warning alerts (e.g. fill rate drops)."
              checked={prefs.warning_alerts}
              onChange={(val: boolean) => handleToggle('warning_alerts', val)}
            />
          </div>

        </CardContent>
      </Card>
    </div>
  );
}
