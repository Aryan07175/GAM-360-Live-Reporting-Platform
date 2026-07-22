"use client";

import { motion } from "framer-motion";
import { User, Zap, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";

interface ChatMessageProps {
  role: "user" | "assistant";
  content: string;
  isStreaming?: boolean;
  error?: string;
  timestamp?: string;
}

// ─── Inline Markdown Renderer ─────────────────────────────────────────────────
//
// Renders a small subset of Markdown that the AI commonly produces:
//   **bold**   →  <strong>
//   `code`     →  <code>
//   - item     →  <li> inside <ul>
//   blank line →  paragraph break
//
// This is intentionally minimal — no extra libraries, no dangerouslySetInnerHTML.
// Extend the INLINE_RULES array to support more syntax if needed.

type InlineSegment = { bold: true; text: string } | { code: true; text: string } | { text: string };

function parseInline(raw: string): InlineSegment[] {
  const segments: InlineSegment[] = [];
  // Match **bold** or `code` spans
  const pattern = /(\*\*(.+?)\*\*|`([^`]+)`)/g;
  let last = 0;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(raw)) !== null) {
    if (match.index > last) {
      segments.push({ text: raw.slice(last, match.index) });
    }
    if (match[0].startsWith("**")) {
      segments.push({ bold: true, text: match[2] });
    } else {
      segments.push({ code: true, text: match[3] });
    }
    last = match.index + match[0].length;
  }

  if (last < raw.length) {
    segments.push({ text: raw.slice(last) });
  }

  return segments;
}

function renderInline(raw: string, key: string | number) {
  const segments = parseInline(raw);
  return segments.map((seg, i) => {
    const k = `${key}-${i}`;
    if ("bold" in seg) {
      return <strong key={k} className="font-semibold text-foreground dark:text-white">{seg.text}</strong>;
    }
    if ("code" in seg) {
      return (
        <code key={k} className="font-mono text-xs bg-foreground/8 dark:bg-white/10 px-1 py-0.5 rounded">
          {seg.text}
        </code>
      );
    }
    return <span key={k}>{seg.text}</span>;
  });
}

function MarkdownContent({ content }: { content: string }) {
  if (!content) return null;

  // Split into blocks by blank lines (paragraph boundaries)
  const blocks = content.split(/\n{2,}/);

  return (
    <>
      {blocks.map((block, bIdx) => {
        const lines = block.split("\n");

        // Bullet list block: every line starts with "- " or "* "
        const isList = lines.every(l => /^[\-\*]\s/.test(l.trimStart()) || l.trim() === "");
        if (isList) {
          const items = lines.filter(l => /^[\-\*]\s/.test(l.trimStart()));
          return (
            <ul key={bIdx} className={cn("list-disc list-inside space-y-0.5", bIdx > 0 && "mt-2")}>
              {items.map((item, iIdx) => (
                <li key={iIdx} className="leading-relaxed break-words [overflow-wrap:anywhere]">
                  {renderInline(item.replace(/^[\-\*]\s+/, ""), `${bIdx}-${iIdx}`)}
                </li>
              ))}
            </ul>
          );
        }

        // Plain paragraph: render each line, joining with <br> for single newlines
        return (
          <p key={bIdx} className={cn("leading-relaxed break-words [overflow-wrap:anywhere]", bIdx > 0 && "mt-2")}>
            {lines.map((line, lIdx) => (
              <span key={lIdx}>
                {renderInline(line, `${bIdx}-${lIdx}`)}
                {lIdx < lines.length - 1 && <br />}
              </span>
            ))}
          </p>
        );
      })}
    </>
  );
}

// ─── Chat Message Component ───────────────────────────────────────────────────

export function ChatMessage({ role, content, isStreaming, error }: ChatMessageProps) {
  const isUser = role === "user";

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        "flex w-full gap-3",
        isUser ? "justify-end" : "justify-start"
      )}
    >
      {!isUser && (
        <div className="flex-shrink-0 h-8 w-8 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-sm">
          <Zap className="h-4 w-4 text-white" />
        </div>
      )}

      <div
        className={cn(
          "max-w-[85%] min-w-0 overflow-hidden rounded-2xl px-4 py-3 text-sm shadow-sm",
          isUser
            ? "bg-indigo-600 text-white rounded-tr-sm"
            : "bg-card border border-border rounded-tl-sm text-card-foreground"
        )}
      >
        {error ? (
          <div className="flex items-center gap-2 text-rose-500">
            <AlertCircle className="h-4 w-4" />
            <span>{error}</span>
          </div>
        ) : (
          <div className="leading-relaxed break-words [overflow-wrap:anywhere]">
            <MarkdownContent content={content} />
            {isStreaming && (
              <span className="inline-flex items-center gap-1 ml-1 h-3">
                <span className="animate-bounce w-1 h-1 bg-current rounded-full" />
                <span className="animate-bounce w-1 h-1 bg-current rounded-full" style={{ animationDelay: "0.1s" }} />
                <span className="animate-bounce w-1 h-1 bg-current rounded-full" style={{ animationDelay: "0.2s" }} />
              </span>
            )}
          </div>
        )}
      </div>

      {isUser && (
        <div className="flex-shrink-0 h-8 w-8 rounded-full bg-indigo-500/10 flex items-center justify-center border border-indigo-500/20">
          <User className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />
        </div>
      )}
    </motion.div>
  );
}
