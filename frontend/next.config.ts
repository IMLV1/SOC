import type { NextConfig } from "next";

const backendOrigin = process.env.BACKEND_ORIGIN ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${backendOrigin}/api/v1/:path*`,
      },
      {
        source: "/health/:path*",
        destination: `${backendOrigin}/health/:path*`,
      },
    ];
  },
};

export default nextConfig;
