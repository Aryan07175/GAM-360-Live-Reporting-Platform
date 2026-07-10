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

// Function to format numbers and currencies in bold
function formatMessageContent(content: string) {
  if (!content) return null;
  
  // Split by newlines first to handle paragraphs
  const paragraphs = content.split('\n');
  
  return paragraphs.map((paragraph, pIdx) => {
    if (!paragraph) return <br key={pIdx} />;
    
    // Regex for matching numbers: $XX,XXX.XX, XX.XX%, X,XXX
    const regex = /(\$?\d{1,3}(?:,\d{3})*(?:\.\d+)?%?)/g;
    const parts = paragraph.split(regex);
    
    return (
      <p key={pIdx} className={pIdx > 0 ? "mt-2" : ""}>
        {parts.map((part, i) => {
          if (regex.test(part)) {
            return (
              <span key={i} className="font-semibold text-foreground dark:text-white bg-foreground/5 dark:bg-white/10 px-1 py-0.5 rounded text-xs mx-0.5">
                {part}
              </span>
            );
          }
          return <span key={i}>{part}</span>;
        })}
      </p>
    );
  });
}

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
          "max-w-[85%] rounded-2xl px-4 py-3 text-sm shadow-sm",
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
          <div className="leading-relaxed">
            {formatMessageContent(content)}
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
