"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

import { ThemeProvider } from "@/components/theme-provider";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider } from "@/features/auth/AuthProvider";
import { LanguageBoundary, LanguageProvider } from "@/i18n/LanguageProvider";
import type { Language } from "@/i18n/pt";

export function Providers({ children, language }: { children: ReactNode; language: Language }) {
  // Um QueryClient por sessão do navegador (nunca compartilhado entre requisições no servidor).
  const [queryClient] = useState(() => new QueryClient());

  return (
    <LanguageProvider initial={language}>
      <QueryClientProvider client={queryClient}>
        <ThemeProvider>
          <AuthProvider>
            <LanguageBoundary>
              {children}
              <Toaster position="top-center" richColors />
            </LanguageBoundary>
          </AuthProvider>
        </ThemeProvider>
      </QueryClientProvider>
    </LanguageProvider>
  );
}
