import { Metadata } from "next";
import { DiagramCard } from "@/components/ui/DiagramCard";

export const metadata: Metadata = {
  title: "Architecture",
  description: "System architecture and data flow of the GAM 360 Live Reporting Platform.",
};

export default function ArchitecturePage() {
  const systemArchitecture = `
graph TD
    User([User]) -->|Views Dashboard & Asks Questions| NextJS[Next.js Dashboard UI]
    NextJS -->|REST API & SSE Streams| Python[Python Backend Server]

    Python -->|Fetches Live Analytics| GAM[Google Ad Manager API]
    GAM -->|Returns Raw Data| Python

    Python -->|Data Summary & Tools| Bedrock[AWS Bedrock - Claude Haiku 4.5]
    Bedrock -.->|Streams Chat Response| Python

    Python -->|Formats & Caches Data| NextJS

    Python -->|Background Tasks| Cron[Scheduled Daily Reports]
    Cron -->|SMTP| Gmail[Gmail Notifications]
    Python -->|Live Alert Triggers| Gmail
  `;

  const requestLifecycle = `
sequenceDiagram
    participant User
    participant NextJS as Next.js Dashboard
    participant Python as Backend Server
    participant GAM as Ad Manager API
    
    User->>NextJS: Opens Dashboard (Selects Last 7 Days)
    NextJS->>Python: GET /api/network/summary?date=7d
    NextJS->>Python: GET /api/inventory/top?date=7d
    
    Python->>GAM: SOAP Request: AdServer Yield
    Python->>GAM: SOAP Request: AdExchange Yield
    Python->>GAM: SOAP Request: AdSense Yield
    
    Note over Python,GAM: Python runs parallel requests via asyncio
    
    GAM-->>Python: Raw SOAP XML Responses
    Python->>Python: Pandas DataFrame Merge & Aggregation
    
    Python-->>NextJS: JSON: Unified Analytics
    NextJS-->>User: Renders Charts & Tables
  `;

  const chatFlow = `
sequenceDiagram
    participant User
    participant Frontend
    participant Backend
    participant Bedrock
    participant GAM
    
    User->>Frontend: "Which website has lowest fill rate?"
    Frontend->>Backend: POST /chat/message
    Backend->>Bedrock: Send prompt + Available Tools
    Bedrock-->>Backend: ToolCall: getWebsiteInventory
    Backend->>GAM: Fetch Website Data
    GAM-->>Backend: Raw Data
    Backend->>Backend: Process Metrics (Pandas)
    Backend->>Bedrock: Send Result (Lowest: example.com)
    Bedrock-->>Backend: Stream Answer Text
    Backend-->>Frontend: SSE Stream Chunk
    Frontend-->>User: Typing...
  `;

  return (
    <div>
      <h1>System Architecture</h1>
      <p>
        The platform uses a decoupled frontend-backend architecture. Next.js handles all UI and state management, while a Starlette Python server manages concurrent API requests to Google Ad Manager and AWS Bedrock.
      </p>

      <h2>End-to-End Architecture</h2>
      <DiagramCard chart={systemArchitecture} />

      <h2>Request Lifecycle</h2>
      <p>
        Because there is no database, the system must fetch data efficiently. The backend uses Python's <code>asyncio</code> to batch and parallelize SOAP requests to Google Ad Manager. It then uses <code>pandas</code> to merge the Ad Server, AdSense, and Ad Exchange channels together.
      </p>
      <DiagramCard chart={requestLifecycle} />

      <h2>Ask GAM 360 (AI Chat Flow)</h2>
      <p>
        The chat system uses a multi-tool architecture powered by AWS Bedrock. The model is given a list of tools it can call. When a user asks a question, the model routes the intent to the correct tool, the backend fetches the live data, and the model streams the summarized answer back via Server-Sent Events (SSE).
      </p>
      <DiagramCard chart={chatFlow} />
    </div>
  );
}
