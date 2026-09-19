import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import { cookies } from "next/headers";
import type { ReactNode } from "react";

import { APP_NAME } from "@/config/brand";
import { serverMessages } from "@/i18n/server";

import { DEFAULT_LANGUAGE, LANGUAGE_COOKIE, isLanguage } from "@/i18n/pt";

import { Providers } from "./providers";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });

export async function generateMetadata(): Promise<Metadata> {
  const m = await serverMessages();
  const title = `${APP_NAME} — ${m.meta.appTitle}`;
  return {
    title,
    description: m.meta.tagline,
    openGraph: { title, description: m.meta.tagline, type: "website" },
    twitter: { card: "summary_large_image" },
  };
}

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

/**
 * Aplica o tema antes da primeira pintura (evita "flash" claro no modo escuro).
 * Deve espelhar a lógica de `ThemeProvider` (mesma chave no localStorage).
 */
const THEME_SCRIPT = `(function(){try{var t=localStorage.getItem("garimpo.theme");var d=t?t==="dark":window.matchMedia("(prefers-color-scheme: dark)").matches;document.documentElement.classList.toggle("dark",d)}catch(e){}})()`;

export default async function RootLayout({ children }: { children: ReactNode }) {
  const stored = (await cookies()).get(LANGUAGE_COOKIE)?.value;
  const language = isLanguage(stored) ? stored : DEFAULT_LANGUAGE;
  return (
    <html lang={language} className={inter.variable} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body>
        <Providers language={language}>{children}</Providers>
      </body>
    </html>
  );
}
