"use client";

import { CodeBlock } from "./CodeBlock";

interface ApiEndpointProps {
  method: "GET" | "POST" | "PUT" | "DELETE";
  path: string;
  description: string;
  request?: string;
  response?: string;
}

export function ApiEndpoint({ method, path, description, request, response }: ApiEndpointProps) {
  const methodColors = {
    GET: "bg-blue-500/10 text-blue-500 border-blue-500/20",
    POST: "bg-green-500/10 text-green-500 border-green-500/20",
    PUT: "bg-yellow-500/10 text-yellow-500 border-yellow-500/20",
    DELETE: "bg-red-500/10 text-red-500 border-red-500/20",
  };

  return (
    <div className="my-8 overflow-hidden rounded-xl border border-border bg-card shadow-sm">
      <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4 border-b border-border p-4 bg-muted/20">
        <span className={`rounded-md border px-2.5 py-1 text-xs font-bold tracking-widest ${methodColors[method]}`}>
          {method}
        </span>
        <code className="text-sm font-mono font-medium text-foreground">{path}</code>
      </div>
      
      <div className="p-4 sm:p-6">
        <p className="text-muted-foreground m-0 mb-6">{description}</p>
        
        {request && (
          <div className="mb-6">
            <h4 className="text-sm font-semibold uppercase tracking-wider text-foreground mb-2">Request Body</h4>
            <CodeBlock code={request} language="json" />
          </div>
        )}
        
        {response && (
          <div>
            <h4 className="text-sm font-semibold uppercase tracking-wider text-foreground mb-2">Example Response</h4>
            <CodeBlock code={response} language="json" />
          </div>
        )}
      </div>
    </div>
  );
}
