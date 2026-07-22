/**
 * MCP Client — Live Data Gateway
 *
 * Calls the Python MCP server (Render) for all GAM data.
 * Supports force_refresh, date ranges, abort controllers, and retry.
 * Never caches. Never stores. Always live.
 *
 * Priority order for backend URL:
 *   1. NEXT_PUBLIC_MCP_SERVER_URL  (Vercel env var, browser + server)
 *   2. MCP_SERVER_URL              (Vercel env var, server-only)
 *   3. Hardcoded Render URL        (fallback)
 */

const MCP_BASE_URL =
  process.env.NEXT_PUBLIC_MCP_SERVER_URL ||
  process.env.MCP_SERVER_URL ||
  "https://gam-360-live-reporting-platform.onrender.com";

// Log the resolved URL once at module load time (visible in Vercel function logs)
console.log(`[MCP Client] Backend URL resolved to: ${MCP_BASE_URL}`);

export interface McpToolArgs {
  startDate?: string;
  endDate?: string;
  date?: string;
  force_refresh?: boolean;
  limit?: number;
  threshold_pct?: number;
  [key: string]: unknown;
}

export async function callMcpTool(
  name: string,
  args: McpToolArgs = {},
  options?: { signal?: AbortSignal; timeout?: number }
): Promise<any> {
  const timeout = options?.timeout ?? 300_000; // 5 minutes default for live GAM requests

  const controller = new AbortController();
  const signal = options?.signal
    ? anySignal([options.signal, controller.signal])
    : controller.signal;

  // Timeout
  const timer = setTimeout(() => controller.abort(), timeout);

  try {
    // Call the Python Starlette API on the MCP server (Render in production)
    const endpoint = `${MCP_BASE_URL}/api/tool`;

    console.log(`[MCP] → POST ${endpoint} | tool: ${name}`);

    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, arguments: args }),
      signal,
      cache: "no-store", // Never cache
    });

    console.log(`[MCP] ← ${response.status} ${response.statusText} | tool: ${name}`);

    if (!response.ok) {
      let bodyText = "";
      try { bodyText = await response.text(); } catch {}
      console.error(`[MCP] Error body for ${name}:`, bodyText);
      throw new Error(`MCP Error: ${response.status} ${response.statusText}${bodyText ? ` — ${bodyText.slice(0, 200)}` : ""}`);
    }

    const parsed = await response.json();

    if (parsed.status === "error") {
      console.error(`[MCP] Tool ${name} returned error:`, parsed.error);
      throw new Error(parsed.error || "Unknown MCP error");
    }

    if (parsed.status === "timeout") {
      throw new Error(parsed.error || "GAM report generation timed out");
    }

    return parsed;
  } catch (error: any) {
    if (error.name === "AbortError") {
      throw new Error(`Request timed out after ${timeout / 1000}s`);
    }
    console.error(`[MCP] Tool ${name} failed:`, error.message || error);
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Combine multiple AbortSignals into one.
 */
function anySignal(signals: AbortSignal[]): AbortSignal {
  const controller = new AbortController();
  for (const signal of signals) {
    if (signal.aborted) {
      controller.abort(signal.reason);
      return controller.signal;
    }
    signal.addEventListener("abort", () => controller.abort(signal.reason), {
      once: true,
    });
  }
  return controller.signal;
}
