"use client";

import { useState, useEffect } from "react";
import { Navbar } from "@/components/layout/Navbar";
import { Sidebar } from "@/components/layout/Sidebar";
import { Footer } from "@/components/layout/Footer";
import { SearchModal } from "@/components/search/SearchModal";
import { Menu } from "lucide-react";

export default function DocsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [readingProgress, setReadingProgress] = useState(0);

  // Handle global keyboard shortcuts for search
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setIsSearchOpen(true);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  // Handle reading progress
  useEffect(() => {
    const handleScroll = () => {
      const windowHeight = window.innerHeight;
      const documentHeight = document.documentElement.scrollHeight - windowHeight;
      const scrolled = window.scrollY;
      const progress = documentHeight > 0 ? (scrolled / documentHeight) * 100 : 0;
      setReadingProgress(progress);
    };

    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  // Close sidebar on navigation (mobile)
  useEffect(() => {
    const handleRouteChange = () => setIsSidebarOpen(false);
    // In Next 13+ App Router, we can just close on click inside the sidebar
  }, []);

  return (
    <div className="relative flex min-h-screen flex-col bg-background">
      {/* Reading Progress Bar */}
      <div 
        id="reading-progress" 
        style={{ width: `${readingProgress}%` }}
      />
      
      <Navbar onMenuClick={() => setIsSidebarOpen(!isSidebarOpen)} />
      <SearchModal isOpen={isSearchOpen} onClose={() => setIsSearchOpen(false)} />

      <div className="container mx-auto flex-1 items-start md:grid md:grid-cols-[220px_minmax(0,1fr)] md:gap-6 lg:grid-cols-[240px_minmax(0,1fr)] lg:gap-10 px-4 md:px-8">
        
        {/* Desktop Sidebar */}
        <aside className="fixed top-14 z-30 -ml-2 hidden h-[calc(100vh-3.5rem)] w-full shrink-0 md:sticky md:block overflow-y-auto pt-8 pb-10">
          <Sidebar />
        </aside>

        {/* Mobile Sidebar overlay */}
        {isSidebarOpen && (
          <div 
            className="fixed inset-0 z-40 bg-background/80 backdrop-blur-sm md:hidden"
            onClick={() => setIsSidebarOpen(false)}
          />
        )}

        {/* Mobile Sidebar panel */}
        <aside
          className={`fixed inset-y-0 left-0 z-50 w-3/4 max-w-sm transform border-r bg-background p-6 transition-transform duration-300 ease-in-out md:hidden overflow-y-auto ${
            isSidebarOpen ? "translate-x-0" : "-translate-x-full"
          }`}
        >
          <div className="flex items-center justify-between mb-6">
            <span className="font-bold gradient-text">Menu</span>
            <button
              onClick={() => setIsSidebarOpen(false)}
              className="rounded-md p-2 text-muted-foreground hover:bg-secondary"
            >
              <Menu className="h-5 w-5" />
            </button>
          </div>
          <div onClick={() => setIsSidebarOpen(false)}>
            <Sidebar />
          </div>
        </aside>

        <main className="relative py-6 lg:gap-10 lg:py-8 xl:grid xl:grid-cols-[1fr_300px]">
          <div className="mx-auto w-full min-w-0">
            <div className="prose prose-docs dark:prose-invert animate-fade-in-up">
              {children}
            </div>
            <div className="mt-16">
              <Footer />
            </div>
          </div>
          
          {/* Table of Contents will go here in the right sidebar (optional for later) */}
          <div className="hidden text-sm xl:block">
            <div className="sticky top-16 -mt-10 pt-4 text-muted-foreground">
              {/* Optional TOC placeholder */}
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
