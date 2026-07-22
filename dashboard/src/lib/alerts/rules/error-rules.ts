import type { Alert } from "../alert-types";
import { getRecommendations } from "../alert-recommendations";

/**
 * Error alert rules — surfaces backend API and authentication errors.
 * These come from the `error` string in the LiveReportContext.
 */
export function generateErrorAlerts(error: string | null): Alert[] {
  if (!error) return [];

  const now = new Date().toISOString();
  const errLower = error.toLowerCase();

  let title = "Backend API Error";
  let reason = error;
  let severity: "critical" | "high" = "high";

  if (errLower.includes("401") || errLower.includes("403") || errLower.includes("auth")) {
    title = "Authentication Failure";
    reason = "GAM API credentials are invalid or expired. Data cannot be fetched.";
    severity = "critical";
  } else if (errLower.includes("timeout") || errLower.includes("timed out")) {
    title = "API Request Timeout";
    reason = "The GAM API request timed out. The service may be slow or overloaded.";
    severity = "high";
  } else if (errLower.includes("rate limit") || errLower.includes("quota")) {
    title = "API Rate Limit Reached";
    reason = "Google Ad Manager API quota has been exceeded. Requests are being throttled.";
    severity = "high";
  } else if (errLower.includes("502") || errLower.includes("503") || errLower.includes("cold start")) {
    title = "Backend Service Unavailable";
    reason = "The backend service is starting up or temporarily unavailable.";
    severity = "high";
  } else if (errLower.includes("network") || errLower.includes("fetch")) {
    title = "Network Connectivity Error";
    reason = "Cannot reach the GAM 360 backend. Check your network connection.";
    severity = "high";
  } else if (errLower.includes("credentials") || errLower.includes("gam_")) {
    title = "Missing GAM Credentials";
    reason = "GAM service account credentials are not configured in the backend.";
    severity = "critical";
  }

  return [
    {
      id: `error-${now}`,
      title,
      appName: "System",
      category: "error",
      severity,
      metric: "API Health",
      currentValue: 0,
      currentFormatted: "Error",
      expectedValue: 1,
      expectedFormatted: "OK",
      changePct: -100,
      direction: "zero",
      reason,
      suggestedAction: "Check Render service logs and verify GAM credentials in environment variables.",
      aiRecommendations: getRecommendations("error", "general" as any),
      generatedAt: now,
    },
  ];
}
