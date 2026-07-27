import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Deployment",
  description: "Deploying the GAM 360 Live Reporting Platform to production.",
};

export default function DeploymentPage() {
  return (
    <div>
      <h1>Deployment</h1>
      <p>
        The platform is designed to be deployed as two separate services: a static Next.js frontend (Vercel, Netlify, or GitHub Pages) and a Python backend (Render, Heroku, or AWS).
      </p>

      <h2>Backend → Render</h2>
      <p>
        A <code>render.yaml</code> blueprint is included in the repository for one-click deployment to Render.com.
      </p>
      
      <h3>Environment Variables</h3>
      <p>Set the following variables in your Render service:</p>

      <div className="overflow-x-auto my-6">
        <table className="w-full text-sm text-left border border-border">
          <thead className="bg-muted/50 text-foreground">
            <tr>
              <th className="px-4 py-3 border-b border-border">Variable</th>
              <th className="px-4 py-3 border-b border-border">Description</th>
            </tr>
          </thead>
          <tbody>
            <tr className="border-b border-border">
              <td className="px-4 py-3 font-mono text-primary">GAM_CREDENTIALS_PATH</td>
              <td className="px-4 py-3">Path to your GAM credentials file</td>
            </tr>
            <tr className="border-b border-border">
              <td className="px-4 py-3 font-mono text-primary">GAM_NETWORK_CODE</td>
              <td className="px-4 py-3">Your Google Ad Manager network code</td>
            </tr>
            <tr className="border-b border-border">
              <td className="px-4 py-3 font-mono text-primary">AWS_BEARER_TOKEN_BEDROCK</td>
              <td className="px-4 py-3">Your AWS Bedrock API key</td>
            </tr>
            <tr className="border-b border-border">
              <td className="px-4 py-3 font-mono text-primary">AWS_REGION</td>
              <td className="px-4 py-3">AWS region (e.g. <code>us-east-1</code>)</td>
            </tr>
            <tr className="border-b border-border">
              <td className="px-4 py-3 font-mono text-primary">BEDROCK_MODEL_ID</td>
              <td className="px-4 py-3">e.g. <code>us.anthropic.claude-haiku-4-5-20251001-v1:0</code></td>
            </tr>
            <tr className="border-b border-border">
              <td className="px-4 py-3 font-mono text-primary">GMAIL_SENDER_EMAIL</td>
              <td className="px-4 py-3">Gmail address for email alerts (optional)</td>
            </tr>
            <tr>
              <td className="px-4 py-3 font-mono text-primary">GMAIL_APP_PASSWORD</td>
              <td className="px-4 py-3">Gmail App Password for SMTP (optional)</td>
            </tr>
          </tbody>
        </table>
      </div>

      <h2>Frontend → Vercel</h2>
      <p>
        Deploy the <code>/dashboard</code> directory to Vercel. 
      </p>

      <h3>Environment Variables</h3>
      <p>Set the following in your Vercel project settings:</p>

      <div className="overflow-x-auto my-6">
        <table className="w-full text-sm text-left border border-border">
          <thead className="bg-muted/50 text-foreground">
            <tr>
              <th className="px-4 py-3 border-b border-border">Variable</th>
              <th className="px-4 py-3 border-b border-border">Value</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td className="px-4 py-3 font-mono text-primary">NEXT_PUBLIC_MCP_SERVER_URL</td>
              <td className="px-4 py-3">Your Render backend URL (e.g. <code>https://gam360-backend.onrender.com</code>)</td>
            </tr>
          </tbody>
        </table>
      </div>

      <h2>Documentation → GitHub Pages</h2>
      <p>
        This documentation site is deployed automatically to GitHub Pages using a GitHub Actions workflow. Every time you push to the <code>main</code> branch, the Next.js site in <code>/docs</code> is built statically (<code>output: "export"</code>) and deployed.
      </p>
    </div>
  );
}
