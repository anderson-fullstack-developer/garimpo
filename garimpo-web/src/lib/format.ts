import { currentLanguage, pt, t as fill } from "@/i18n/pt";

function locale(): string {
  return currentLanguage() === "en" ? "en-GB" : "pt-BR";
}

export function formatMoney(value: number, currency = "EUR"): string {
  return new Intl.NumberFormat(locale(), {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(value);
}

export function formatNumber(value: number): string {
  return new Intl.NumberFormat(locale()).format(value);
}

/** Tempo relativo curto: "agora", "há 3 min", "há 2 h", "há 4 d". */
export function relativeTime(iso: string | null | undefined, now: number = Date.now()): string {
  if (!iso) return "—";
  const diff = Math.max(0, now - new Date(iso).getTime());
  const min = Math.floor(diff / 60000);
  if (min < 1) return pt.time.now;
  if (min < 60) return fill(pt.time.ago, { n: min, u: pt.time.unitMin });
  const hours = Math.floor(min / 60);
  if (hours < 24) return fill(pt.time.ago, { n: hours, u: pt.time.unitHour });
  const days = Math.floor(hours / 24);
  return fill(pt.time.ago, { n: days, u: pt.time.unitDay });
}

/** "em ~2 min" para o próximo ciclo do monitor. */
export function untilTime(iso: string | null | undefined, now: number = Date.now()): string {
  if (!iso) return "—";
  const diff = new Date(iso).getTime() - now;
  if (diff <= 0) return pt.time.anyMoment;
  const min = Math.round(diff / 60000);
  if (min < 1) return fill(pt.time.inAbout, { n: Math.round(diff / 1000), u: pt.time.unitSec });
  return fill(pt.time.inAbout, { n: min, u: pt.time.unitMin });
}

/** Intervalo de verificação legível: 0,5 -> "30 s", 1 -> "1 min". */
export function formatInterval(minutes: number): string {
  if (minutes < 1) return `${Math.round(minutes * 60)} s`;
  return `${Number.isInteger(minutes) ? minutes : minutes.toFixed(1)} min`;
}

export function formatDuration(seconds: number | null): string {
  if (seconds === null) return "—";
  if (seconds < 60) return `${Math.round(seconds)} s`;
  return `${Math.round(seconds / 60)} min`;
}

export function formatDateTime(iso: string | null): string {
  if (!iso) return "—";
  return new Intl.DateTimeFormat(locale(), {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(iso));
}

export function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Intl.DateTimeFormat(locale(), {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(new Date(iso));
}

export function formatTime(iso: string | null): string {
  if (!iso) return "—";
  return new Intl.DateTimeFormat(locale(), { hour: "2-digit", minute: "2-digit" }).format(
    new Date(iso),
  );
}
