import { useQuery } from "@tanstack/react-query";

import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { ErrorState, LoadingBlock } from "@/components/states";
import { PriceHistoryChart } from "@/features/history/PriceHistoryChart";
import { api } from "@/lib/api";
import { qk } from "@/hooks/useGarimpo";
import { pt } from "@/i18n/pt";
import { formatDateTime } from "@/lib/format";
import type { Item } from "@/lib/api/types";

export function ItemHistoryDrawer({
  item,
  onOpenChange,
}: {
  item: Item | null;
  onOpenChange: (open: boolean) => void;
}) {
  const query = useQuery({
    queryKey: qk.history(item?.id ?? ""),
    queryFn: () => api.items.history(item!.id),
    enabled: Boolean(item),
  });

  return (
    <Sheet open={Boolean(item)} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full sm:max-w-lg">
        <SheetHeader>
          <SheetTitle className="text-left text-base">{item?.title}</SheetTitle>
          <SheetDescription className="text-left">
            {pt.history.firstSeen}: {formatDateTime(item?.firstSeenAt ?? null)}
          </SheetDescription>
        </SheetHeader>
        <div className="p-4">
          {query.isLoading ? <LoadingBlock /> : null}
          {query.isError ? (
            <ErrorState error={query.error} onRetry={() => query.refetch()} />
          ) : null}
          {query.data ? (
            <PriceHistoryChart points={query.data} currency={item?.currency ?? "EUR"} />
          ) : null}
        </div>
      </SheetContent>
    </Sheet>
  );
}
