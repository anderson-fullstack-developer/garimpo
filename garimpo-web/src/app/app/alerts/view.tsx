"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { MoreHorizontal, Plus, Search, Siren } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Switch } from "@/components/ui/switch";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { EmptyState, ErrorState, LoadingList, PageHeader, errorMessage } from "@/components/states";
import { UpgradeHint } from "@/components/upgrade-hint";
import { countryLabel } from "@/config/countries";
import { FEATURES } from "@/config/features";
import { MonitorCard } from "@/features/alerts/MonitorCard";
import { useAlertMutations, useAlerts, useDestinations } from "@/hooks/useGarimpo";
import { SearchButton } from "@/features/search/SearchButton";
import { useAuth } from "@/features/auth/AuthProvider";
import { api } from "@/lib/api";
import { entitlementsFor } from "@/lib/entitlements";
import { formatMoney } from "@/lib/format";
import { pt, t } from "@/i18n/pt";

export function AlertsPage() {
  const { user } = useAuth();
  const router = useRouter();
  const alerts = useAlerts();
  const { data: destinations } = useDestinations();
  const { toggle, remove, duplicate } = useAlertMutations();
  const [deleteId, setDeleteId] = useState<string | null>(null);

  const ent = entitlementsFor(user?.plan ?? "FREE");
  const used = alerts.data?.length ?? 0;
  const limitReached = used >= ent.maxAlerts;

  const destinationName = (id: string | null) =>
    destinations?.find((d) => d.id === id)?.title ?? pt.alerts.noDestination;

  return (
    <div className="space-y-5">
      <PageHeader
        title={pt.alerts.title}
        subtitle={pt.alerts.subtitle}
        actions={
          <>
            <SearchButton variant="outline" disabled={used === 0} />
            {limitReached ? (
              <Button disabled>
                <Plus className="mr-1 size-4" aria-hidden /> {pt.alerts.newAlert}
              </Button>
            ) : (
              <Button asChild>
                <Link href="/app/alerts/new">
                  <Plus className="mr-1 size-4" aria-hidden /> {pt.alerts.newAlert}
                </Link>
              </Button>
            )}
          </>
        }
      />

      <MonitorCard />

      {limitReached ? (
        <div className="surface space-y-2 p-4">
          <p className="text-sm text-muted-foreground">{pt.alerts.limitReached}</p>
          <UpgradeHint feature="maxAlerts" />
        </div>
      ) : null}

      {FEATURES.billing ? (
        <div className="surface space-y-2 p-4">
          <div className="flex items-center justify-between text-sm">
            <span>{t(pt.alerts.usage, { used, max: ent.maxAlerts })}</span>
            <Badge variant="secondary">{user?.plan}</Badge>
          </div>
          <Progress value={Math.min(100, (used / ent.maxAlerts) * 100)} />
        </div>
      ) : null}

      {alerts.isLoading ? <LoadingList /> : null}
      {alerts.isError ? <ErrorState error={alerts.error} onRetry={() => alerts.refetch()} /> : null}

      {alerts.data && alerts.data.length === 0 ? (
        <EmptyState
          icon={<Siren className="size-6" aria-hidden />}
          title={pt.alerts.emptyTitle}
          description={pt.alerts.emptyText}
          action={
            <Button asChild>
              <Link href="/app/alerts/new">{pt.alerts.emptyCta}</Link>
            </Button>
          }
        />
      ) : null}

      <div className="grid gap-3">
        {(alerts.data ?? []).map((alert) => (
          <article key={alert.id} className="surface flex flex-wrap items-center gap-3 p-4">
            <div className="min-w-0 flex-1 space-y-1">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="truncate text-sm font-semibold">{alert.name}</h2>
                <Badge variant={alert.active ? "default" : "secondary"}>
                  {alert.active ? pt.alerts.active : pt.alerts.paused}
                </Badge>
                {alert.newToday > 0 ? (
                  <Link href={`/app/results?alert=${alert.id}`}>
                    <Badge variant="outline">
                      {alert.newToday} {pt.alerts.newToday}
                    </Badge>
                  </Link>
                ) : null}
              </div>
              <p className="text-xs text-muted-foreground">
                {alert.query} · {formatMoney(alert.minPrice)} —{" "}
                {alert.maxPrice ? formatMoney(alert.maxPrice) : "∞"} · {countryLabel(alert.country)}{" "}
                · {destinationName(alert.destinationId)}
              </p>
            </div>

            <Switch
              checked={alert.active}
              aria-label={`${pt.alerts.active}: ${alert.name}`}
              onCheckedChange={(active) => toggle.mutate({ id: alert.id, active })}
            />

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={t(pt.misc.actionsFor, { name: alert.name })}
                >
                  <MoreHorizontal className="size-4" aria-hidden />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem asChild>
                  <Link href={`/app/alerts/${alert.id}`}>{pt.common.edit}</Link>
                </DropdownMenuItem>
                <DropdownMenuItem asChild>
                  <Link href={`/app/results?alert=${alert.id}`}>{pt.alerts.viewResults}</Link>
                </DropdownMenuItem>
                <DropdownMenuItem
                  onSelect={() =>
                    duplicate.mutate(alert.id, {
                      onError: (error) => toast.error(errorMessage(error)),
                      onSuccess: () => toast.success(pt.misc.alertDuplicated),
                    })
                  }
                >
                  {pt.common.duplicate}
                </DropdownMenuItem>
                <DropdownMenuItem onSelect={() => setDeleteId(alert.id)}>
                  {pt.common.delete}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </article>
        ))}
      </div>

      <AlertDialog open={Boolean(deleteId)} onOpenChange={(open) => !open && setDeleteId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{pt.alerts.deleteTitle}</AlertDialogTitle>
            <AlertDialogDescription>{pt.alerts.deleteText}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{pt.common.cancel}</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (!deleteId) return;
                remove.mutate(deleteId, {
                  onSuccess: () => toast.success(pt.misc.alertDeleted),
                  onError: (error) => toast.error(errorMessage(error)),
                });
                setDeleteId(null);
              }}
            >
              {pt.common.delete}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
