import type { NextConfig } from "next";

const isProd = process.env.NODE_ENV === "production";

const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: {
    unoptimized: true,
  },
  // For GitHub Pages: set basePath to your repo name
  // Change 'GAM-360-Live-Reporting-Platform' to your actual repo name if different
  basePath: isProd ? "/GAM-360-Live-Reporting-Platform" : "",
  assetPrefix: isProd ? "/GAM-360-Live-Reporting-Platform/" : "",
};

export default nextConfig;
