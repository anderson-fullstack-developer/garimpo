"use client";

import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { History as HistoryIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { EmptyState, ErrorState, LoadingList, PageHeader } from "@/components/states";
import { UpgradeHint } from "@/components/upgrade-hint";
import { PriceHistoryChart } from "@/features/history/PriceHistoryChart";
import { useAlerts, qk } from "@/hooks/useGarimpo";
import { useAuth } from "@/features/auth/AuthProvider";
import { entitlementsFor } from "@/lib/entitlements";
import { api } from "@/lib/api";
import { formatMoney, relativeTime } from "@/lib/format";
import { pt, t } from "@/i18n/pt";
import { APP_NAME } from "@/config/brand";
import type { Item, ItemQuery } from "@/lib/api/types";

export function HistoryPage() {
  const { user } = useAuth();
  const ent = entitlementsFor(user?.plan ?? "FREE");
  const { data: alerts } = useAlerts();
  const [alertId, setAlertId] = useState<string>("all");
  const [period, setPeriod] = useState<"1h" | "today" | "7d">("7d");
  const [selected, setSelected] = useState<Item | null>(null);

  const query: ItemQuery = {
    alertIds: alertId === "all" ? undefined : [alertId],
    period,
    sort: "newest",
  };

  const list = useInfiniteQuery({
    queryKey: ["items", "history", query],
    queryFn: ({ pageParam }) =>
      api.items.list({ ...query, cursor: pageParam as string | undefined }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.nextCursor ?? undefined,
  });

  const history = useQuery({
    queryKey: qk.history(selected?.id ?? ""),
    queryFn: () => api.items.history(selected!.id),
    enabled: Boolean(selected),
  });

  const items = list.data?.pages.flatMap((p) => p.items) ?? [];
  const selectedAlert = alerts?.find((a) => a.id === selected?.alertId);

  return (
    <div className="space-y-5">
      <PageHeader title={pt.history.title} subtitle={pt.history.subtitle} />

      <div className="surface flex flex-wrap items-center gap-3 p-3">
        <Select value={alertId} onValueChange={setAlertId}>
          <SelectTrigger className="w-48" aria-label={pt.feed.filterAlert}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{pt.common.all}</SelectItem>
            {(alerts ?? []).map((a) => (
              <SelectItem key={a.id} value={a.id}>
                {a.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={period} onValueChange={(v) => setPeriod(v as typeof period)}>
          <SelectTrigger className="w-36" aria-label={pt.feed.filterPeriod}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="1h">{pt.feed.period1h}</SelectItem>
            <SelectItem value="today">{pt.feed.periodToday}</SelectItem>
            <SelectItem value="7d">{pt.feed.period7d}</SelectItem>
          </SelectContent>
        </Select>
        <Badge variant="secondary">
          {ent.historyDays === null
            ? pt.billing.unlimited
            : t(pt.history.limit, { days: ent.historyDays })}
        </Badge>
      </div>

      {ent.historyDays !== null && ent.historyDays <= 7 ? (
        <UpgradeHint feature="historyDays" />
      ) : null}

      {list.isLoading ? <LoadingList rows={4} /> : null}
      {list.isError ? <ErrorState error={list.error} onRetry={() => list.refetch()} /> : null}

      {list.data && items.length === 0 ? (
        <EmptyState
          icon={<HistoryIcon className="size-6" aria-hidden />}
          title={pt.history.emptyTitle}
          description={pt.history.emptyText}
        />
      ) : null}

      {items.length ? (
        <div className="grid gap-4 lg:grid-cols-[22rem_1fr]">
          <ul className="surface max-h-[32rem] divide-y divide-border overflow-y-auto">
            {items.map((item) => (
              <li key={item.id}>
                <button
                  type="button"
                  onClick={() => setSelected(item)}
                  aria-current={selected?.id === item.id}
                  className={
                    selected?.id === item.id
                      ? "flex w-full flex-col gap-0.5 bg-accent/60 p-3 text-left"
                      : "flex w-full flex-col gap-0.5 p-3 text-left hover:bg-muted/60"
                  }
                >
                  <span className="truncate text-sm font-medium">{item.title}</span>
                  <span className="text-xs text-muted-foreground">
                    {formatMoney(item.price, item.currency)} · {relativeTime(item.firstSeenAt)}
                  </span>
                </button>
              </li>
            ))}
            {list.hasNextPage ? (
              <li className="p-3">
                <Button
                  variant="outline"
                  className="w-full"
                  onClick={() => void list.fetchNextPage()}
                >
                  {pt.common.loadMore}
                </Button>
              </li>
            ) : null}
          </ul>

          <div className="surface p-4">
            {!selected ? (
              <p className="py-16 text-center text-sm text-muted-foreground">
                {pt.history.pickItem}
              </p>
            ) : history.isLoading ? (
              <LoadingList rows={2} />
            ) : history.isError ? (
              <ErrorState error={history.error} onRetry={() => history.refetch()} />
            ) : history.data ? (
              <>
                <h2 className="mb-3 text-sm font-semibold">{selected.title}</h2>
                <PriceHistoryChart
                  points={history.data}
                  currency={selected.currency}
                  perfectMin={selectedAlert?.perfectMin ?? null}
                  perfectMax={selectedAlert?.perfectMax ?? null}
                />
              </>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}
