import type { ChatMessage, ChatDateRange } from "@/types";

const MCP_BASE_URL = process.env.NEXT_PUBLIC_MCP_SERVER_URL || process.env.MCP_SERVER_URL || "https://gam-360-live-reporting-platform.onrender.com";

/** How many times to retry on network-level failures (backend cold-start etc.) */
const MAX_RETRIES = 3;
const RETRY_DELAY_MS = 4000;

export type StreamEvent = 
  | { type: 'token'; content: string }
  | { type: 'done' }
  | { type: 'error'; content: string }
  | { type: 'retrying'; attempt: number; max: number };

/** Translate raw fetch errors into user-friendly messages. */
function friendlyError(err: any): string {
  const msg: string = err?.message || "";
  if (
    msg === "Failed to fetch" ||
    msg.includes("NetworkError") ||
    msg.includes("ERR_CONNECTION_REFUSED") ||
    msg.includes("ERR_NAME_NOT_RESOLVED") ||
    msg.includes("net::")
  ) {
    return (
      "Cannot reach the backend server. " +
      "It may be starting up (Render cold-start takes ~30 s). " +
      "Please wait a moment and try again."
    );
  }
  if (msg.includes("timeout") || msg.includes("TimeoutError")) {
    return "The request timed out. The backend may be under load — please retry in a few seconds.";
  }
  return msg || "An unexpected error occurred. Please try again.";
}

export async function* streamChat(
  sessionId: string,
  message: string,
  history: ChatMessage[],
  dateRange: ChatDateRange,
  signal?: AbortSignal
): AsyncGenerator<StreamEvent, void, unknown> {
  const chatUrl = `${MCP_BASE_URL}/api/chat`;

  for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
    try {
      console.log(`[Chat] → POST ${chatUrl} (attempt ${attempt}/${MAX_RETRIES})`);

      const response = await fetch(chatUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
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
        // 4xx = client error, never retry
        if (response.status < 500) {
          yield { type: 'error', content: err.error || `Chat API error: ${response.status} ${response.statusText}` };
          return;
        }
        // 5xx — may be transient; retry if attempts remain
        throw new Error(err.error || `Server error: ${response.status}`);
      }

      if (!response.body) throw new Error("No response body");

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const dataStr = line.slice(6);
          if (!dataStr.trim()) continue;
          try {
            const event = JSON.parse(dataStr) as StreamEvent;
            yield event;
            if (event.type === "error" || event.type === "done") return;
          } catch (e) {
            console.error("[Chat] Failed to parse SSE event:", dataStr, e);
          }
        }
      }
      return; // success

    } catch (err: any) {
      if (err?.name === "AbortError") {
        yield { type: "error", content: "Request was cancelled" };
        return;
      }

      const isNetworkError =
        err?.message === "Failed to fetch" ||
        err?.message?.includes("NetworkError") ||
        err?.message?.includes("net::");

      if (attempt < MAX_RETRIES && isNetworkError) {
        // Emit a retrying notice so the UI can show progress
        yield { type: "retrying", attempt, max: MAX_RETRIES };
        console.warn(`[Chat] Network error on attempt ${attempt}. Retrying in ${RETRY_DELAY_MS}ms...`, err);
        await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY_MS));
        continue;
      }

      console.error("[Chat] streamChat failed:", err);
      yield { type: "error", content: friendlyError(err) };
      return;
    }
  }
}
