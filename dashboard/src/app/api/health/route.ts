/**
 * Next.js API Proxy — /api/health
 *
 * Proxies the health check to the Render backend server-side.
 * This avoids browser CORS issues when the frontend checks if the
 * backend is alive. The browser calls /api/health (same origin),
 * and this route forwards it to the Render backend.
 *
 * Response mirrors the backend /health response.
 */

import { NextResponse } from "next/server";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_MCP_SERVER_URL ||
  process.env.MCP_SERVER_URL ||
  "https://gam-360-live-reporting-platform.onrender.com";

export async function GET() {
  const healthUrl = `${BACKEND_URL}/health`;
  console.log(`[API Proxy] Forwarding health check → ${healthUrl}`);

  try {
    const res = await fetch(healthUrl, {
      method: "GET",
      cache: "no-store",
      signal: AbortSignal.timeout(60_000), // 60s — covers full Render cold-start time
      headers: {
        "User-Agent": "GAM360-NextJS-Proxy/1.0",
      },
    });

    console.log(`[API Proxy] Backend /health responded: ${res.status}`);

    const body = await res.json().catch(() => ({ status: "error", error: "Non-JSON response" }));

    return NextResponse.json(body, { status: res.status });
  } catch (err: any) {
    const errName: string = err?.name || "UnknownError";
    const errMsg: string = err?.message || "Unknown error";

    console.error(`[API Proxy] Health check failed: ${errName} — ${errMsg}`);

    if (errName === "TimeoutError") {
      return NextResponse.json(
        {
          status: "error",
          error: "Backend health check timed out (20s). Service may be cold-starting.",
          error_type: "timeout",
        },
        { status: 504 }
      );
    }

    return NextResponse.json(
      {
        status: "error",
        error: `Cannot reach backend at ${BACKEND_URL}: ${errMsg}`,
        error_type: "network",
      },
      { status: 502 }
    );
  }
}
