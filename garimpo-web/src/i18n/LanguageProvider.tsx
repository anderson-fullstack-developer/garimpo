"use client";

import { createContext, Fragment, useCallback, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { LANGUAGE_COOKIE, setLanguage as applyLanguage, type Language } from "./pt";

interface LanguageContextValue {
  language: Language;
  /** `soft`: só atualiza os textos de quem já renderiza (não remonta a tela; preserva formulários). */
  setLanguage: (language: Language, soft?: boolean) => void;
  epoch: number;
}

const LanguageContext = createContext<LanguageContextValue | null>(null);

export function LanguageProvider({
  initial,
  children,
}: {
  initial: Language;
  children: ReactNode;
}) {
  const [language, setState] = useState<Language>(initial);
  const [epoch, setEpoch] = useState(0);
  applyLanguage(language); // antes de os filhos renderizarem: `pt.*` já lê o idioma certo

  const setLanguage = useCallback((next: Language, soft = false) => {
    applyLanguage(next);
    try {
      document.cookie = `${LANGUAGE_COOKIE}=${next}; path=/; max-age=31536000; samesite=lax`;
      document.documentElement.lang = next;
    } catch {
      /* sem cookie: vale só nesta visita */
    }
    setState(next);
    if (!soft) setEpoch((e) => e + 1);
  }, []);

  const value = useMemo(() => ({ language, setLanguage, epoch }), [language, setLanguage, epoch]);
  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

/** Remonta a árvore ao trocar de idioma (os componentes leem `pt.*` direto, sem hook). */
export function LanguageBoundary({ children }: { children: ReactNode }) {
  const { epoch } = useLanguage();
  return <Fragment key={epoch}>{children}</Fragment>;
}

export function useLanguage(): LanguageContextValue {
  const ctx = useContext(LanguageContext);
  if (!ctx) throw new Error("useLanguage precisa estar dentro de LanguageProvider");
  return ctx;
}
