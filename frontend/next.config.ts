import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // /dashboard was renamed to /library. Keep old links and bookmarks working.
  async redirects() {
    return [
      { source: "/dashboard", destination: "/library", permanent: false },
      {
        source: "/dashboard/:path*",
        destination: "/library/:path*",
        permanent: false,
      },
    ];
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/:path*`,
      },
    ];
  },
};

export default nextConfig;
