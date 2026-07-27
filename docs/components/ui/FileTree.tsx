"use client";

import { useState } from "react";
import { ChevronRight, ChevronDown, Folder, File, FileCode2, FileJson } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

export interface FileNode {
  name: string;
  type: "file" | "folder";
  description?: string;
  children?: FileNode[];
  icon?: "code" | "json" | "default";
}

interface FileTreeProps {
  data: FileNode[];
  defaultExpanded?: boolean;
}

export function FileTree({ data, defaultExpanded = true }: FileTreeProps) {
  return (
    <div className="rounded-xl border border-border bg-card p-4 font-mono text-sm shadow-sm my-6">
      {data.map((node, index) => (
        <FileTreeNode key={index} node={node} defaultExpanded={defaultExpanded} />
      ))}
    </div>
  );
}

function FileTreeNode({ node, depth = 0, defaultExpanded }: { node: FileNode; depth?: number; defaultExpanded: boolean }) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);
  
  const isFolder = node.type === "folder";
  
  const getFileIcon = () => {
    if (node.icon === "code") return <FileCode2 className="h-4 w-4 text-blue-400" />;
    if (node.icon === "json") return <FileJson className="h-4 w-4 text-yellow-400" />;
    return <File className="h-4 w-4 text-muted-foreground" />;
  };

  return (
    <div className="select-none">
      <div 
        className={`group flex items-center justify-between rounded-md py-1.5 px-2 hover:bg-secondary transition-colors ${isFolder ? 'cursor-pointer' : ''}`}
        style={{ paddingLeft: `${depth * 1.5 + 0.5}rem` }}
        onClick={() => isFolder && setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-2">
          {isFolder ? (
            <>
              {isExpanded ? (
                <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
              ) : (
                <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
              )}
              <Folder className="h-4 w-4 text-primary" fill="currentColor" fillOpacity={0.2} />
            </>
          ) : (
            <>
              <span className="w-3.5" />
              {getFileIcon()}
            </>
          )}
          <span className={`font-medium ${isFolder ? 'text-foreground' : 'text-muted-foreground'}`}>
            {node.name}
          </span>
        </div>
        
        {node.description && (
          <span className="hidden md:inline-flex text-xs text-muted-foreground opacity-60 group-hover:opacity-100 transition-opacity">
            {node.description}
          </span>
        )}
      </div>

      <AnimatePresence>
        {isFolder && isExpanded && node.children && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            {node.children.map((child, index) => (
              <FileTreeNode 
                key={index} 
                node={child} 
                depth={depth + 1} 
                defaultExpanded={defaultExpanded} 
              />
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
