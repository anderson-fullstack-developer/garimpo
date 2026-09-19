"use client";

import { Search, Square } from "lucide-react";

import { Button } from "@/components/ui/button";
import { pt } from "@/i18n/pt";
import { useManualSearch } from "./useManualSearch";

/**
 * "Buscar agora": ao clicar vira "Buscando…" (lupa girando) e a busca segue até alguém parar.
 * O quadrado ao lado indica que outro clique interrompe.
 */
export function SearchButton({
  variant = "default",
  disabled = false,
}: {
  variant?: "default" | "outline";
  disabled?: boolean;
}) {
  const { running, toggle } = useManualSearch();
  return (
    <Button
      variant={variant}
      onClick={toggle}
      disabled={disabled && !running}
      aria-label={running ? pt.alerts.stopSearch : pt.alerts.searchNow}
      title={running ? pt.alerts.stopSearch : undefined}
    >
      <Search className={running ? "mr-1 size-4 animate-spin" : "mr-1 size-4"} aria-hidden />
      {running ? pt.alerts.searching : pt.alerts.searchNow}
      {running ? <Square className="ml-2 size-3 fill-current" aria-hidden /> : null}
    </Button>
  );
}
