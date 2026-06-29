# GAM 360 Revenue Pipeline Summary

This document serves as a high-level overview of the pipeline's architecture and how its different components work together.

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
