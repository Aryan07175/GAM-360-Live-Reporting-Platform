"use client";

import { Hero } from "@/components/home/Hero";
import { FeatureCard } from "@/components/ui/FeatureCard";
import { TechCard } from "@/components/ui/TechCard";
import { DiagramCard } from "@/components/ui/DiagramCard";
import { MetricCard } from "@/components/ui/MetricCard";
import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";
import { 
  BarChart3, 
  MessageSquare, 
  Globe, 
  Bell, 
  Zap, 
  LineChart,
  Server,
  Cloud,
  Database,
  Cpu
} from "lucide-react";

export default function Home() {
  const architectureDiagram = `
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

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <Navbar />
      
      <main className="flex-1">
        <Hero />

        {/* Stats Section */}
        <section className="py-20 border-y border-border bg-muted/20">
          <div className="container mx-auto px-4 md:px-8">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
              <MetricCard value="18+" label="Live Analytics Tools" delay={0.1} />
              <MetricCard value="100%" label="Real-time Data" delay={0.2} />
              <MetricCard value="0" label="Databases Needed" delay={0.3} />
              <MetricCard value="< 1s" label="AI Query Response" delay={0.4} />
            </div>
          </div>
        </section>

        {/* Features Section */}
        <section className="py-24">
          <div className="container mx-auto px-4 md:px-8">
            <div className="mb-16 text-center">
              <h2 className="text-3xl font-bold tracking-tight md:text-4xl lg:text-5xl mb-4">
                Enterprise Features. Zero Overhead.
              </h2>
              <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
                Built for publishers who need immediate insights without the complexity of traditional ETL pipelines and data warehouses.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              <FeatureCard
                title="Website Intelligence"
                description="Live website inventory data directly from Google Ad Manager without any database caching. Track health, domains, CTRs."
                icon={Globe}
                delay={0.1}
              />
              <FeatureCard
                title="Ask GAM 360 AI"
                description="Context-aware AI assistant powered by Claude Haiku 4.5. Ask natural language questions with zero hallucinations."
                icon={MessageSquare}
                delay={0.2}
              />
              <FeatureCard
                title="Unified Revenue"
                description="Combines Ad Server, AdSense, and Ad Exchange into a single consolidated view across your entire network."
                icon={BarChart3}
                delay={0.3}
              />
              <FeatureCard
                title="AI Anomaly Detection"
                description="Compares current performance against historical averages to detect sudden drops or spikes in real-time."
                icon={Zap}
                delay={0.4}
              />
              <FeatureCard
                title="Real-Time Alerts"
                description="Integrated email system sends instant alerts when anomalies are detected and daily executive reports."
                icon={Bell}
                delay={0.5}
              />
              <FeatureCard
                title="Progressive Loading"
                description="Data loads incrementally via Server Actions, keeping the UI highly responsive as reports load in parallel."
                icon={LineChart}
                delay={0.6}
              />
            </div>
          </div>
        </section>

        {/* Architecture Section */}
        <section className="py-24 bg-muted/30 border-y border-border">
          <div className="container mx-auto px-4 md:px-8">
            <div className="mb-12 text-center">
              <h2 className="text-3xl font-bold tracking-tight md:text-4xl mb-4">
                System Architecture
              </h2>
              <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
                A streamlined, stateless architecture that connects directly to Google Ad Manager and AWS Bedrock.
              </p>
            </div>
            
            <div className="max-w-5xl mx-auto">
              <DiagramCard 
                chart={architectureDiagram} 
                title="End-to-End Data Flow"
                description="Click the expand icon to view full screen"
              />
            </div>
          </div>
        </section>

        {/* Tech Stack Section */}
        <section className="py-24">
          <div className="container mx-auto px-4 md:px-8">
            <div className="mb-16 text-center">
              <h2 className="text-3xl font-bold tracking-tight md:text-4xl mb-4">
                Built with Modern Technologies
              </h2>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 max-w-5xl mx-auto">
              <TechCard
                name="Next.js 15"
                category="Frontend"
                description="App Router, Server Actions, and React Context for state management."
                icon={<Globe />}
              />
              <TechCard
                name="Python 3.12"
                category="Backend"
                description="Starlette & Uvicorn for REST API and Server-Sent Events (SSE) streaming."
                icon={<Server />}
              />
              <TechCard
                name="Claude Haiku 4.5"
                category="AI Layer"
                description="AWS Bedrock integration for blazing fast, highly accurate tool-calling."
                icon={<Cpu />}
              />
              <TechCard
                name="Google Ad Manager"
                category="Data Source"
                description="Direct connection to the SOAP API for 100% live analytics."
                icon={<Database />}
              />
            </div>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  );
}
