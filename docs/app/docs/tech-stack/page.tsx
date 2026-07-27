import { Metadata } from "next";
import { TechCard } from "@/components/ui/TechCard";
import { 
  Globe, 
  Server, 
  Cpu, 
  Database,
  MonitorPlay,
  Mail,
  Zap,
  Layout
} from "lucide-react";

export const metadata: Metadata = {
  title: "Tech Stack",
  description: "Technologies used in the GAM 360 Live Reporting Platform.",
};

export default function TechStackPage() {
  return (
    <div>
      <h1>Technology Stack</h1>
      <p>
        The GAM 360 Live Reporting Platform is built with a modern, high-performance tech stack designed for speed, type safety, and real-time data streaming.
      </p>

      <h2>Frontend (Next.js Dashboard)</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 my-6">
        <TechCard
          name="Next.js 15"
          category="Framework"
          description="React framework using the App Router for server-side rendering and static export."
          icon={<Globe />}
        />
        <TechCard
          name="TypeScript"
          category="Language"
          description="Strict type safety across the entire codebase."
          icon={<Layout />}
        />
        <TechCard
          name="Tailwind CSS"
          category="Styling"
          description="Utility-first CSS framework for rapid UI development."
          icon={<MonitorPlay />}
        />
        <TechCard
          name="shadcn/ui"
          category="Components"
          description="Beautifully designed, accessible, and customizable components."
          icon={<Layout />}
        />
        <TechCard
          name="Recharts"
          category="Data Viz"
          description="Composable charting library built on React components."
          icon={<Zap />}
        />
        <TechCard
          name="Framer Motion"
          category="Animation"
          description="Production-ready animation library for React."
          icon={<Zap />}
        />
      </div>

      <h2>Backend (MCP Server)</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 my-6">
        <TechCard
          name="Python 3.12"
          category="Language"
          description="Core language for the backend API and data processing."
          icon={<Server />}
        />
        <TechCard
          name="Starlette"
          category="Framework"
          description="Lightweight, async ASGI framework ideal for SSE streaming."
          icon={<Zap />}
        />
        <TechCard
          name="Uvicorn"
          category="Server"
          description="Lightning-fast ASGI web server implementation."
          icon={<Server />}
        />
        <TechCard
          name="Pandas"
          category="Data Processing"
          description="Powerful data manipulation library for merging GAM channels."
          icon={<Database />}
        />
        <TechCard
          name="AWS Bedrock"
          category="AI"
          description="Managed service for foundational models. Uses Claude Haiku 4.5."
          icon={<Cpu />}
        />
        <TechCard
          name="Google Ads SOAP"
          category="API"
          description="Official Google Ad Manager API client for Python."
          icon={<Database />}
        />
        <TechCard
          name="smtplib"
          category="Notifications"
          description="Standard Python library for sending email alerts."
          icon={<Mail />}
        />
      </div>
    </div>
  );
}
