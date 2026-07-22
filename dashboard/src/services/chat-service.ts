import type { ChatMessage, ChatDateRange } from "@/types";

const MCP_BASE_URL = process.env.NEXT_PUBLIC_MCP_SERVER_URL || process.env.MCP_SERVER_URL || "https://gam-360-live-reporting-platform.onrender.com";

export type StreamEvent = 
  | { type: 'token'; content: string }
  | { type: 'done' }
  | { type: 'error'; content: string };

export async function* streamChat(
  sessionId: string,
  message: string,
  history: ChatMessage[],
  dateRange: ChatDateRange,
  signal?: AbortSignal
): AsyncGenerator<StreamEvent, void, unknown> {
  try {
    const chatUrl = `${MCP_BASE_URL}/api/chat`;
    console.log(`[Chat] → POST ${chatUrl}`);
    const response = await fetch(chatUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        session_id: sessionId,
        message,
        history,
        date_range: dateRange,
      }),
      signal,
    });

    console.log(`[Chat] ← ${response.status} ${response.statusText}`);

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.error || `Chat API error: ${response.status} ${response.statusText}`);
    }

    if (!response.body) {
      throw new Error("No response body");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      
      // Keep the last partial line in the buffer
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const dataStr = line.slice(6);
          if (!dataStr.trim()) continue;
          
          try {
            const event = JSON.parse(dataStr) as StreamEvent;
            yield event;
            if (event.type === 'error' || event.type === 'done') {
              return;
            }
          } catch (e) {
            console.error("Failed to parse SSE event:", dataStr, e);
          }
        }
      }
    }
  } catch (error: any) {
    if (error.name === "AbortError") {
      yield { type: 'error', content: "Request was cancelled" };
    } else {
      console.error("streamChat failed:", error);
      yield { type: 'error', content: error.message || "An unknown error occurred" };
    }
  }
}
