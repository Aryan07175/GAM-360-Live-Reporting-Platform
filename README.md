# GAM 360 Revenue Pipeline — SOAP API + MCP + Live Dashboard

**🚀 Live Dashboard:** [https://dashboard-gvovzqt8y-aryan07175s-projects.vercel.app](https://dashboard-gvovzqt8y-aryan07175s-projects.vercel.app)

Full pipeline to extract revenue data from Google Ad Manager 360
using the SOAP API, store it in a Neon PostgreSQL database, visualize it
through a real-time Next.js dashboard, and expose it via MCP
for Claude-powered summarization and reporting.

---

## 🌐 Dashboard — How It Works

The dashboard is a **real-time analytics web application** that gives you a complete view of your Google Ad Manager 360 network performance. Here's what each section does:

### Pages & Features

| Page | What It Shows |
|------|--------------|
| **Overview** | Network-wide KPIs — Total Revenue, Impressions, Clicks, eCPM, Fill Rate, Ad Requests, Top App. Plus 30-day trend charts for Revenue, Impressions, and eCPM. |
| **Applications** | Per-app performance table with sortable columns (Revenue, Impressions, eCPM, Fill Rate, CTR). Searchable by app name. |
| **Revenue Analytics** | Revenue & eCPM trend charts + top earning applications breakdown. |
| **Anomaly Detection** | AI-driven anomaly detection comparing each app's daily revenue against its rolling 7-day average. Flags drops > 20% with severity levels (High / Medium / Low) and confidence scores. |
| **System Alerts** | Live alert feed generated from real data — flags low impressions, low revenue, and poor fill rates across all ad units. |
| **Reports** | Report generator with configurable date presets (Yesterday, Last 7 Days, Last 30 Days, This Month, Custom Range) and dimension selection. Tracks report status (Queued → Running → Completed) with CSV download. |

### Global Date Picker

The header contains an **interactive date picker** that controls all pages simultaneously:
- Click the date button to open a dropdown with a calendar input and quick-select shortcuts
- Navigate between days using ← / → arrow buttons
- A **LIVE** badge appears when viewing the latest available date from the database
- Changing the date instantly reloads data on every page

### Live Data & Auto-Refresh

- **Auto-refresh**: The dashboard automatically polls for new data every 5 minutes
- **Manual refresh**: Click the Refresh button in the header to immediately fetch the latest data from PostgreSQL
- **Export**: One-click CSV export of the current day's revenue data for all ad units

---

## 🏗️ Tech Stack

### Frontend — Dashboard (`/dashboard`)

| Technology | Purpose |
|-----------|---------|
| **Next.js 16** (App Router) | React framework with server actions, file-based routing |
| **TypeScript** | End-to-end type safety |
| **Tailwind CSS** | Utility-first styling |
| **shadcn/ui** | Accessible, composable UI components (Cards, Tables, Buttons, Selects, Badges) |
| **Recharts** | Interactive trend charts |
| **Lucide React** | Icon library |
| **date-fns** | Date manipulation and formatting |
| **next-themes** | Dark/Light mode toggle |
| **Vercel** | Production hosting with automatic deploys from GitHub |

### Backend — Data Pipeline (`/extractor`, `/database`, `/mcp_server`)

| Technology | Purpose |
|-----------|---------|
| **Python 3.12** | Pipeline orchestration and data extraction |
| **Google Ads API (SOAP)** | Pulls revenue reports from GAM 360 |
| **Neon PostgreSQL** | Cloud-hosted database storing all revenue data |
| **postgres (npm)** | Node.js PostgreSQL driver used by Next.js server actions |
| **MCP Server** | Model Context Protocol server for Claude AI integration |

### Infrastructure

| Service | Role |
|---------|------|
| **GitHub** | Source control — [Aryan07175/gam360api](https://github.com/Aryan07175/gam360api) |
| **Vercel** | Dashboard deployment with auto-deploy on push to `main` |
| **Neon** | Serverless PostgreSQL database |

---

## Architecture

```mermaid
graph TD
    GAM[GAM 360 SOAP API] -->|Downloads Report CSV| Extractor(extractor/gam_extractor.py)
    Extractor -->|Saves raw metrics & data| DB[(Neon PostgreSQL)]
    
    subgraph Daily Cron Job
    Cron[run_pipeline.py] -->|1. Triggers Pull| Extractor
    Cron -->|2. Queries DB| DB
    Cron -->|3. Analyzes Anomalies| DB
    Cron -->|4. Writes Report File| Reports["reports/*.md"]
    Cron -.->|5. Sends Alert| Slack[Slack Webhook]
    end

    subgraph Next.js Dashboard on Vercel
    Dashboard[Live Dashboard] -->|Server Actions| DB
    Dashboard -->|CSV Export| ExportAPI["/api/export"]
    end
    
    subgraph AI Integration via MCP
    Claude[Claude AI Assistant] -->|Queries Data via MCP| MCPServer(mcp_server/server.py)
    MCPServer -->|Runs SQL / Fetch| DB
    MCPServer -->|Can trigger fresh pull| Extractor
    end

    classDef api fill:#4285F4,stroke:#333,stroke-width:2px,color:white;
    classDef script fill:#f4b400,stroke:#333,stroke-width:2px,color:black;
    classDef db fill:#0f9d58,stroke:#333,stroke-width:2px,color:white;
    classDef ai fill:#db4437,stroke:#333,stroke-width:2px,color:white;
    classDef dashboard fill:#7c3aed,stroke:#333,stroke-width:2px,color:white;
    
    class GAM api;
    class Extractor,Cron script;
    class DB db;
    class Claude,MCPServer ai;
    class Dashboard,ExportAPI dashboard;
```

---

## Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure credentials
```bash
cp config/googleads.yaml.example config/googleads.yaml
# Fill in: network_code, path_to_private_key_file, application_name
```

### 3. Set up the database
```bash
python database/db.py --init
```

### 4. Run the extractor (pulls yesterday's revenue by app)
```bash
python extractor/gam_extractor.py --date yesterday
```

### 5. Start the MCP server
```bash
python mcp_server/server.py
```

### 6. Run the dashboard locally
```bash
cd dashboard
npm install
npm run dev
# Opens at http://localhost:3000
```

---

## Matching GAM 360 Dashboard

The SOAP API report uses the exact same dimensions/metrics as the GAM UI:

| GAM Dashboard column   | SOAP API Column                        |
|------------------------|----------------------------------------|
| Total revenue          | AD_SERVER_CPM_AND_CPC_REVENUE          |
| Impressions            | AD_SERVER_IMPRESSIONS                  |
| Clicks                 | AD_SERVER_CLICKS                       |
| eCPM                   | AD_SERVER_WITHOUT_CPD_AVERAGE_ECPM     |
| Fill rate              | AD_SERVER_FILL_RATE                    |
| Ad requests            | AD_SERVER_AD_REQUESTS                  |

| GAM Dashboard dimension | SOAP API Dimension                     |
|-------------------------|----------------------------------------|
| App name (ad unit)      | AD_UNIT_NAME                           |
| Date                    | DATE                                   |
| Order                   | ORDER_NAME                             |
| Line item               | LINE_ITEM_NAME                         |
| Ad type                 | AD_REQUEST_AD_TYPE                     |
| Country                 | COUNTRY_NAME                           |

## Per-app revenue

GAM 360 organises apps as **Ad Units** in the inventory hierarchy.
Each mobile app has a top-level ad unit (e.g. "com.yourco.appname").
The extractor uses `AD_UNIT_NAME` + `AD_UNIT_ID` dimensions and
filters by parent ad unit to isolate each app.

---

## 📂 Project Structure

```
gam360-pipeline/
├── config/                  # GAM API credentials
├── database/                # Database schema & connection (db.py)
├── extractor/               # GAM SOAP API extractor (gam_extractor.py)
├── mcp_server/              # MCP server for Claude AI integration
├── reports/                 # Generated markdown reports
├── run_pipeline.py          # Daily pipeline orchestrator
├── dashboard/               # Next.js analytics dashboard
│   ├── src/
│   │   ├── app/             # App Router pages
│   │   │   ├── (dashboard)/ # Dashboard pages (Overview, Apps, Revenue, etc.)
│   │   │   └── api/         # API routes (CSV export)
│   │   ├── components/      # UI components (header, sidebar, charts, cards)
│   │   ├── contexts/        # React contexts (DateContext for shared state)
│   │   ├── services/        # Server actions (PostgreSQL queries)
│   │   └── types/           # TypeScript type definitions
│   └── package.json
└── README.md
```

---

## License

MIT
