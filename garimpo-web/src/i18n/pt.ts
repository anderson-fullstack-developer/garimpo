import { enDict } from "./dict-en";
import { ptDict } from "./dict-pt";
import type { Messages } from "./messages";

export const LANGUAGES = ["pt", "en"] as const;
export type Language = (typeof LANGUAGES)[number];
export const DEFAULT_LANGUAGE: Language = "pt";
export const LANGUAGE_COOKIE = "garimpo-lang";

const dictionaries: Record<Language, Messages> = { pt: ptDict as Messages, en: enDict };
let current: Language = DEFAULT_LANGUAGE;

export function isLanguage(value: unknown): value is Language {
  return typeof value === "string" && (LANGUAGES as readonly string[]).includes(value);
}

/** Textos de um idioma específico (usado no servidor, onde não há o idioma "ativo"). */
export function messagesFor(language: Language): Messages {
  return dictionaries[language];
}

export function setLanguage(language: Language): void {
  current = language;
}

export function currentLanguage(): Language {
  return current;
}

/**
 * Textos do idioma ativo. É um proxy para que o restante do app continue escrevendo `pt.secao.chave`:
 * a cada leitura vale o idioma atual (a troca remonta a tela, ver LanguageProvider).
 */
export const pt: Messages = new Proxy({} as Messages, {
  get: (_target, key: string) => dictionaries[current][key as keyof Messages],
  has: (_target, key: string) => key in dictionaries[current],
  ownKeys: () => Reflect.ownKeys(dictionaries[current]),
  getOwnPropertyDescriptor: (_target, key: string) => ({
    enumerable: true,
    configurable: true,
    value: dictionaries[current][key as keyof Messages],
  }),
});

export function t(template: string, vars: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (_, k: string) => String(vars[k] ?? `{${k}}`));
}
