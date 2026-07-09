/**
 * MCP Client — Live Data Gateway
 *
 * Calls the local Python MCP server for all GAM data.
 * Supports force_refresh, date ranges, abort controllers, and retry.
 * Never caches. Never stores. Always live.
 */

const MCP_BASE_URL = process.env.NEXT_PUBLIC_MCP_URL || "http://127.0.0.1:8000";

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
    // For local development, we call the Python Starlette API directly
    const endpoint = `${MCP_BASE_URL}/api/tool`;

    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, arguments: args }),
      signal,
      cache: "no-store", // Never cache
    });

    if (!response.ok) {
      throw new Error(`MCP Error: ${response.status} ${response.statusText}`);
    }

    const parsed = await response.json();

    if (parsed.status === "error") {
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
    console.error(`MCP tool ${name} failed:`, error);
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
