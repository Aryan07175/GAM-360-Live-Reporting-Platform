"use client";

interface Props {
  isLoading: boolean;
  lastFetchedAt: string | null;
  error: string | null;
}

export function LiveStatusIndicator({ isLoading, lastFetchedAt, error }: Props) {
  const getTimeAgo = (isoString: string): string => {
    const diff = Math.floor((Date.now() - new Date(isoString).getTime()) / 1000);
    if (diff < 10) return "just now";
    if (diff < 60) return `${diff}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    return `${Math.floor(diff / 3600)}h ago`;
  };

  if (error) {
    return (
      <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-rose-500/10 border border-rose-500/20">
        <span className="relative flex h-2 w-2">
          <span className="h-2 w-2 rounded-full bg-rose-500" />
        </span>
        <span className="text-xs font-medium text-rose-600 dark:text-rose-400">
          Error
        </span>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-indigo-500/10 border border-indigo-500/20">
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-indigo-500" />
        </span>
        <span className="text-xs font-medium text-indigo-600 dark:text-indigo-400">
          Fetching Live Data...
        </span>
      </div>
    );
  }

  if (lastFetchedAt) {
    return (
      <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20">
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
        </span>
        <span className="text-xs font-medium text-emerald-600 dark:text-emerald-400">
          LIVE
        </span>
        <span className="text-[10px] text-muted-foreground">
          {getTimeAgo(lastFetchedAt)}
        </span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-muted/50 border">
      <span className="h-2 w-2 rounded-full bg-muted-foreground/40" />
      <span className="text-xs text-muted-foreground">Ready</span>
    </div>
  );
}
