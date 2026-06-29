# GAM 360 Revenue Pipeline Summary

This document serves as a high-level overview of the pipeline's architecture and how its different components work together.

## Architecture Diagram

```mermaid
graph TD
    GAM[GAM 360 SOAP API] -->|Downloads Report CSV| Extractor(extractor/gam_extractor.py)
    Extractor -->|Saves raw metrics & data| DB[(Database: db.py)]
    
    subgap1[Daily Cron Job]
    Cron[run_pipeline.py] -->|1. Triggers Pull| Extractor
    Cron -->|2. Queries DB| DB
    Cron -->|3. Analyzes Anomalies| DB
    Cron -->|4. Writes Report File| Reports[/reports/*.md/]
    Cron -.->|5. Sends Alert| Slack[Slack Webhook]
    end
    
    subgap2[AI Integration via MCP]
    Claude[Claude AI Assistant] -->|Queries Data via MCP| MCPServer(mcp_server/server.py)
    MCPServer -->|Runs SQL / Fetch| DB
    MCPServer -->|Can trigger fresh pull| Extractor
    end

    classDef api fill:#4285F4,stroke:#333,stroke-width:2px,color:white;
    classDef script fill:#f4b400,stroke:#333,stroke-width:2px,color:black;
    classDef db fill:#0f9d58,stroke:#333,stroke-width:2px,color:white;
    classDef ai fill:#db4437,stroke:#333,stroke-width:2px,color:white;
    
    class GAM api;
    class Extractor,Cron script;
    class DB db;
    class Claude,MCPServer ai;
```

## 1. The Extractor (`extractor/gam_extractor.py`)
- **Purpose:** Connects to the GAM 360 SOAP API to run report jobs.
- **Functionality:** It pulls down yesterday's ad revenue, impressions, eCPM, and fill rates. The data is broken down by individual mobile apps, which are represented as Ad Units in GAM.

## 2. The Database (`database/db.py`)
- **Purpose:** Stores the extracted CSV data locally.
- **Functionality:** Saves the data into a local SQLite or PostgreSQL database. It includes built-in logic to calculate week-over-week trends and detect anomalies (e.g., triggering an alert if a specific app's revenue drops by more than 20% compared to its 7-day average).

## 3. The Daily Automation (`run_pipeline.py`)
- **Purpose:** Automates the daily extraction and reporting process.
- **Functionality:** Designed to run via a daily cron job (e.g., at 6 AM). It triggers the extractor, generates a Markdown-formatted revenue report in the `reports/` folder, and optionally sends a Slack alert summarizing the total revenue and any detected drops/anomalies.

## 4. The AI Server (`mcp_server/server.py`)
- **Purpose:** Acts as a Model Context Protocol (MCP) bridge between the GAM data and AI models like Claude.
- **Functionality:** It exposes backend database tools so an AI can be queried dynamically. For example, you can ask an AI assistant:
  - *"Which apps had a revenue drop yesterday?"*
  - *"Show me the 30-day revenue trend for App X."*
  The AI uses this server to fetch the exact numbers and provide insights interactively.

---
**In short:** The pipeline automates pulling daily ad revenue, looks for sudden drops in performance, and allows an AI to chat directly with your ad data to answer on-demand questions.
