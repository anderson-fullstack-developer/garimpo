import { currentLanguage } from "@/i18n/pt";

/** Valor especial: buscar em todos os países da Europa de uma vez. */
export const EUROPE = "eu";

/** Países com marketplace disponível (o código é o domínio: vinted.<código>). */
export const COUNTRIES = [
  "pt",
  "es",
  "fr",
  "it",
  "de",
  "nl",
  "be",
  "lu",
  "at",
  "ie",
  "pl",
  "cz",
  "sk",
  "hu",
  "ro",
  "hr",
  "lt",
  "fi",
  "se",
  "dk",
  "gr",
].map((code) => ({ code })) as ReadonlyArray<{ code: string }>;

/** Moedas que o app converte (o preço original continua visível ao lado). */
export const CURRENCIES = [
  "EUR",
  "PLN",
  "SEK",
  "DKK",
  "CZK",
  "HUF",
  "RON",
  "BGN",
  "GBP",
  "CHF",
  "NOK",
  "USD",
] as const;

/** Nome do país no idioma atual (Portugal / Poland...). */
export function countryLabel(code: string): string {
  if (code === EUROPE) return currentLanguage() === "en" ? "Europe" : "Europa";
  try {
    return (
      new Intl.DisplayNames([currentLanguage()], { type: "region" }).of(code.toUpperCase()) ?? code
    );
  } catch {
    return code.toUpperCase();
  }
}
