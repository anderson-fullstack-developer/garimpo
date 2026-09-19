import { pt, t } from "@/i18n/pt";

/** Converte "excluded_by_word:capa" em texto legível. */
export function reasonLabel(reason: string): string {
  const [code, value] = reason.split(":");
  const template = (pt.reasons as Record<string, string | undefined>)[code ?? ""];
  if (!template) return reason;
  return value ? t(template, { w: `“${value}”` }) : template;
}
