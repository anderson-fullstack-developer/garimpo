import type { Item } from "./api/types";

export type Highlight = "PERFECT" | "BEST_DEAL" | null;

/** Os 3 itens mais baratos da lista atual são "melhor oferta". */
export function bestDealIds(items: Item[], count = 3): Set<string> {
  return new Set(
    [...items]
      .sort((a, b) => a.price - b.price)
      .slice(0, count)
      .map((i) => i.id),
  );
}

/** PERFEITO tem prioridade sobre MELHOR OFERTA. */
export function highlightFor(item: Item, bestDeals: Set<string>): Highlight {
  if (item.isPerfect) return "PERFECT";
  if (bestDeals.has(item.id)) return "BEST_DEAL";
  return null;
}

export function isPerfectPrice(
  price: number,
  perfectMin: number | null,
  perfectMax: number | null,
): boolean {
  if (perfectMin === null && perfectMax === null) return false;
  if (perfectMin !== null && price < perfectMin) return false;
  if (perfectMax !== null && price > perfectMax) return false;
  return true;
}
