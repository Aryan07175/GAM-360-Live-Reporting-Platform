import { Metadata } from "next";
import { CodeBlock } from "@/components/ui/CodeBlock";
import { StepCard } from "@/components/ui/StepCard";

export const metadata: Metadata = {
  title: "Local Development",
  description: "Set up the GAM 360 Live Reporting Platform locally.",
};

export default function LocalDevelopmentPage() {
  return (
    <div>
      <h1>Local Development</h1>
      <p>
        Follow these steps to get the GAM 360 Live Reporting Platform running locally on your machine.
      </p>

      <div className="mt-12">
        <StepCard number={1} title="Clone and Install Dependencies">
          <p>First, clone the repository and install the Python dependencies for the backend.</p>
          <CodeBlock 
            code="pip install -r requirements.txt" 
            language="bash" 
          />
        </StepCard>

        <StepCard number={2} title="Configure Credentials">
          <p>Copy the example environment files to set up your configuration.</p>
          <CodeBlock 
            code={`cp config/googleads.yaml.example config/googleads.yaml\ncp config/.env.example config/.env`}
            language="bash" 
          />
          <p className="mt-4 font-semibold text-foreground">Edit config/googleads.yaml:</p>
          <CodeBlock 
            code={`network_code: YOUR_NETWORK_CODE\napplication_name: GAM360-Revenue-Pipeline\npath_to_private_key_file: config/service_account.json`}
            language="yaml" 
            filename="config/googleads.yaml"
          />
          <p className="mt-4 font-semibold text-foreground">Edit config/.env:</p>
          <CodeBlock 
            code={`GAM_NETWORK_CODE=your_network_code\n\n# AWS Bedrock (AI Chat)\nAWS_BEARER_TOKEN_BEDROCK=your_bedrock_api_key_here\nAWS_REGION=us-east-1\nBEDROCK_MODEL_ID=us.anthropic.claude-haiku-4-5-20251001-v1:0\n\n# Email Notifications (optional)\nGMAIL_SENDER_EMAIL=your_email@gmail.com\nGMAIL_APP_PASSWORD=your_app_password`}
            language="env" 
            filename="config/.env"
          />
        </StepCard>

        <StepCard number={3} title="Set up AWS Bedrock">
          <ol className="space-y-2 mt-4 ml-4 list-decimal text-muted-foreground">
            <li>Log in to the <strong>AWS Console</strong> and go to <strong>Bedrock</strong>.</li>
            <li>In the left menu click <strong>Model access</strong> → <strong>Manage model access</strong>.</li>
            <li>Enable <strong>Anthropic Claude Haiku 4.5</strong>.</li>
            <li>Generate a <strong>Bedrock API Key</strong> from the Bedrock console.</li>
            <li>Paste it as <code>AWS_BEARER_TOKEN_BEDROCK</code> in your <code>.env</code>.</li>
          </ol>
        </StepCard>

        <StepCard number={4} title="Start the Backend Server">
          <p>Run the Starlette MCP server using Uvicorn.</p>
          <CodeBlock 
            code="python -m uvicorn mcp_server.server:starlette_app --reload" 
            language="bash" 
          />
          <p>The backend API will run on <code>http://localhost:8000</code>.</p>
        </StepCard>

        <StepCard number={5} title="Run the Dashboard">
          <p>In a new terminal window, start the Next.js frontend.</p>
          <CodeBlock 
            code={`cd dashboard\nnpm install\nnpm run dev`}
            language="bash" 
          />
          <p>The dashboard will open at <code>http://localhost:3000</code>.</p>
        </StepCard>
      </div>
    </div>
  );
}
