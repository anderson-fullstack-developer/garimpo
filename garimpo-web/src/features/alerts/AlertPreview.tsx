import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ErrorState, LoadingList } from "@/components/states";
import { reasonLabel } from "@/features/alerts/reasons";
import { useDebounced } from "@/hooks/useDebounced";
import { api } from "@/lib/api";
import { formatMoney, relativeTime } from "@/lib/format";
import { pt, t } from "@/i18n/pt";
import type { AlertInput, PreviewRow } from "@/lib/api/types";

const COLLAPSED = 4;
const EXPANDED = 20;

function Row({ row, tone }: { row: PreviewRow; tone: "matched" | "discarded" }) {
  return (
    <li
      className={
        tone === "matched"
          ? "flex gap-3 rounded-lg border border-primary/30 bg-accent/40 p-2"
          : "flex gap-3 rounded-lg border border-border bg-muted/40 p-2"
      }
    >
      {row.item.photoUrl ? (
        <img
          src={row.item.photoUrl}
          alt=""
          loading="lazy"
          className="size-14 shrink-0 rounded-md bg-muted object-cover"
        />
      ) : null}
      <div className="min-w-0 flex-1">
        <p className="truncate text-xs font-medium">{row.item.title}</p>
        <p className="text-xs text-muted-foreground">
          {formatMoney(row.item.price, row.item.currency)} ·{" "}
          {row.item.condition ? pt.condition[row.item.condition] : "—"} ·{" "}
          {relativeTime(row.item.postedAt)}
        </p>
        {row.reasons.length ? (
          <ul className="mt-1 flex flex-wrap gap-1">
            {row.reasons.slice(0, 3).map((reason) => (
              <li key={reason}>
                <Badge variant="secondary" className="text-[10px]">
                  {reasonLabel(reason)}
                </Badge>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </li>
  );
}

/** Só o que afeta o resultado da prévia; nome/destino/ativo não devem disparar nova busca. */
function previewInput(draft: AlertInput): AlertInput {
  return { ...draft, name: "", destinationId: null, active: true };
}

/**
 * Prévia ao vivo: roda sozinha (com atraso) enquanto o usuário edita o alerta e mostra o que
 * casaria e o que foi descartado — com o motivo. É isso que dá confiança no filtro.
 */
export function AlertPreview({ draft }: { draft: AlertInput }) {
  const key = JSON.stringify(previewInput(draft));
  const debouncedKey = useDebounced(key, 600);
  const input = useMemo(() => JSON.parse(debouncedKey) as AlertInput, [debouncedKey]);
  const [expanded, setExpanded] = useState(false);

  const ready = input.query.trim().length >= 2;
  const preview = useQuery({
    queryKey: ["alert-preview", debouncedKey],
    queryFn: () => api.alerts.preview(input),
    enabled: ready,
    staleTime: 30_000,
    placeholderData: keepPreviousData,
  });

  const updating = ready && (key !== debouncedKey || preview.isFetching);
  const limit = expanded ? EXPANDED : COLLAPSED;
  const result = ready ? preview.data : undefined;

  return (
    <section className="surface space-y-3 p-4" aria-live="polite">
      <div className="space-y-1">
        <h2 className="text-sm font-semibold">{pt.alerts.previewTitle}</h2>
        <p className="text-xs text-muted-foreground">{pt.alerts.previewHint}</p>
      </div>

      {!ready ? (
        <p className="rounded-lg bg-muted/60 p-3 text-sm text-muted-foreground">
          {pt.alerts.previewEmpty}
        </p>
      ) : null}

      {ready && preview.isLoading ? <LoadingList rows={3} /> : null}
      {ready && preview.isError ? (
        <ErrorState error={preview.error} onRetry={() => preview.refetch()} />
      ) : null}

      {result ? (
        <div className="space-y-4">
          <p className="flex items-center justify-between gap-2 text-sm text-muted-foreground">
            <span>
              {t(pt.alerts.previewCounts, {
                matched: result.matched.length,
                discarded: result.discarded.length,
              })}
            </span>
            {updating ? <span className="text-xs">{pt.alerts.previewUpdating}</span> : null}
          </p>

          <div className="space-y-2">
            <h3 className="text-xs font-semibold text-primary">
              {pt.alerts.previewMatched} ({result.matched.length})
            </h3>
            <ul className="space-y-2">
              {result.matched.slice(0, limit).map((row) => (
                <Row key={row.item.id} row={row} tone="matched" />
              ))}
            </ul>
          </div>

          <div className="space-y-2">
            <h3 className="text-xs font-semibold text-muted-foreground">
              {pt.alerts.previewDiscarded} ({result.discarded.length})
            </h3>
            <ul className="space-y-2">
              {result.discarded.slice(0, limit).map((row) => (
                <Row key={row.item.id} row={row} tone="discarded" />
              ))}
            </ul>
          </div>

          {result.matched.length > COLLAPSED || result.discarded.length > COLLAPSED ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setExpanded((value) => !value)}
            >
              {expanded ? pt.alerts.previewLess : pt.alerts.previewMore}
            </Button>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
