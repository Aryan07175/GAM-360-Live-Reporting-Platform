"use client";

import { motion } from "framer-motion";
import { ReactNode } from "react";

interface TechCardProps {
  name: string;
  category: string;
  description: string;
  icon?: ReactNode;
}

export function TechCard({ name, category, description, icon }: TechCardProps) {
  return (
    <motion.div
      whileHover={{ scale: 1.02 }}
      className="flex flex-col rounded-xl border border-border bg-card p-5 shadow-sm transition-shadow hover:shadow-md"
    >
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          {icon && (
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-secondary text-foreground">
              {icon}
            </div>
          )}
          <h4 className="font-semibold m-0 text-foreground">{name}</h4>
        </div>
        <span className="rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-medium text-primary">
          {category}
        </span>
      </div>
      <p className="text-sm text-muted-foreground m-0 leading-relaxed">
        {description}
      </p>
    </motion.div>
  );
}
