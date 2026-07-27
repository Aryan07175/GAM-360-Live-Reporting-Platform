import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Ask GAM 360",
  description: "AI-powered context-aware assistant for Google Ad Manager.",
};

export default function AskGAM360Page() {
  return (
    <div>
      <h1>Ask GAM 360</h1>
      <p>
        <strong>Ask GAM 360</strong> is a highly capable, context-aware AI reporting analyst powered by <strong>AWS Bedrock (Anthropic Claude Haiku 4.5)</strong>. It uses a multi-tool architecture to fetch <strong>100% live data</strong> directly from Google Ad Manager, ensuring <strong>zero hallucinations</strong>.
      </p>

      <h2>How it Works (Under the Hood)</h2>
      <ol>
        <li><strong>Intent Routing:</strong> The AI reads your question and selects the most optimal backend tool (e.g., <code>getMatchRateAnalytics</code>, <code>getChildNetworkAnalytics</code>).</li>
        <li><strong>Live Data Fetching:</strong> The Python backend connects to the Google Ad Manager API and fetches the exact data requested.</li>
        <li><strong>Pre-computation:</strong> The backend aggregates the data, scores health (Excellent/Warning/Critical), detects anomalies (e.g., zero revenue, low fill), and computes raw insights.</li>
        <li><strong>Streaming Response:</strong> The AI formats these computed insights into a natural, easy-to-read response and streams it token-by-token to the frontend.</li>
      </ol>

      <h2>Question Categories</h2>
      <p>
        Ask GAM 360 supports an extensive range of queries across multiple dimensions. Here are the categories of questions it can answer out-of-the-box:
      </p>

      <h3>1. Network Code Intelligence & Health</h3>
      <p>
        Get a high-level overview of your entire network's performance, complete with automatic anomaly detection and AI-generated insights (strengths, weaknesses, optimization opportunities).
      </p>
      <ul>
        <li><em>"Show network summary"</em></li>
        <li><em>"What is my network health?"</em></li>
        <li><em>"Network performance for the past 30 days"</em></li>
        <li><em>"Show network 12345678"</em></li>
      </ul>

      <h3>2. Child Network (MCM) Analytics</h3>
      <p>
        If you use Multiple Customer Management (MCM), you can analyze all your child networks instantly. The AI will compare them, rank them, and flag networks with critical issues.
      </p>
      <ul>
        <li><em>"List all child networks"</em></li>
        <li><em>"Which child network has the highest revenue?"</em></li>
        <li><em>"Compare child networks by fill rate"</em></li>
        <li><em>"Show child networks needing optimization"</em></li>
      </ul>

      <h3>3. Match Rate Analytics</h3>
      <p>
        Analyze programmatic Match Rate (Matched Requests ÷ Total Ad Requests) across any dimension.
      </p>
      <ul>
        <li><em>"What is the match rate by app?"</em></li>
        <li><em>"Which website has the lowest match rate?"</em></li>
        <li><em>"Show apps with match rate below 60%"</em></li>
      </ul>

      <h3>4. App & Website Intelligence</h3>
      <p>
        Deep dive into specific inventory sources. The AI automatically detects if you are asking about a mobile app or a web domain.
      </p>
      <ul>
        <li><em>"Which website generated the most clicks?"</em></li>
        <li><em>"Show the best performing apps this month"</em></li>
        <li><em>"Are there any critical websites right now?"</em></li>
        <li><em>"Find websites losing revenue compared to yesterday"</em></li>
      </ul>

      <h3>5. Advanced Metric Ranking & Filtering</h3>
      <p>
        Sort and filter live data across 20+ preset timeframes (YTD, MTD, past 7 days, etc.) or custom date ranges.
      </p>
      <ul>
        <li><em>"Show the top 5 ad units by eCPM"</em></li>
        <li><em>"Which app has the lowest fill rate?"</em></li>
        <li><em>"Show bottom 3 websites by impressions"</em></li>
      </ul>

      <h2>Zero Hallucination Design</h2>
      <p>
        Large Language Models (LLMs) are notoriously bad at math. Ask GAM 360 solves this by <strong>forbidding the LLM from doing calculations</strong>.
      </p>
      <p>
        When you ask "What is the total revenue?", the LLM does not calculate the sum. It simply calls the <code>query_gam_data</code> tool. The Python backend fetches the rows, Pandas computes the exact sum, and returns the final number to the LLM. The LLM only acts as a natural language formatting layer over deterministic Python mathematics.
      </p>
    </div>
  );
}
