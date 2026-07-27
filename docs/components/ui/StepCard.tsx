"use client";

import { ReactNode } from "react";

interface StepCardProps {
  number: number;
  title: string;
  children: ReactNode;
}

export function StepCard({ number, title, children }: StepCardProps) {
  return (
    <div className="relative pl-12 py-4 mb-6">
      {/* Vertical line connecting steps */}
      <div className="absolute left-[1.15rem] top-12 bottom-[-1.5rem] w-px bg-border last:hidden" />
      
      {/* Number circle */}
      <div className="absolute left-0 top-4 flex h-9 w-9 items-center justify-center rounded-full border-2 border-primary bg-background text-sm font-bold text-primary shadow-sm z-10">
        {number}
      </div>
      
      <h3 className="m-0 mb-4 text-xl font-semibold text-foreground">
        {title}
      </h3>
      
      <div className="m-0 text-muted-foreground">
        {children}
      </div>
    </div>
  );
}
