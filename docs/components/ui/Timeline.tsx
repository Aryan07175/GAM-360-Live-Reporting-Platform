"use client";

import { ReactNode } from "react";
import { motion } from "framer-motion";

interface TimelineEvent {
  title: string;
  description: string;
  icon?: ReactNode;
}

interface TimelineProps {
  events: TimelineEvent[];
}

export function Timeline({ events }: TimelineProps) {
  return (
    <div className="relative border-l border-border ml-4 md:ml-6 my-8 space-y-8">
      {events.map((event, index) => (
        <motion.div
          key={index}
          initial={{ opacity: 0, x: -20 }}
          whileInView={{ opacity: 1, x: 0 }}
          viewport={{ once: true, margin: "-50px" }}
          transition={{ duration: 0.4, delay: index * 0.1 }}
          className="relative pl-8 md:pl-10"
        >
          {/* Dot / Icon */}
          <div className="absolute -left-4 top-1 flex h-8 w-8 items-center justify-center rounded-full border border-border bg-card shadow-sm text-primary">
            {event.icon || <div className="h-2.5 w-2.5 rounded-full bg-primary" />}
          </div>
          
          <h4 className="text-lg font-semibold text-foreground m-0 mb-2">
            {event.title}
          </h4>
          <p className="text-muted-foreground m-0 leading-relaxed text-sm">
            {event.description}
          </p>
        </motion.div>
      ))}
    </div>
  );
}
