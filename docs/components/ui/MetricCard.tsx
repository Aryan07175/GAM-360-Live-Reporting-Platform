"use client";

import { motion } from "framer-motion";

interface MetricCardProps {
  value: string;
  label: string;
  delay?: number;
}

export function MetricCard({ value, label, delay = 0 }: MetricCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      whileInView={{ opacity: 1, scale: 1 }}
      viewport={{ once: true }}
      transition={{ duration: 0.4, delay }}
      className="flex flex-col items-center justify-center p-6 text-center"
    >
      <div className="text-4xl md:text-5xl font-bold gradient-text mb-2 tracking-tight">
        {value}
      </div>
      <div className="text-sm font-medium uppercase tracking-widest text-muted-foreground">
        {label}
      </div>
    </motion.div>
  );
}
