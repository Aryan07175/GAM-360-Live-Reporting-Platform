import { Metadata } from "next";
import { ApiEndpoint } from "@/components/ui/ApiEndpoint";

export const metadata: Metadata = {
  title: "API Documentation",
  description: "REST API endpoints for the GAM 360 Live Reporting Platform backend.",
};

export default function ApiPage() {
  return (
    <div>
      <h1>API Documentation</h1>
      <p>
        The Python backend provides several REST endpoints and Server-Sent Events (SSE) streams for the frontend to consume. 
        Because there is no database, all endpoints fetch data live from the Google Ad Manager SOAP API.
      </p>

      <h2>Authentication</h2>
      <p>
        Currently, the API endpoints do not require authentication for local development, but in production (e.g., Render), you should secure them using standard JWT or bearer token authentication in front of the Uvicorn server.
      </p>

      <h2>Endpoints</h2>

      <ApiEndpoint
        method="GET"
        path="/api/network/summary?date={dateRange}"
        description="Fetches a high-level summary of the entire network across Ad Server, AdSense, and Ad Exchange."
        response={`{
  "status": "success",
  "data": {
    "totalRevenue": 15420.50,
    "totalImpressions": 4500000,
    "overallEcpm": 3.42,
    "overallFillRate": 85.4
  }
}`}
      />

      <ApiEndpoint
        method="GET"
        path="/api/inventory/top?type={app|web}&date={dateRange}"
        description="Fetches the top performing inventory (apps or websites) ranked by revenue."
        response={`{
  "status": "success",
  "data": [
    {
      "name": "com.example.game",
      "revenue": 5000.00,
      "impressions": 1000000,
      "ecpm": 5.00
    },
    {
      "name": "com.example.news",
      "revenue": 4500.00,
      "impressions": 1500000,
      "ecpm": 3.00
    }
  ]
}`}
      />

      <ApiEndpoint
        method="POST"
        path="/chat/message"
        description="Sends a natural language query to the Ask GAM 360 AI and returns a streaming Server-Sent Events (SSE) response."
        request={`{
  "message": "Which website has the lowest fill rate this month?",
  "history": []
}`}
      />

      <ApiEndpoint
        method="POST"
        path="/api/alerts/trigger"
        description="Manually triggers the anomaly detection engine. If anomalies are found, email alerts are dispatched immediately."
        response={`{
  "status": "success",
  "message": "Alerts dispatched.",
  "anomalies_detected": 2
}`}
      />
    </div>
  );
}
