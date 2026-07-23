"use client";

import { useEffect } from "react";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_MCP_SERVER_URL ||
  "https://gam-360-live-reporting-platform.onrender.com";

// Ping the backend every 9 minutes to prevent Render free-tier from sleeping.
// Render spins down after 15 minutes of inactivity. This keeps it alive.
const PING_INTERVAL_MS = 9 * 60 * 1000; // 9 minutes

export function BackendKeepAlive() {
  useEffect(() => {
    const ping = async () => {
      try {
        await fetch(`${BACKEND_URL}/health`, {
          method: "GET",
          cache: "no-store",
          signal: AbortSignal.timeout(10_000),
        });
      } catch {
        // Silently ignore — keep-alive pings are best-effort
      }
    };

    // Ping immediately on mount to wake up any sleeping backend
    ping();

    // Then ping every 9 minutes
    const interval = setInterval(ping, PING_INTERVAL_MS);
    return () => clearInterval(interval);
  }, []);

  return null; // No UI — this is a background component
}
