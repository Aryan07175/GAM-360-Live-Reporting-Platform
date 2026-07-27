import { Metadata } from "next";
import { Timeline } from "@/components/ui/Timeline";
import { CheckCircle2, Target, TrendingUp, Lightbulb } from "lucide-react";

export const metadata: Metadata = {
  title: "Overview",
  description: "Problem statement, solution, and goals for the GAM 360 Live Reporting Platform.",
};

export default function OverviewPage() {
  const goals = [
    {
      title: "Real-time accuracy",
      description: "Eliminate the delay in standard ETL pipelines. See your ad performance exactly as it is right now in Google Ad Manager.",
      icon: <Target className="h-4 w-4" />
    },
    {
      title: "Actionable Insights",
      description: "Don't just show data. Have the Ask GAM 360 AI proactively identify anomalies and explain revenue drops.",
      icon: <Lightbulb className="h-4 w-4" />
    },
    {
      title: "Consolidated Truth",
      description: "Merge Ad Server, AdSense, and Ad Exchange into a single unified truth for true network-wide reporting.",
      icon: <CheckCircle2 className="h-4 w-4" />
    },
    {
      title: "Zero Infrastructure",
      description: "Operate entirely stateless. No caching layer, no SQL database, and no data warehouse to maintain.",
      icon: <TrendingUp className="h-4 w-4" />
    }
  ];

  return (
    <div>
      <h1>Project Overview</h1>
      
      <h2>The Problem</h2>
      <p>
        Publishers using Google Ad Manager 360 often struggle with data latency and complex reporting setups. 
        Traditional architectures require building complex ETL (Extract, Transform, Load) pipelines to pull data from GAM's API, store it in a data warehouse (like BigQuery), and then serve it to a BI tool. 
      </p>
      <p>
        This process is:
      </p>
      <ul>
        <li><strong>Slow:</strong> Data is often hours or a full day behind.</li>
        <li><strong>Expensive:</strong> Requires maintaining databases, cron jobs, and caching layers.</li>
        <li><strong>Fragmented:</strong> Hard to consolidate Ad Server (Direct), AdSense (Backfill), and Ad Exchange (Programmatic) data perfectly.</li>
      </ul>

      <h2>The Solution</h2>
      <p>
        The <strong>GAM 360 Live Reporting Platform</strong> bypasses the data warehouse entirely. It connects the Next.js frontend directly to a Python backend, which connects directly to the Google Ad Manager SOAP API. 
      </p>
      <div className="my-8 rounded-xl bg-primary/10 p-6 border border-primary/20">
        <h3 className="text-primary mt-0">100% Live, 0% Database</h3>
        <p className="mb-0 text-foreground/80">
          When a user opens the dashboard, the Python backend fetches the exact analytics required straight from Google's servers, merges the channels, and serves it to the frontend via Server-Sent Events and REST.
        </p>
      </div>

      <h2>Business Goals</h2>
      <Timeline events={goals} />

      <h2>How It Works</h2>
      <ol className="space-y-4">
        <li><strong>Global Context:</strong> The Next.js dashboard uses a global React Context to manage state. When the date range changes, the context updates.</li>
        <li><strong>Progressive Loading:</strong> Data is loaded incrementally via <code>Promise.allSettled</code>, keeping the UI highly responsive.</li>
        <li><strong>Bounded Parallelism:</strong> When fetching multi-day trends, the Python backend batches requests and executes them in parallel against the GAM API.</li>
        <li><strong>Deduplication:</strong> The server uses <code>asyncio.Lock</code> to coalesce concurrent identical requests within a 30-second window, preventing Google Ad Manager API rate limits.</li>
      </ol>
    </div>
  );
}
