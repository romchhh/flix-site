/** @type {import('next').NextConfig} */
const backend = process.env.SITE_BACKEND_URL || "http://127.0.0.1:8000";

function allowedDevOrigins() {
  const hosts = ["*.ngrok-free.dev", "*.ngrok.io", "*.ngrok.app", "*.ngrok-free.app"];
  try {
    if (process.env.APP_URL) hosts.push(new URL(process.env.APP_URL).hostname);
  } catch {
    /* ignore invalid APP_URL */
  }
  return [...new Set(hosts.filter(Boolean))];
}

export default {
  reactStrictMode: true,
  allowedDevOrigins: allowedDevOrigins(),
  env: { APP_URL: process.env.APP_URL || "http://localhost:3000" },
  poweredByHeader: false,
  async rewrites() {
    return [
      { source: "/api/auth/:path*", destination: `${backend}/api/auth/:path*` },
      { source: "/api/checkout", destination: `${backend}/api/checkout` },
      { source: "/api/webhooks/:path*", destination: `${backend}/api/webhooks/:path*` },
      { source: "/api/me", destination: `${backend}/api/me` },
      { source: "/api/catalog", destination: `${backend}/api/catalog` },
      { source: "/api/products/:path*", destination: `${backend}/api/products/:path*` },
      { source: "/api/media/:path*", destination: `${backend}/api/media/:path*` },
      { source: "/api/cabinet", destination: `${backend}/api/cabinet` },
      { source: "/api/admin/:path*", destination: `${backend}/api/admin/:path*` },
      { source: "/api/subs/:path*", destination: `${backend}/api/subs/:path*` },
    ];
  },
};
