"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

export interface NavItem {
  title: string;
  href: string;
}

export interface NavGroup {
  title: string;
  items: NavItem[];
}

export const docsConfig: NavGroup[] = [
  {
    title: "Getting Started",
    items: [
      { title: "Introduction", href: "/docs" },
      { title: "Overview", href: "/docs/overview" },
      { title: "Local Development", href: "/docs/local-development" },
      { title: "Project Structure", href: "/docs/project-structure" },
    ],
  },
  {
    title: "Core Concepts",
    items: [
      { title: "Features", href: "/docs/features" },
      { title: "Architecture", href: "/docs/architecture" },
      { title: "Data Flow", href: "/docs/data-flow" },
    ],
  },
  {
    title: "AI Layer",
    items: [
      { title: "Ask GAM 360", href: "/docs/ask-gam-360" },
    ],
  },
  {
    title: "Reference",
    items: [
      { title: "API Documentation", href: "/docs/api" },
      { title: "Tech Stack", href: "/docs/tech-stack" },
      { title: "Deployment", href: "/docs/deployment" },
    ],
  },
];

export function Sidebar({ className }: { className?: string }) {
  const pathname = usePathname();

  return (
    <div className={cn("w-full", className)}>
      <div className="w-full">
        {docsConfig.map((group, index) => (
          <div key={index} className="pb-8">
            <h4 className="mb-2 rounded-md px-2 py-1 text-sm font-semibold uppercase tracking-wider text-foreground">
              {group.title}
            </h4>
            <div className="grid grid-flow-row auto-rows-max text-sm">
              {group.items.map((item, itemIndex) => {
                // Ensure proper matching logic
                const isActive = pathname === item.href || (pathname.startsWith(item.href) && item.href !== "/docs");
                return (
                  <Link
                    key={itemIndex}
                    href={item.href}
                    className={cn(
                      "group flex w-full items-center rounded-md border border-transparent px-2 py-1.5 hover:underline",
                      isActive
                        ? "font-medium text-foreground sidebar-link-active"
                        : "text-muted-foreground hover:text-foreground"
                    )}
                  >
                    {item.title}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
