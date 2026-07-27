export interface SearchRecord {
  id: string;
  title: string;
  content: string;
  href: string;
  category: string;
}

export const searchData: SearchRecord[] = [
  {
    id: "1",
    title: "Introduction",
    content: "Getting started with the GAM 360 Live Reporting Platform documentation.",
    href: "/docs",
    category: "Getting Started",
  },
  {
    id: "2",
    title: "Overview",
    content: "Problem statement, solution, business goals, and how the platform works.",
    href: "/docs/overview",
    category: "Getting Started",
  },
  {
    id: "3",
    title: "Local Development",
    content: "How to set up the dashboard and MCP server locally, configure credentials, and start the development servers.",
    href: "/docs/local-development",
    category: "Getting Started",
  },
  {
    id: "4",
    title: "Project Structure",
    content: "Detailed file and folder structure of the repository, including frontend and backend.",
    href: "/docs/project-structure",
    category: "Getting Started",
  },
  {
    id: "5",
    title: "Features",
    content: "Website intelligence engine, Ask GAM 360 AI, real-time dashboard, unified revenue, and more.",
    href: "/docs/features",
    category: "Core Concepts",
  },
  {
    id: "6",
    title: "Architecture",
    content: "System architecture, request lifecycle, Next.js frontend, Python backend, and AWS Bedrock integration.",
    href: "/docs/architecture",
    category: "Core Concepts",
  },
  {
    id: "7",
    title: "Ask GAM 360",
    content: "Context-aware AI assistant using Claude Haiku 4.5. Intent routing, tool calling, zero hallucination design.",
    href: "/docs/ask-gam-360",
    category: "AI Layer",
  },
  {
    id: "8",
    title: "API Reference",
    content: "API documentation for the backend endpoints including request and response examples.",
    href: "/docs/api",
    category: "Reference",
  },
  {
    id: "9",
    title: "Tech Stack",
    content: "Technologies used including Next.js, TypeScript, Tailwind, Python, Starlette, Pandas, AWS Bedrock.",
    href: "/docs/tech-stack",
    category: "Reference",
  },
  {
    id: "10",
    title: "Deployment",
    content: "How to deploy the backend to Render, frontend to Vercel, and configure environment variables.",
    href: "/docs/deployment",
    category: "Reference",
  },
];
