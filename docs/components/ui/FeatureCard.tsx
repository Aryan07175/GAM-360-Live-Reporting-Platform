"use client";

import { ReactNode } from "react";
import { motion } from "framer-motion";
import { LucideIcon } from "lucide-react";

interface FeatureCardProps {
  title: string;
  description: string;
  icon: LucideIcon;
  delay?: number;
}

export function FeatureCard({ title, description, icon: Icon, delay = 0 }: FeatureCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-50px" }}
      transition={{ duration: 0.5, delay }}
      whileHover={{ y: -5 }}
      className="group relative overflow-hidden rounded-2xl border border-border bg-card p-6 shadow-sm transition-all hover:shadow-md"
    >
      <div className="absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-transparent opacity-0 transition-opacity group-hover:opacity-100" />
      
      <div className="relative z-10 flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 text-primary mb-6 transition-transform group-hover:scale-110">
        <Icon className="h-6 w-6" />
      </div>
      
      <h3 className="mb-2 text-xl font-semibold tracking-tight text-foreground m-0">
        {title}
      </h3>
      
      <p className="text-muted-foreground leading-relaxed m-0 text-sm">
        {description}
      </p>
    </motion.div>
  );
}
