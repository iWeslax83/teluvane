import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async redirects() {
    return [
      {
        source: "/pricing",
        destination: "/#pricing",
        permanent: false,
      },
    ];
  },
};

export default nextConfig;
