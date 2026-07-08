"use client";

import { motion } from "framer-motion";
import { Loader2 } from "lucide-react";
import type { ReportProgress } from "@/types";

interface Props {
  progress: ReportProgress;
  isLoading: boolean;
}

export function LiveProgressBar({ progress, isLoading }: Props) {
  if (!isLoading && progress.completed === 0) return null;

  const pct =
    progress.total > 0
      ? Math.round((progress.completed / progress.total) * 100)
      : 0;

  return (
    <div className="rounded-xl border bg-card p-5 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          {isLoading && (
            <Loader2 className="h-5 w-5 animate-spin text-indigo-500" />
          )}
          <div>
            <p className="text-sm font-semibold">
              {isLoading
                ? "Generating Live Report from Google Ad Manager..."
                : "Report Generated"}
            </p>
            <p className="text-xs text-muted-foreground">
              {isLoading
                ? `${progress.completed} of ${progress.total} sections complete`
                : `All ${progress.total} sections loaded`}
            </p>
          </div>
        </div>
        <span className="text-2xl font-bold text-indigo-500">{pct}%</span>
      </div>

      {/* Progress Bar */}
      <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
        <motion.div
          className="h-full rounded-full bg-gradient-to-r from-indigo-500 via-violet-500 to-purple-500"
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.5, ease: "easeOut" }}
        />
      </div>

      {/* Section Status */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
        {progress.sections.map((section) => (
          <div
            key={section.name}
            className={`flex items-center gap-2 rounded-lg px-3 py-2 text-xs transition-all ${
              section.status === "done"
                ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                : section.status === "loading"
                ? "bg-indigo-500/10 text-indigo-600 dark:text-indigo-400"
                : section.status === "error"
                ? "bg-rose-500/10 text-rose-600 dark:text-rose-400"
                : "bg-muted/50 text-muted-foreground"
            }`}
          >
            {section.status === "done" && (
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
            )}
            {section.status === "loading" && (
              <Loader2 className="h-3 w-3 animate-spin" />
            )}
            {section.status === "error" && (
              <span className="h-1.5 w-1.5 rounded-full bg-rose-500" />
            )}
            {section.status === "pending" && (
              <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground/40" />
            )}
            <span className="font-medium truncate">{section.name}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
