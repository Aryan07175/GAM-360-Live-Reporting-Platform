"use client";

import { useEffect, useRef, useState } from "react";
import mermaid from "mermaid";
import { useTheme } from "next-themes";
import { Maximize2, Minimize2 } from "lucide-react";

interface DiagramCardProps {
  chart: string;
  title?: string;
  description?: string;
}

export function DiagramCard({ chart, title, description }: DiagramCardProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [svg, setSvg] = useState<string>("");
  const { resolvedTheme } = useTheme();
  const [isExpanded, setIsExpanded] = useState(false);

  useEffect(() => {
    mermaid.initialize({
      startOnLoad: false,
      theme: resolvedTheme === "dark" ? "dark" : "default",
      fontFamily: "inherit",
      securityLevel: "loose",
    });

    const renderDiagram = async () => {
      if (ref.current) {
        try {
          const id = `mermaid-${Math.random().toString(36).substring(2, 9)}`;
          const { svg: svgData } = await mermaid.render(id, chart);
          setSvg(svgData);
        } catch (error) {
          console.error("Failed to render mermaid diagram", error);
        }
      }
    };

    renderDiagram();
  }, [chart, resolvedTheme]);

  const DiagramContent = () => (
    <div className={`overflow-hidden rounded-xl border border-border bg-card shadow-sm ${isExpanded ? 'h-full flex flex-col' : 'my-8'}`}>
      {(title || description) && (
        <div className="flex items-start justify-between border-b border-border/50 bg-muted/30 p-4">
          <div>
            {title && <h3 className="font-semibold text-foreground m-0 text-lg">{title}</h3>}
            {description && <p className="text-sm text-muted-foreground m-0 mt-1">{description}</p>}
          </div>
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="rounded p-1.5 text-muted-foreground hover:bg-secondary hover:text-foreground transition-colors hidden md:block"
          >
            {isExpanded ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
          </button>
        </div>
      )}
      <div 
        className={`flex justify-center p-6 bg-gradient-to-b from-background to-muted/20 ${isExpanded ? 'flex-1 overflow-auto items-center' : 'overflow-x-auto'}`}
        ref={ref}
      >
        {svg ? (
          <div dangerouslySetInnerHTML={{ __html: svg }} className="max-w-full" />
        ) : (
          <div className="h-32 flex items-center justify-center text-muted-foreground">
            Rendering diagram...
          </div>
        )}
      </div>
    </div>
  );

  if (isExpanded) {
    return (
      <div className="fixed inset-0 z-[100] bg-background/95 backdrop-blur-sm p-4 md:p-12 flex items-center justify-center">
        <div className="w-full h-full max-w-6xl max-h-[90vh]">
          <DiagramContent />
        </div>
      </div>
    );
  }

  return <DiagramContent />;
}
