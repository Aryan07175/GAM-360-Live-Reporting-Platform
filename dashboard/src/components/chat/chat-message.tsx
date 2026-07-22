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
type InlineSegment =
  | { bold: true; text: string }
  | { italic: true; text: string }
  | { code: true; text: string }
  | { text: string };

function parseInline(raw: string): InlineSegment[] {
  const segments: InlineSegment[] = [];
  const pattern = /(\*\*(.+?)\*\*|\*([^*]+)\*|`([^`]+)`)/g;
  let last = 0;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(raw)) !== null) {
    if (match.index > last) segments.push({ text: raw.slice(last, match.index) });
    if (match[0].startsWith("**")) {
      segments.push({ bold: true, text: match[2] });
    } else if (match[0].startsWith("*")) {
      segments.push({ italic: true, text: match[3] });
    } else {
      segments.push({ code: true, text: match[4] });
    }
    last = match.index + match[0].length;
  }
  if (last < raw.length) segments.push({ text: raw.slice(last) });
  return segments;
}

function renderInline(raw: string, key: string | number) {
  return parseInline(raw).map((seg, i) => {
    const k = `${key}-${i}`;
    if ("bold" in seg)
      return <strong key={k} className="font-semibold text-foreground dark:text-white">{seg.text}</strong>;
    if ("italic" in seg)
      return <em key={k} className="italic">{seg.text}</em>;
    if ("code" in seg)
      return (
        <code key={k} className="font-mono text-xs bg-foreground/10 dark:bg-white/10 px-1 py-0.5 rounded">
          {seg.text}
        </code>
      );
    return <span key={k}>{seg.text}</span>;
  });
}

// ─── Table Renderer ─────────────────────────────────────────────────────────────
function isTableLine(line: string) {
  return line.trim().startsWith("|") && line.trim().endsWith("|");
}
function isSeparatorLine(line: string) {
  return /^\|[\s\-:|]+\|[\s\-:|]*\|/.test(line.trim());
}
function parseTableLine(line: string): string[] {
  return line
    .trim()
    .replace(/^\||\|$/g, "")
    .split("|")
    .map((c) => c.trim());
}

function TableBlock({ lines, bIdx }: { lines: string[]; bIdx: number }) {
  const nonSep = lines.filter((l) => !isSeparatorLine(l));
  const [header, ...rows] = nonSep;
  const cols = header ? parseTableLine(header) : [];

  return (
    <div key={bIdx} className={cn("overflow-x-auto rounded-lg border border-border", bIdx > 0 && "mt-3")}>
      <table className="w-full text-xs border-collapse">
        <thead>
          <tr className="bg-muted/60">
            {cols.map((c, ci) => (
              <th
                key={ci}
                className="px-3 py-2 text-left font-semibold text-foreground border-b border-border whitespace-nowrap"
              >
                {renderInline(c, `th-${bIdx}-${ci}`)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, ri) => {
            const cells = parseTableLine(row);
            return (
              <tr key={ri} className={cn("border-b border-border/50 last:border-0", ri % 2 === 1 && "bg-muted/20")}>
                {cells.map((cell, ci) => (
                  <td key={ci} className="px-3 py-2 text-muted-foreground break-words">
                    {renderInline(cell, `td-${bIdx}-${ri}-${ci}`)}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ─── Full Markdown Renderer ────────────────────────────────────────────────────
function MarkdownContent({ content }: { content: string }) {
  if (!content) return null;

  const rawLines = content.split("\n");
  const nodes: React.ReactNode[] = [];
  let i = 0;

  while (i < rawLines.length) {
    const line = rawLines[i];

    // ── Horizontal rule ──
    if (/^[-*_]{3,}$/.test(line.trim())) {
      nodes.push(<hr key={i} className="border-border my-2" />);
      i++;
      continue;
    }

    // ── Headings ──
    const h3 = line.match(/^###\s+(.+)/);
    const h2 = line.match(/^##\s+(.+)/);
    const h1 = line.match(/^#\s+(.+)/);
    if (h3) {
      nodes.push(
        <h3 key={i} className="text-sm font-semibold mt-3 mb-1 text-foreground">
          {renderInline(h3[1], i)}
        </h3>
      );
      i++;
      continue;
    }
    if (h2) {
      nodes.push(
        <h2 key={i} className="text-sm font-bold mt-4 mb-1 text-foreground border-b border-border/50 pb-1">
          {renderInline(h2[1], i)}
        </h2>
      );
      i++;
      continue;
    }
    if (h1) {
      nodes.push(
        <h1 key={i} className="text-base font-bold mt-3 mb-1 text-foreground">
          {renderInline(h1[1], i)}
        </h1>
      );
      i++;
      continue;
    }

    // ── Table block ──
    if (isTableLine(line)) {
      const tableLines: string[] = [];
      while (i < rawLines.length && (isTableLine(rawLines[i]) || isSeparatorLine(rawLines[i]))) {
        tableLines.push(rawLines[i]);
        i++;
      }
      nodes.push(<TableBlock key={`table-${i}`} lines={tableLines} bIdx={nodes.length} />);
      continue;
    }

    // ── Bullet list ──
    if (/^[\-\*]\s/.test(line.trimStart())) {
      const items: string[] = [];
      while (i < rawLines.length && /^[\-\*]\s/.test(rawLines[i].trimStart())) {
        items.push(rawLines[i].replace(/^[\-\*]\s+/, ""));
        i++;
      }
      nodes.push(
        <ul key={`ul-${i}`} className="list-disc list-inside space-y-0.5 mt-1">
          {items.map((item, idx) => (
            <li key={idx} className="leading-relaxed break-words text-muted-foreground">
              {renderInline(item, `li-${idx}`)}
            </li>
          ))}
        </ul>
      );
      continue;
    }

    // ── Numbered list ──
    if (/^\d+\.\s/.test(line.trimStart())) {
      const items: string[] = [];
      while (i < rawLines.length && /^\d+\.\s/.test(rawLines[i].trimStart())) {
        items.push(rawLines[i].replace(/^\d+\.\s+/, ""));
        i++;
      }
      nodes.push(
        <ol key={`ol-${i}`} className="list-decimal list-inside space-y-0.5 mt-1">
          {items.map((item, idx) => (
            <li key={idx} className="leading-relaxed break-words text-muted-foreground">
              {renderInline(item, `oli-${idx}`)}
            </li>
          ))}
        </ol>
      );
      continue;
    }

    // ── Blockquote ──
    if (line.trimStart().startsWith("> ")) {
      const text = line.replace(/^>\s?/, "");
      nodes.push(
        <blockquote key={i} className="border-l-2 border-indigo-400 pl-3 italic text-muted-foreground mt-1">
          {renderInline(text, i)}
        </blockquote>
      );
      i++;
      continue;
    }

    // ── Empty line: spacer ──
    if (line.trim() === "") {
      const last = nodes[nodes.length - 1];
      if (last && (last as React.ReactElement)?.type !== "div") {
        nodes.push(<div key={`sp-${i}`} className="h-1" />);
      }
      i++;
      continue;
    }

    // ── Paragraph ──
    nodes.push(
      <p key={i} className="leading-relaxed break-words [overflow-wrap:anywhere]">
        {renderInline(line, i)}
      </p>
    );
    i++;
  }

  return <>{nodes}</>;
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
          <div className="leading-relaxed break-words [overflow-wrap:anywhere] space-y-0.5">
            <MarkdownContent content={content} />
            {isStreaming && !content && (
              <span className="inline-flex items-center gap-1 h-3">
                <span className="animate-bounce w-1.5 h-1.5 bg-muted-foreground/60 rounded-full" />
                <span className="animate-bounce w-1.5 h-1.5 bg-muted-foreground/60 rounded-full" style={{ animationDelay: "0.1s" }} />
                <span className="animate-bounce w-1.5 h-1.5 bg-muted-foreground/60 rounded-full" style={{ animationDelay: "0.2s" }} />
              </span>
            )}
            {isStreaming && content && (
              <span className="inline-block w-0.5 h-3.5 bg-indigo-500 ml-0.5 animate-pulse align-middle" />
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
