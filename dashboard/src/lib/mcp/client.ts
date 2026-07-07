import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { SSEClientTransport } from "@modelcontextprotocol/sdk/client/sse.js";
import * as EventSourcePolyfill from "eventsource"; // Polyfill for Node.js if needed

// In Node.js 18+, EventSource might be natively available, but we import it just in case
if (typeof global.EventSource === "undefined") {
    // @ts-ignore
    global.EventSource = EventSourcePolyfill.default || EventSourcePolyfill;
}

const MCP_SERVER_URL = process.env.MCP_SERVER_URL || "http://127.0.0.1:8000/sse";

let mcpClient: Client | null = null;

export async function getMcpClient(): Promise<Client> {
  if (mcpClient) {
    return mcpClient;
  }

  const transport = new SSEClientTransport(new URL(MCP_SERVER_URL));
  const client = new Client({
    name: "nextjs-dashboard",
    version: "1.0.0"
  }, {
    capabilities: {}
  });

  try {
    await client.connect(transport);
    console.log("Connected to MCP Server via SSE at", MCP_SERVER_URL);
    mcpClient = client;
  } catch (error) {
    console.error("Failed to connect to MCP Server:", error);
    throw error;
  }

  return mcpClient;
}

export async function callMcpTool(name: string, args: Record<string, any>) {
  const client = await getMcpClient();
  const response = await client.callTool({
    name,
    arguments: args,
  }, { timeout: 300000 }); // 5 minute timeout for historical reports
  
  if (response.isError) {
    throw new Error(`MCP Tool Error: ${response.content[0]?.text}`);
  }

  try {
    // @ts-ignore
    const parsed = JSON.parse(response.content[0]?.text || "{}");
    if (parsed.status === "error") {
      throw new Error(parsed.error);
    }
    return parsed;
  } catch (e: any) {
    if (e.message.includes("Unexpected token")) {
      // @ts-ignore
      return { raw: response.content[0]?.text };
    }
    throw e;
  }
}
