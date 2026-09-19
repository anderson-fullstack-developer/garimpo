import type { NextConfig } from "next";

/**
 * Em modo real o navegador fala só com este domínio (`/api/...`) e o Next repassa ao
 * backend NestJS. Assim os cookies de sessão são first-party (sem SameSite=None e sem
 * bloqueio de cookies de terceiros) e não precisa de CORS.
 */
const API_PROXY_TARGET = process.env["API_PROXY_TARGET"];

const nextConfig: NextConfig = {
  // Permite uma segunda cópia (ex.: teste ponta a ponta) sem pisar no servidor de desenvolvimento.
  distDir: process.env["NEXT_DIST_DIR"] ?? ".next",
  reactStrictMode: true,
  // Some o "N" do Next.js no canto da tela (só existe em desenvolvimento).
  devIndicators: false,
  poweredByHeader: false,
  // "Buscar agora" num alerta de "Europa" consulta ~21 países e pode levar 30 s+.
  experimental: { proxyTimeout: 120_000 },
  async rewrites() {
    if (!API_PROXY_TARGET) return [];
    return [{ source: "/api/:path*", destination: `${API_PROXY_TARGET}/:path*` }];
  },
};

export default nextConfig;
