import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Features",
  description: "Core features of the GAM 360 Live Reporting Platform.",
};

export default function FeaturesPage() {
  return (
    <div>
      <h1>Platform Features</h1>
      <p>
        The GAM 360 Live Reporting Platform is a comprehensive business intelligence tool designed specifically for publishers. Here are the core features.
      </p>

      <h2>Website Intelligence Engine</h2>
      <p>
        Fully supports Website-level reporting alongside App-level reporting. Pulls 100% live website inventory data directly from Google Ad Manager without any database caching. Easily track website health, top performing domains, CTRs, and impressions.
      </p>

      <h2>Ask GAM 360 (AI Chat)</h2>
      <p>
        A built-in, context-aware AI assistant powered by <strong>AWS Bedrock (Anthropic Claude Haiku 4.5)</strong>. Ask complex questions about your network in natural language — e.g., <em>"Which website has the highest revenue?"</em>, <em>"Are any websites critical?"</em>, or <em>"Show me the bottom 3 apps by eCPM"</em>. It uses strict tool-calling to fetch live GAM data, guaranteeing zero hallucinated numbers, and streams responses instantly.
      </p>

      <h2>Real-Time BI Dashboard</h2>
      <p>
        Generates comprehensive business intelligence reports dynamically using live data.
      </p>

      <h2>Unified Revenue</h2>
      <p>
        Combines Ad Server, AdSense, and Ad Exchange into a single consolidated view. Most dashboards show these channels separately, forcing you to manually calculate total yield.
      </p>

      <h2>18+ Live Analytics Tools</h2>
      <p>
        Executive summaries, revenue by app/website, trends, top/bottom inventory, impressions, clicks, CTR, eCPM, fill rate, and ad requests.
      </p>

      <h2>AI Anomaly Detection</h2>
      <p>
        Compares current performance against historical averages to detect sudden drops or spikes in real-time. Know instantly if a recent app deployment broke ad requests or if fill rate drops on a specific website.
      </p>

      <h2>Email Notifications</h2>
      <p>
        Integrated settings panel to manage recipients. Automatically sends instant alerts when anomalies are detected and dispatches a full Executive Report via Gmail every day.
      </p>

      <h2>Interactive UI</h2>
      <p>
        Custom date ranges (down to the hour), dark mode, and progressive loading skeletons. Built with Next.js App Router for extreme performance.
      </p>
    </div>
  );
}
