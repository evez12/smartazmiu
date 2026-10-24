import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  reactStrictMode: true,
  // Keeps the floating dev badge out of screenshots and visual baselines.
  devIndicators: false,
  // `make dev-web` is reached via 127.0.0.1 as well as localhost (see Makefile).
  allowedDevOrigins: ["127.0.0.1"],
};

export default withNextIntl(nextConfig);
