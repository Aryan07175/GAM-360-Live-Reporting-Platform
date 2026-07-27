import { Metadata } from "next";
import { FileTree, FileNode } from "@/components/ui/FileTree";

export const metadata: Metadata = {
  title: "Project Structure",
  description: "Directory and file structure for the GAM 360 Live Reporting Platform.",
};

export default function ProjectStructurePage() {
  const treeData: FileNode[] = [
    {
      name: "GAM-360-Live-Reporting-Platform",
      type: "folder",
      children: [
        {
          name: "dashboard",
          type: "folder",
          description: "Next.js Frontend",
          children: [
            {
              name: "src/app",
              type: "folder",
              description: "App Router pages and API routes",
              children: [
                { name: "page.tsx", type: "file", icon: "code" },
                { name: "layout.tsx", type: "file", icon: "code" },
              ]
            },
            {
              name: "src/components",
              type: "folder",
              description: "React components (shadcn/ui, chat, charts)",
            },
            {
              name: "package.json",
              type: "file",
              icon: "json"
            }
          ]
        },
        {
          name: "mcp_server",
          type: "folder",
          description: "Python Backend Services",
          children: [
            { name: "server.py", type: "file", icon: "code", description: "Main Starlette API and SSE routes" },
            { name: "gam_client.py", type: "file", icon: "code", description: "Google Ad Manager SOAP API client" },
            { name: "email_service.py", type: "file", icon: "code", description: "Daily reports and notifications" },
            { name: "render_start.py", type: "file", icon: "code", description: "Render.com startup script" },
            {
              name: "services",
              type: "folder",
              children: [
                { name: "bedrock_service.py", type: "file", icon: "code", description: "AWS Bedrock integration" }
              ]
            }
          ]
        },
        {
          name: "config",
          type: "folder",
          description: "Configuration and secrets",
          children: [
            { name: ".env", type: "file", description: "Local environment variables" },
            { name: "googleads.yaml", type: "file", description: "GAM SOAP API credentials" },
            { name: "service_account.json", type: "file", icon: "json", description: "Google Cloud Service Account key" }
          ]
        },
        { name: "render.yaml", type: "file", description: "Render deployment blueprint" },
        { name: "requirements.txt", type: "file", description: "Python dependencies" },
        { name: "README.md", type: "file" }
      ]
    }
  ];

  return (
    <div>
      <h1>Project Structure</h1>
      <p>
        The repository is structured as a monorepo containing both the Next.js frontend (<code>/dashboard</code>) and the Python backend (<code>/mcp_server</code>).
      </p>

      <FileTree data={treeData} />

      <h2>Key Directories</h2>
      
      <h3><code>/mcp_server</code> (Backend)</h3>
      <p>
        The Python backend uses <strong>Starlette</strong> and <strong>Uvicorn</strong> to provide high-performance async REST and SSE streaming endpoints. It acts as the bridge between the Next.js dashboard, the Google Ad Manager SOAP API, and AWS Bedrock.
      </p>
      
      <h3><code>/dashboard</code> (Frontend)</h3>
      <p>
        The frontend is built with <strong>Next.js 15</strong> (App Router) and <strong>TypeScript</strong>. It handles all data fetching and progressive rendering of charts (Recharts) and UI components (shadcn/ui).
      </p>
      
      <h3><code>/config</code></h3>
      <p>
        Contains all secrets and credentials needed to connect to Google APIs and AWS. These files should be gitignored in your actual implementation.
      </p>
    </div>
  );
}
