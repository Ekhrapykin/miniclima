import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  reactStrictMode: true,
  productionBrowserSourceMaps: false, // faster
};

export default nextConfig;
