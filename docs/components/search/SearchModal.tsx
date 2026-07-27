"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { Search, X, FileText, ChevronRight } from "lucide-react";
import Fuse from "fuse.js";
import { searchData, SearchRecord } from "@/lib/search-data";

export function SearchModal({
  isOpen,
  onClose,
}: {
  isOpen: boolean;
  onClose: () => void;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchRecord[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();

  // Initialize Fuse
  const fuse = new Fuse(searchData, {
    keys: ["title", "content", "category"],
    threshold: 0.3,
    includeScore: true,
  });

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 100);
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "auto";
      setQuery("");
      setSelectedIndex(0);
    }
    return () => {
      document.body.style.overflow = "auto";
    };
  }, [isOpen]);

  useEffect(() => {
    if (query.trim() === "") {
      setResults([]);
      return;
    }
    const searchResults = fuse.search(query).map((res) => res.item);
    setResults(searchResults.slice(0, 5));
    setSelectedIndex(0);
  }, [query]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!isOpen) {
        if ((e.metaKey || e.ctrlKey) && e.key === "k") {
          e.preventDefault();
          // Open handled globally, this is fallback
        }
        return;
      }

      if (e.key === "Escape") {
        onClose();
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((prev) => (prev + 1) % Math.max(1, results.length));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((prev) =>
          prev === 0 ? Math.max(0, results.length - 1) : prev - 1
        );
      } else if (e.key === "Enter" && results.length > 0) {
        e.preventDefault();
        handleSelect(results[selectedIndex]);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, results, selectedIndex, onClose]);

  const handleSelect = (item: SearchRecord) => {
    router.push(item.href);
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-start justify-center pt-16 sm:pt-24">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-background/80 backdrop-blur-sm transition-opacity"
        onClick={onClose}
      />
      
      {/* Modal */}
      <div className="relative w-full max-w-2xl transform overflow-hidden rounded-xl border border-border bg-card shadow-2xl transition-all sm:mx-4">
        <div className="flex items-center border-b border-border px-4 py-3">
          <Search className="h-5 w-5 text-muted-foreground mr-3" />
          <input
            ref={inputRef}
            className="flex-1 bg-transparent text-base outline-none placeholder:text-muted-foreground"
            placeholder="Search documentation..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <button
            onClick={onClose}
            className="rounded-md p-1 hover:bg-secondary text-muted-foreground hover:text-foreground transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="max-h-[60vh] overflow-y-auto py-2">
          {query.trim() === "" ? (
            <div className="p-6 text-center text-sm text-muted-foreground">
              Type to start searching...
            </div>
          ) : results.length === 0 ? (
            <div className="p-6 text-center text-sm text-muted-foreground">
              No results found for "{query}".
            </div>
          ) : (
            <ul className="px-2">
              {results.map((item, index) => (
                <li key={item.id}>
                  <button
                    onClick={() => handleSelect(item)}
                    className={`flex w-full items-center justify-between rounded-lg px-4 py-3 text-left transition-colors ${
                      index === selectedIndex
                        ? "bg-primary/10 text-primary"
                        : "hover:bg-secondary"
                    }`}
                    onMouseEnter={() => setSelectedIndex(index)}
                  >
                    <div className="flex items-center gap-3">
                      <div className={`rounded-md p-2 ${
                        index === selectedIndex ? "bg-primary/20 text-primary" : "bg-muted text-muted-foreground"
                      }`}>
                        <FileText className="h-4 w-4" />
                      </div>
                      <div>
                        <div className="font-medium">{item.title}</div>
                        <div className="text-xs text-muted-foreground mt-0.5 line-clamp-1">
                          {item.content}
                        </div>
                      </div>
                    </div>
                    <ChevronRight className={`h-4 w-4 ${
                      index === selectedIndex ? "opacity-100" : "opacity-0"
                    }`} />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        
        <div className="flex items-center justify-between border-t border-border bg-muted/50 px-4 py-2.5 text-xs text-muted-foreground">
          <div className="flex items-center gap-4">
            <span className="flex items-center gap-1">
              <kbd className="rounded border bg-background px-1.5 font-mono text-[10px]">↑</kbd>
              <kbd className="rounded border bg-background px-1.5 font-mono text-[10px]">↓</kbd>
              <span>to navigate</span>
            </span>
            <span className="flex items-center gap-1">
              <kbd className="rounded border bg-background px-1.5 font-mono text-[10px]">↵</kbd>
              <span>to select</span>
            </span>
          </div>
          <span className="flex items-center gap-1">
            <kbd className="rounded border bg-background px-1.5 font-mono text-[10px]">esc</kbd>
            <span>to close</span>
          </span>
        </div>
      </div>
    </div>
  );
}
