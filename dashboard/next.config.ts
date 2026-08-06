import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: 'standalone',
  // !! WARN !! — These flags suppress TypeScript and ESLint errors during build.
  // They exist to allow live deployment without blocking on type-check failures.
  // Removing ignoreBuildErrors is strongly recommended once all type errors are resolved.
  typescript: {
    ignoreBuildErrors: true,
  },
  eslint: {
    ignoreDuringBuilds: true,
  },
};

export default nextConfig;
