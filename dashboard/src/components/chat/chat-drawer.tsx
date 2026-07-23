"use client";

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  MessageCircle,
  X,
  Zap,
  Send,
  RotateCcw,
  BarChart2,
  Globe,
  TrendingUp,
  AlertTriangle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ChatMessage } from "./chat-message";
import { streamChat } from "@/services/chat-service";
import type { ChatMessage as ChatMessageType } from "@/types";
import { useLiveReport } from "@/contexts/DateContext";

// ─── Suggestion categories reflecting all active AI policies ─────────────────
const SUGGESTION_GROUPS = [
  {
    label: "Quick Metrics",
    icon: BarChart2,
    color: "text-indigo-500",
    items: [
      "What is the fill rate?",
      "CTR?",
      "Total impressions yesterday",
      "Revenue today",
    ],
  },
  {
    label: "Inventory Status",
    icon: Globe,
    color: "text-emerald-500",
    items: [
      "How many websites are active?",
      "Which apps served ads yesterday?",
      "List all configured websites and apps",
      "Show full network inventory status",
    ],
  },
  {
    label: "Analysis",
    icon: TrendingUp,
    color: "text-violet-500",
    items: [
      "Summarize the report",
      "Which app has the highest revenue?",
      "Give insights on eCPM performance",
      "Analyze top apps this month",
    ],
  },
  {
    label: "Ad Requests",
    icon: AlertTriangle,
    color: "text-amber-500",
    items: [
      "Are Ad Requests available in the report?",
      "Why are Ad Requests showing zero?",
      "Show responses served by app",
    ],
  },
];

// Flat list for the compact default chips (first item from each group)
const DEFAULT_CHIPS = SUGGESTION_GROUPS.map((g) => g.items[0]);

// Global event to open chat from sidebar
export const OPEN_CHAT_EVENT = "open-gam-chat";

export function ChatDrawer() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessageType[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [activeGroup, setActiveGroup] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const { startDate, endDate, demandChannel } = useLiveReport();
  const sessionId = `${startDate}_${endDate}_${demandChannel}`;

  // Reset chat context when date range changes
  useEffect(() => {
    if (messages.length > 0) {
      setMessages([]);
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      setIsStreaming(false);
    }
  }, [sessionId]);

  // Listen for global open event
  useEffect(() => {
    const handleOpen = () => setIsOpen(true);
    window.addEventListener(OPEN_CHAT_EVENT, handleOpen);
    return () => window.removeEventListener(OPEN_CHAT_EVENT, handleOpen);
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isStreaming]);

  const handleSend = async (text: string) => {
    if (!text.trim() || isStreaming) return;
    setActiveGroup(null);

    const userMessage: ChatMessageType = {
      id: Date.now().toString(),
      role: "user",
      content: text,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsStreaming(true);

    const assistantId = (Date.now() + 1).toString();
    setMessages((prev) => [
      ...prev,
      {
        id: assistantId,
        role: "assistant",
        content: "",
        timestamp: new Date().toISOString(),
        isStreaming: true,
      },
    ]);

    abortControllerRef.current = new AbortController();

    try {
      const stream = streamChat(
        sessionId,
        text,
        messages,
        { startDate, endDate, demandChannel },
        abortControllerRef.current.signal
      );

      for await (const event of stream) {
        if (event.type === "token") {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, content: m.content + event.content }
                : m
            )
          );
        } else if (event.type === "error") {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, error: event.content, isStreaming: false }
                : m
            )
          );
        }
      }
    } catch {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? { ...m, error: "An unexpected error occurred.", isStreaming: false }
            : m
        )
      );
    } finally {
      setIsStreaming(false);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId ? { ...m, isStreaming: false } : m
        )
      );
    }
  };

  const retryMessage = () => {
    const lastUser = [...messages].reverse().find((m) => m.role === "user");
    if (lastUser) {
      const newHistory = messages.slice(0, -2);
      setMessages(newHistory);
      handleSend(lastUser.content);
    }
  };

  // Which suggestions to show — expanded group or default chips
  const visibleGroup = activeGroup
    ? SUGGESTION_GROUPS.find((g) => g.label === activeGroup)
    : null;

  return (
    <>
      {/* Floating Action Button */}
      <AnimatePresence>
        {!isOpen && (
          <motion.div
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0, opacity: 0 }}
            className="fixed bottom-6 right-6 z-50"
          >
            <Button
              size="lg"
              className="h-14 w-14 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 shadow-lg hover:shadow-xl hover:scale-105 transition-all text-white p-0 relative"
              onClick={() => setIsOpen(true)}
            >
              <MessageCircle className="h-6 w-6" />
              <span className="absolute -top-1 -right-1 h-3 w-3 rounded-full bg-emerald-500 border-2 border-background" />
            </Button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Drawer Overlay */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-background/40 backdrop-blur-sm z-50 flex justify-end"
            onClick={() => setIsOpen(false)}
          >
            {/* Drawer Panel */}
            <motion.div
              initial={{ x: "100%" }}
              animate={{ x: 0 }}
              exit={{ x: "100%" }}
              transition={{ type: "spring", damping: 25, stiffness: 200 }}
              className="w-full max-w-[440px] bg-background border-l shadow-2xl h-full flex flex-col"
              onClick={(e) => e.stopPropagation()}
            >
              {/* Header */}
              <div className="flex items-center justify-between p-4 border-b bg-card">
                <div className="flex items-center gap-3">
                  <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-sm">
                    <Zap className="h-4 w-4 text-white" />
                  </div>
                  <div>
                    <h2 className="text-sm font-semibold tracking-tight">Ask GAM 360</h2>
                    <div className="flex items-center gap-1.5 mt-0.5">
                      <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                      <span className="text-[10px] text-muted-foreground font-medium">LIVE</span>
                      <span className="text-[10px] text-muted-foreground mx-1">•</span>
                      <span className="text-[10px] text-muted-foreground truncate max-w-[140px]">
                        {startDate === endDate ? startDate : `${startDate} to ${endDate}`}
                      </span>
                    </div>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 rounded-full text-muted-foreground hover:bg-muted"
                  onClick={() => setIsOpen(false)}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>

              {/* Messages Area */}
              <div className="flex-1 overflow-y-auto p-4 space-y-6 bg-muted/10">
                {messages.length === 0 ? (
                  <div className="h-full flex flex-col items-center justify-center text-center px-2">
                    <div className="h-12 w-12 rounded-2xl bg-indigo-500/10 flex items-center justify-center mb-4">
                      <MessageCircle className="h-6 w-6 text-indigo-600 dark:text-indigo-400" />
                    </div>
                    <h3 className="text-base font-semibold mb-1">How can I help you?</h3>
                    <p className="text-xs text-muted-foreground mb-5 max-w-[300px]">
                      Ask a single metric for a quick answer, or say&nbsp;
                      <span className="font-medium text-foreground">"Summarize the report"</span>
                      &nbsp;for a full executive summary.
                    </p>

                    {/* Category tabs */}
                    <div className="flex flex-wrap justify-center gap-2 mb-4 w-full">
                      {SUGGESTION_GROUPS.map((group) => {
                        const Icon = group.icon;
                        const isActive = activeGroup === group.label;
                        return (
                          <button
                            key={group.label}
                            onClick={() =>
                              setActiveGroup(isActive ? null : group.label)
                            }
                            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs font-medium transition-all ${
                              isActive
                                ? "bg-indigo-600 border-indigo-600 text-white shadow-sm"
                                : "bg-card border-border text-muted-foreground hover:border-indigo-400/50 hover:text-foreground"
                            }`}
                          >
                            <Icon className={`h-3 w-3 ${isActive ? "text-white" : group.color}`} />
                            {group.label}
                          </button>
                        );
                      })}
                    </div>

                    {/* Suggestion chips */}
                    <div className="flex flex-col w-full gap-2">
                      <AnimatePresence mode="wait">
                        {visibleGroup ? (
                          <motion.div
                            key={visibleGroup.label}
                            initial={{ opacity: 0, y: 6 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -6 }}
                            className="flex flex-col gap-2"
                          >
                            {visibleGroup.items.map((suggestion, i) => (
                              <button
                                key={i}
                                onClick={() => handleSend(suggestion)}
                                className="text-left px-4 py-2.5 rounded-lg border bg-card hover:bg-muted/50 hover:border-indigo-500/30 text-sm transition-all text-muted-foreground hover:text-foreground shadow-sm"
                              >
                                {suggestion}
                              </button>
                            ))}
                          </motion.div>
                        ) : (
                          <motion.div
                            key="default"
                            initial={{ opacity: 0, y: 6 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -6 }}
                            className="flex flex-col gap-2"
                          >
                            {DEFAULT_CHIPS.map((suggestion, i) => (
                              <button
                                key={i}
                                onClick={() => handleSend(suggestion)}
                                className="text-left px-4 py-2.5 rounded-lg border bg-card hover:bg-muted/50 hover:border-indigo-500/30 text-sm transition-all text-muted-foreground hover:text-foreground shadow-sm"
                              >
                                {suggestion}
                              </button>
                            ))}
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                  </div>
                ) : (
                  <>
                    {messages.map((msg) => (
                      <ChatMessage
                        key={msg.id}
                        role={msg.role}
                        content={msg.content}
                        isStreaming={msg.isStreaming}
                        error={msg.error}
                      />
                    ))}
                    {messages[messages.length - 1]?.error && (
                      <div className="flex justify-center">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={retryMessage}
                          className="gap-2 text-xs h-8"
                        >
                          <RotateCcw className="h-3 w-3" /> Retry Last Message
                        </Button>
                      </div>
                    )}
                    <div ref={messagesEndRef} className="h-1" />
                  </>
                )}
              </div>

              {/* Input Area */}
              <div className="p-4 bg-background border-t">
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    handleSend(input);
                  }}
                  className="relative flex items-end gap-2 bg-muted/50 rounded-xl border focus-within:ring-1 focus-within:ring-indigo-500/50 focus-within:border-indigo-500/50 transition-all p-2"
                >
                  <textarea
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        handleSend(input);
                      }
                    }}
                    placeholder="Ask about metrics, inventory, or say 'Summarize the report'…"
                    className="flex-1 max-h-32 min-h-[40px] resize-none bg-transparent border-0 focus:ring-0 text-sm px-2 py-2.5 scrollbar-thin placeholder:text-muted-foreground"
                    disabled={isStreaming}
                    rows={1}
                  />
                  <Button
                    type="submit"
                    size="icon"
                    disabled={!input.trim() || isStreaming}
                    className="h-9 w-9 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white shrink-0 shadow-sm"
                  >
                    <Send className="h-4 w-4" />
                  </Button>
                </form>
                <div className="text-center mt-2">
                  <span className="text-[10px] text-muted-foreground">
                    Single metric → concise answer &nbsp;·&nbsp; "Summarize" → full report
                  </span>
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}


// Global event to open chat from sidebar
export const OPEN_CHAT_EVENT = "open-gam-chat";

export function ChatDrawer() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessageType[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const { startDate, endDate, demandChannel } = useLiveReport();
  const sessionId = `${startDate}_${endDate}_${demandChannel}`;

  // Reset chat context when date range changes
  useEffect(() => {
    if (messages.length > 0) {
      setMessages([]);
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      setIsStreaming(false);
    }
  }, [sessionId]);

  // Listen for global open event
  useEffect(() => {
    const handleOpen = () => setIsOpen(true);
    window.addEventListener(OPEN_CHAT_EVENT, handleOpen);
    return () => window.removeEventListener(OPEN_CHAT_EVENT, handleOpen);
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isStreaming]);

  const handleSend = async (text: string) => {
    if (!text.trim() || isStreaming) return;

    const userMessage: ChatMessageType = {
      id: Date.now().toString(),
      role: "user",
      content: text,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsStreaming(true);

    const assistantId = (Date.now() + 1).toString();
    setMessages((prev) => [
      ...prev,
      {
        id: assistantId,
        role: "assistant",
        content: "",
        timestamp: new Date().toISOString(),
        isStreaming: true,
      },
    ]);

    abortControllerRef.current = new AbortController();

    try {
      const stream = streamChat(
        sessionId,
        text,
        messages,
        { startDate, endDate, demandChannel },
        abortControllerRef.current.signal
      );

      for await (const event of stream) {
        if (event.type === 'token') {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, content: m.content + event.content }
                : m
            )
          );
        } else if (event.type === 'error') {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, error: event.content, isStreaming: false }
                : m
            )
          );
        }
      }
    } catch (error) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? { ...m, error: "An unexpected error occurred.", isStreaming: false }
            : m
        )
      );
    } finally {
      setIsStreaming(false);
      setMessages((prev) =>
        prev.map((m) => (m.id === assistantId ? { ...m, isStreaming: false } : m))
      );
    }
  };

  const retryMessage = () => {
    const lastUser = [...messages].reverse().find(m => m.role === 'user');
    if (lastUser) {
      const newHistory = messages.slice(0, -2);
      setMessages(newHistory);
      handleSend(lastUser.content);
    }
  };

  return (
    <>
      {/* Floating Action Button */}
      <AnimatePresence>
        {!isOpen && (
          <motion.div
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0, opacity: 0 }}
            className="fixed bottom-6 right-6 z-50"
          >
            <Button
              size="lg"
              className="h-14 w-14 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 shadow-lg hover:shadow-xl hover:scale-105 transition-all text-white p-0 relative"
              onClick={() => setIsOpen(true)}
            >
              <MessageCircle className="h-6 w-6" />
              <span className="absolute -top-1 -right-1 h-3 w-3 rounded-full bg-emerald-500 border-2 border-background" />
            </Button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Drawer Overlay */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-background/40 backdrop-blur-sm z-50 flex justify-end"
            onClick={() => setIsOpen(false)}
          >
            {/* Drawer Panel */}
            <motion.div
              initial={{ x: "100%" }}
              animate={{ x: 0 }}
              exit={{ x: "100%" }}
              transition={{ type: "spring", damping: 25, stiffness: 200 }}
              className="w-full max-w-[420px] bg-background border-l shadow-2xl h-full flex flex-col"
              onClick={(e) => e.stopPropagation()}
            >
              {/* Header */}
              <div className="flex items-center justify-between p-4 border-b bg-card">
                <div className="flex items-center gap-3">
                  <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-sm">
                    <Zap className="h-4 w-4 text-white" />
                  </div>
                  <div>
                    <h2 className="text-sm font-semibold tracking-tight">Ask GAM 360</h2>
                    <div className="flex items-center gap-1.5 mt-0.5">
                      <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                      <span className="text-[10px] text-muted-foreground font-medium">LIVE</span>
                      <span className="text-[10px] text-muted-foreground mx-1">•</span>
                      <span className="text-[10px] text-muted-foreground truncate max-w-[120px]">
                        {startDate === endDate ? startDate : `${startDate} to ${endDate}`}
                      </span>
                    </div>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 rounded-full text-muted-foreground hover:bg-muted"
                  onClick={() => setIsOpen(false)}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>

              {/* Messages Area */}
              <div className="flex-1 overflow-y-auto p-4 space-y-6 bg-muted/10">
                {messages.length === 0 ? (
                  <div className="h-full flex flex-col items-center justify-center text-center px-4">
                    <div className="h-12 w-12 rounded-2xl bg-indigo-500/10 flex items-center justify-center mb-4">
                      <MessageCircle className="h-6 w-6 text-indigo-600 dark:text-indigo-400" />
                    </div>
                    <h3 className="text-base font-semibold mb-2">How can I help you?</h3>
                    <p className="text-sm text-muted-foreground mb-6">
                      Ask any question about your live GAM data for {startDate === endDate ? 'today' : 'the selected date range'}.
                    </p>
                    <div className="flex flex-col w-full gap-2">
                      {SUGGESTIONS.map((suggestion, i) => (
                        <button
                          key={i}
                          onClick={() => handleSend(suggestion)}
                          className="text-left px-4 py-2.5 rounded-lg border bg-card hover:bg-muted/50 hover:border-indigo-500/30 text-sm transition-all text-muted-foreground hover:text-foreground shadow-sm"
                        >
                          {suggestion}
                        </button>
                      ))}
                    </div>
                  </div>
                ) : (
                  <>
                    {messages.map((msg) => (
                      <ChatMessage
                        key={msg.id}
                        role={msg.role}
                        content={msg.content}
                        isStreaming={msg.isStreaming}
                        error={msg.error}
                      />
                    ))}
                    {messages[messages.length - 1]?.error && (
                      <div className="flex justify-center">
                        <Button 
                          variant="outline" 
                          size="sm" 
                          onClick={retryMessage}
                          className="gap-2 text-xs h-8"
                        >
                          <RotateCcw className="h-3 w-3" /> Retry Last Message
                        </Button>
                      </div>
                    )}
                    <div ref={messagesEndRef} className="h-1" />
                  </>
                )}
              </div>

              {/* Input Area */}
              <div className="p-4 bg-background border-t">
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    handleSend(input);
                  }}
                  className="relative flex items-end gap-2 bg-muted/50 rounded-xl border focus-within:ring-1 focus-within:ring-indigo-500/50 focus-within:border-indigo-500/50 transition-all p-2"
                >
                  <textarea
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        handleSend(input);
                      }
                    }}
                    placeholder="Ask about your live data..."
                    className="flex-1 max-h-32 min-h-[40px] resize-none bg-transparent border-0 focus:ring-0 text-sm px-2 py-2.5 scrollbar-thin placeholder:text-muted-foreground"
                    disabled={isStreaming}
                    rows={1}
                  />
                  <Button
                    type="submit"
                    size="icon"
                    disabled={!input.trim() || isStreaming}
                    className="h-9 w-9 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white shrink-0 shadow-sm"
                  >
                    <Send className="h-4 w-4" />
                  </Button>
                </form>
                <div className="text-center mt-2">
                  <span className="text-[10px] text-muted-foreground">
                    Powered by live Google Ad Manager data — ask about any date range.
                  </span>
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
