/**
 * Aceita apenas caminhos internos (`/app/alerts`). Bloqueia URLs absolutas (`https://x`),
 * protocol-relative (`//x`) e barras invertidas, evitando open redirect via `?redirect=`.
 */
export function safeRedirect(value: unknown): string | undefined {
  if (typeof value !== "string") return undefined;
  if (!value.startsWith("/") || value.startsWith("//") || value.includes("\\")) return undefined;
  return value;
}
