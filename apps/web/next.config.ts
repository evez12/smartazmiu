import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

// One id per build: it names the service worker's caches and tells open pages that a newer build is deployed.
// The build's worker processes load this file again, so the value is kept in the environment they inherit.
process.env.BUILD_STAMP ??= Date.now().toString(36);
const buildId = process.env.NODE_ENV === "production" ? process.env.BUILD_STAMP : "development";

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  reactStrictMode: true,
  generateBuildId: async () => buildId,
  env: { NEXT_PUBLIC_BUILD_ID: buildId },
  // Keeps the floating dev badge out of screenshots and visual baselines.
  devIndicators: false,
  // `make dev-web` is reached via 127.0.0.1 as well as localhost (see Makefile).
  allowedDevOrigins: ["127.0.0.1"],
};

export default withNextIntl(nextConfig);
