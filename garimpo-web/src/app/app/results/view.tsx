"use client";

import { useInfiniteQuery } from "@tanstack/react-query";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowUp, Search, Sparkles } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { EmptyState, ErrorState, LoadingList, PageHeader, errorMessage } from "@/components/states";
import { ItemCard } from "@/features/feed/ItemCard";
import { SendToDestinationDialog } from "@/features/feed/SendToDestinationDialog";
import { useAlerts } from "@/hooks/useGarimpo";
import { SearchButton } from "@/features/search/SearchButton";
import { api } from "@/lib/api";
import { bestDealIds, highlightFor } from "@/lib/highlights";
import { pt, t } from "@/i18n/pt";
import type { Item, ItemQuery } from "@/lib/api/types";

interface ResultsSearch {
  alert?: string | undefined;
  sort: "newest" | "price_asc";
}

/** Filtros vivem na URL (`?alert=…&sort=…`), então dá para compartilhar/recarregar a tela. */
function parseSearch(params: URLSearchParams): ResultsSearch {
  return {
    alert: params.get("alert") ?? undefined,
    sort: params.get("sort") === "price_asc" ? "price_asc" : "newest",
  };
}

export function ResultsPage() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const search = useMemo(() => parseSearch(searchParams), [searchParams]);
  const { data: alerts } = useAlerts();
  const [sendItem, setSendItem] = useState<Item | null>(null);
  const [newCount, setNewCount] = useState(0);
  const firstIdRef = useRef<string | null>(null);

  const query: ItemQuery = useMemo(
    () => ({
      alertIds: search.alert ? [search.alert] : undefined,
      sort: search.sort,
    }),
    [search.alert, search.sort],
  );

  const feed = useInfiniteQuery({
    queryKey: ["items", query],
    queryFn: ({ pageParam }) =>
      api.items.list({ ...query, cursor: pageParam as string | undefined }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.nextCursor ?? undefined,
    refetchInterval: 15000,
  });

  const items = useMemo(() => feed.data?.pages.flatMap((p) => p.items) ?? [], [feed.data]);
  const bestDeals = useMemo(() => bestDealIds(items), [items]);

  // Avisa (sem pular a lista sozinho) quando chegam anúncios novos no topo.
  useEffect(() => {
    const first = items[0];
    if (!first) return;
    if (firstIdRef.current === null) {
      firstIdRef.current = first.id;
      return;
    }
    if (firstIdRef.current !== first.id) {
      const index = items.findIndex((i) => i.id === firstIdRef.current);
      setNewCount(index > 0 ? index : 1);
    }
  }, [items]);

  const setSearch = (patch: Partial<ResultsSearch>) => {
    const next = { ...search, ...patch };
    const qs = new URLSearchParams();
    if (next.alert) qs.set("alert", next.alert);
    if (next.sort !== "newest") qs.set("sort", next.sort);
    const text = qs.toString();
    router.replace(text ? `${pathname}?${text}` : pathname, { scroll: false });
  };

  return (
    <div className="space-y-5">
      <PageHeader title={pt.feed.title} subtitle={pt.feed.subtitle} actions={<SearchButton />} />

      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <span className="text-[11px] text-muted-foreground">{pt.feed.filterAlert}</span>
          <Select
            value={search.alert ?? "all"}
            onValueChange={(v) => setSearch({ alert: v === "all" ? undefined : v })}
          >
            <SelectTrigger className="w-48" aria-label={pt.feed.filterAlert}>
              <SelectValue placeholder={pt.feed.filterAlert} />
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
        </div>

        <div className="flex flex-col gap-1">
          <span className="text-[11px] text-muted-foreground">{pt.feed.sort}</span>
          <Select
            value={search.sort}
            onValueChange={(v) => setSearch({ sort: v as ResultsSearch["sort"] })}
          >
            <SelectTrigger className="w-44" aria-label={pt.feed.sort}>
              <SelectValue placeholder={pt.feed.sort} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="newest">{pt.feed.sortNewest}</SelectItem>
              <SelectItem value="price_asc">{pt.feed.sortPriceAsc}</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {newCount > 0 ? (
        <div className="sticky top-20 z-20 flex justify-center">
          <Button
            size="sm"
            className="shadow-lg"
            onClick={() => {
              setNewCount(0);
              firstIdRef.current = items[0]?.id ?? null;
              window.scrollTo({ top: 0, behavior: "smooth" });
            }}
          >
            <ArrowUp className="mr-1 size-4" aria-hidden />
            {t(pt.feed.newItems, { n: newCount })}
          </Button>
        </div>
      ) : null}

      {feed.isLoading ? <LoadingList rows={5} /> : null}
      {feed.isError ? <ErrorState error={feed.error} onRetry={() => feed.refetch()} /> : null}

      {feed.data && items.length === 0 ? (
        <EmptyState
          icon={<Sparkles className="size-6" aria-hidden />}
          title={pt.feed.emptyTitle}
          description={pt.feed.emptyText}
        />
      ) : null}

      <div className="grid gap-3 sm:grid-cols-2">
        {items.map((item) => (
          <ItemCard
            key={item.id}
            item={item}
            highlight={highlightFor(item, bestDeals)}
            onSend={setSendItem}
          />
        ))}
      </div>

      {feed.hasNextPage ? (
        <div className="flex justify-center">
          <Button
            variant="outline"
            onClick={() => void feed.fetchNextPage()}
            disabled={feed.isFetchingNextPage}
          >
            {feed.isFetchingNextPage ? pt.common.loading : pt.common.loadMore}
          </Button>
        </div>
      ) : null}

      <SendToDestinationDialog
        item={sendItem}
        onOpenChange={(open) => !open && setSendItem(null)}
      />
    </div>
  );
}
