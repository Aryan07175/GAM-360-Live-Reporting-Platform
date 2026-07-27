import { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, Terminal, BookOpen, Layers } from "lucide-react";

export const metadata: Metadata = {
  title: "Introduction",
  description: "Getting started with GAM 360 Live Reporting Platform documentation.",
};

export default function DocsPage() {
  return (
    <div>
      <h1>Introduction</h1>
      <p className="text-xl text-muted-foreground mb-8">
        Welcome to the official documentation for the GAM 360 Live Reporting Platform.
        This platform is a Next.js executive BI reporting dashboard that fetches ad revenue analytics <strong>in real-time</strong> from Google Ad Manager 360.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 my-12">
        <Link href="/docs/local-development" className="group flex flex-col justify-between rounded-xl border border-border bg-card p-6 shadow-sm transition-all hover:shadow-md hover:border-primary/50">
          <div>
            <div className="mb-4 inline-flex rounded-lg bg-primary/10 p-3 text-primary">
              <Terminal className="h-6 w-6" />
            </div>
            <h3 className="mb-2 text-xl font-semibold m-0 text-foreground">Local Development</h3>
            <p className="text-muted-foreground m-0 text-sm">
              Learn how to set up the dashboard and MCP backend server locally on your machine.
            </p>
          </div>
          <div className="mt-6 flex items-center text-sm font-medium text-primary group-hover:underline">
            Get started <ArrowRight className="ml-1 h-4 w-4" />
          </div>
        </Link>

        <Link href="/docs/overview" className="group flex flex-col justify-between rounded-xl border border-border bg-card p-6 shadow-sm transition-all hover:shadow-md hover:border-primary/50">
          <div>
            <div className="mb-4 inline-flex rounded-lg bg-primary/10 p-3 text-primary">
              <BookOpen className="h-6 w-6" />
            </div>
            <h3 className="mb-2 text-xl font-semibold m-0 text-foreground">Overview</h3>
            <p className="text-muted-foreground m-0 text-sm">
              Understand the problem statement, business value, and how the platform works.
            </p>
          </div>
          <div className="mt-6 flex items-center text-sm font-medium text-primary group-hover:underline">
            Read overview <ArrowRight className="ml-1 h-4 w-4" />
          </div>
        </Link>

        <Link href="/docs/architecture" className="group flex flex-col justify-between rounded-xl border border-border bg-card p-6 shadow-sm transition-all hover:shadow-md hover:border-primary/50">
          <div>
            <div className="mb-4 inline-flex rounded-lg bg-primary/10 p-3 text-primary">
              <Layers className="h-6 w-6" />
            </div>
            <h3 className="mb-2 text-xl font-semibold m-0 text-foreground">Architecture</h3>
            <p className="text-muted-foreground m-0 text-sm">
              Explore the system architecture, data flow, and Next.js + Python integration.
            </p>
          </div>
          <div className="mt-6 flex items-center text-sm font-medium text-primary group-hover:underline">
            View architecture <ArrowRight className="ml-1 h-4 w-4" />
          </div>
        </Link>
      </div>
      
      <h2>Core Principles</h2>
      <ul>
        <li><strong>Zero database. Zero cache. Zero ETL.</strong> Data is fetched on-demand directly from Google's servers.</li>
        <li><strong>Unified Data Extraction.</strong> Consolidates Ad Server, AdSense, and Ad Exchange data into a single truth.</li>
        <li><strong>Zero Hallucinations.</strong> Ask GAM 360 uses strict tool-calling to fetch live data, guaranteeing accuracy.</li>
      </ul>
    </div>
  );
}
