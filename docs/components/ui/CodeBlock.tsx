"use client";

import { useState, useEffect } from "react";
import { Check, Copy } from "lucide-react";
import { codeToHtml } from "shiki";

interface CodeBlockProps {
  code: string;
  language?: string;
  filename?: string;
  className?: string;
}

export function CodeBlock({ code, language = "typescript", filename, className = "" }: CodeBlockProps) {
  const [html, setHtml] = useState<string>("");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    async function highlight() {
      const result = await codeToHtml(code, {
        lang: language,
        theme: "vitesse-dark",
      });
      setHtml(result);
    }
    highlight();
  }, [code, language]);

  const copyToClipboard = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={`my-6 overflow-hidden rounded-xl border border-border bg-[#121212] ${className}`}>
      <div className="flex items-center justify-between border-b border-border/50 bg-[#1e1e1e] px-4 py-2">
        <div className="flex items-center gap-2">
          <div className="flex space-x-1.5">
            <div className="h-3 w-3 rounded-full bg-destructive/80"></div>
            <div className="h-3 w-3 rounded-full bg-yellow-500/80"></div>
            <div className="h-3 w-3 rounded-full bg-green-500/80"></div>
          </div>
          {filename && (
            <span className="ml-2 text-xs font-medium text-muted-foreground font-mono">
              {filename}
            </span>
          )}
        </div>
        <button
          onClick={copyToClipboard}
          className="rounded p-1.5 text-muted-foreground hover:bg-white/10 hover:text-foreground transition-colors"
          aria-label="Copy code"
        >
          {copied ? <Check className="h-4 w-4 text-green-500" /> : <Copy className="h-4 w-4" />}
        </button>
      </div>
      <div className="overflow-x-auto p-4 text-sm font-mono leading-relaxed">
        {html ? (
          <div dangerouslySetInnerHTML={{ __html: html }} className="code-block" />
        ) : (
          <pre className="opacity-0"><code className="code-block">{code}</code></pre>
        )}
      </div>
    </div>
  );
}
