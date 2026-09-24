const path = require('path');

/** @type {import('next').NextConfig} */
const nextConfig = {
  outputFileTracingRoot: path.resolve(__dirname),
  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: true,
  },
  // Note: NEXT_PUBLIC_API_URL / NEXT_PUBLIC_SUPABASE_URL / NEXT_PUBLIC_SUPABASE_ANON_KEY
  // are intentionally NOT set here so that .env.local wins at build time.
  // If you ever add an override here, make sure it points to the SAME backend
  // the user is actually running (port 8001 in local dev, not 8000).
  // Optimizations
  reactStrictMode: true,
  // Headers for SSE streaming
  async headers() {
    return [
      {
        source: '/api/:path*',
        headers: [{ key: 'X-Content-Type-Options', value: 'nosniff' }],
      },
    ];
  },
};

module.exports = nextConfig;


