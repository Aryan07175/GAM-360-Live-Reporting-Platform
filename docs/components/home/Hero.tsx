"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowRight, BookOpen, Activity } from "lucide-react";

const GithubIcon = () => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    className="mr-2 h-4 w-4"
  >
    <path d="M15 22v-4a4.8 4.8 0 0 0-1-3.02c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A4.8 4.8 0 0 0 8 18v4"></path>
  </svg>
);

export function Hero() {
  return (
    <div className="relative overflow-hidden pt-24 pb-32 md:pt-32 md:pb-40">
      {/* Animated Background */}
      <div className="absolute inset-0 grid-bg -z-10" />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-primary/20 blur-[120px] rounded-full mix-blend-screen pointer-events-none -z-10 pulse-glow" />

      <div className="container mx-auto px-4 md:px-8">
        <div className="flex flex-col items-center text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="inline-flex items-center rounded-full border border-border bg-background/50 backdrop-blur-sm px-4 py-1.5 text-sm font-medium mb-8"
          >
            <span className="flex h-2 w-2 rounded-full bg-green-500 mr-2 animate-pulse" />
            Zero database. Zero cache. 100% Live.
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="max-w-4xl text-5xl font-extrabold tracking-tight sm:text-6xl md:text-7xl lg:text-8xl mb-6"
          >
            <span className="gradient-text">GAM 360</span> <br className="hidden sm:block" />
            Live Reporting Platform
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.2 }}
            className="max-w-2xl text-xl text-muted-foreground mb-10 leading-relaxed"
          >
            A Next.js executive BI reporting dashboard that fetches ad revenue analytics in real-time from Google Ad Manager 360, powered by Claude Haiku 4.5.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.3 }}
            className="flex flex-col sm:flex-row gap-4 w-full sm:w-auto"
          >
            <Link
              href="/docs"
              className="inline-flex h-12 items-center justify-center rounded-md bg-primary px-8 text-sm font-medium text-primary-foreground shadow transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              <BookOpen className="mr-2 h-4 w-4" />
              Read the Docs
            </Link>
            <Link
              href="https://github.com/YOUR_USERNAME/GAM-360-Live-Reporting-Platform"
              target="_blank"
              rel="noreferrer"
              className="inline-flex h-12 items-center justify-center rounded-md border border-input bg-background px-8 text-sm font-medium shadow-sm transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              <GithubIcon />
              GitHub
            </Link>
            <Link
              href="https://dashboard.render.com"
              target="_blank"
              rel="noreferrer"
              className="inline-flex h-12 items-center justify-center rounded-md bg-secondary px-8 text-sm font-medium shadow-sm transition-colors hover:bg-secondary/80 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              <Activity className="mr-2 h-4 w-4" />
              Live Demo
            </Link>
          </motion.div>
        </div>
      </div>
    </div>
  );
}
