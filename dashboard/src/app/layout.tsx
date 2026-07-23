import type { Metadata } from "next";
export const maxDuration = 60; // Max Vercel timeout
import { Inter } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "@/components/theme-provider";
import { BackendKeepAlive } from "@/components/backend-keep-alive";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "GAM 360 Analytics Dashboard",
  description: "AI-powered Google Ad Manager 360 Analytics Dashboard",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${inter.className} antialiased`} suppressHydrationWarning>
        <ThemeProvider
          attribute="class"
          defaultTheme="system"
          enableSystem
          disableTransitionOnChange
        >
          <BackendKeepAlive />
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
