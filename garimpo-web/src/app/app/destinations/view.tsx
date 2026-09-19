"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { MoreHorizontal, Plus, Send, Star } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { EmptyState, ErrorState, LoadingList, PageHeader, errorMessage } from "@/components/states";
import { UpgradeHint } from "@/components/upgrade-hint";
import { FEATURES } from "@/config/features";
import { LinkWizard } from "@/features/destinations/LinkWizard";
import { qk, useDestinations } from "@/hooks/useGarimpo";
import { useAuth } from "@/features/auth/AuthProvider";
import { entitlementsFor } from "@/lib/entitlements";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { pt, t } from "@/i18n/pt";
import { APP_NAME } from "@/config/brand";

const statusLabel = () =>
  ({
    LINKED: pt.destinations.statusLINKED,
    PENDING: pt.destinations.statusPENDING,
    DISCONNECTED: pt.destinations.statusDISCONNECTED,
  }) as const;

const kindLabel = () =>
  ({
    PRIVATE: pt.destinations.kindPRIVATE,
    GROUP: pt.destinations.kindGROUP,
    CHANNEL: pt.destinations.kindCHANNEL,
  }) as const;

/** `embedded`: usado dentro de Configurações (sem título de página próprio). */
export function DestinationsPage({ embedded = false }: { embedded?: boolean }) {
  const { user } = useAuth();
  const destinations = useDestinations();
  const queryClient = useQueryClient();
  const [wizardOpen, setWizardOpen] = useState(false);

  const ent = entitlementsFor(user?.plan ?? "FREE");
  const used = (destinations.data ?? []).filter((d) => d.status !== "PENDING").length;
  const limitReached = used >= ent.maxDestinations;
  const refresh = () => void queryClient.invalidateQueries({ queryKey: qk.destinations });

  return (
    <div className="space-y-5">
      {embedded ? (
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm text-muted-foreground">{pt.destinations.subtitle}</p>
          <Button onClick={() => setWizardOpen(true)} disabled={limitReached}>
            <Plus className="mr-1 size-4" aria-hidden /> {pt.destinations.connect}
          </Button>
        </div>
      ) : (
        <PageHeader
          title={pt.destinations.title}
          subtitle={pt.destinations.subtitle}
          actions={
            <Button onClick={() => setWizardOpen(true)} disabled={limitReached}>
              <Plus className="mr-1 size-4" aria-hidden /> {pt.destinations.connect}
            </Button>
          }
        />
      )}

      {FEATURES.billing ? (
        <div className="surface space-y-2 p-4">
          <div className="flex items-center justify-between text-sm">
            <span>{t(pt.destinations.usage, { used, max: ent.maxDestinations })}</span>
            <Badge variant="secondary">{user?.plan}</Badge>
          </div>
          <Progress value={Math.min(100, (used / ent.maxDestinations) * 100)} />
          {limitReached ? <UpgradeHint feature="maxDestinations" /> : null}
        </div>
      ) : null}

      {destinations.isLoading ? <LoadingList rows={2} /> : null}
      {destinations.isError ? (
        <ErrorState error={destinations.error} onRetry={() => destinations.refetch()} />
      ) : null}

      {destinations.data && destinations.data.length === 0 ? (
        <EmptyState
          icon={<Send className="size-6" aria-hidden />}
          title={pt.destinations.emptyTitle}
          description={pt.destinations.emptyText}
          action={<Button onClick={() => setWizardOpen(true)}>{pt.destinations.connect}</Button>}
        />
      ) : null}

      <div className="grid gap-3">
        {(destinations.data ?? []).map((destination) => (
          <article key={destination.id} className="surface flex flex-wrap items-center gap-3 p-4">
            <div className="min-w-0 flex-1 space-y-1">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="truncate text-sm font-semibold">
                  {destination.title ?? destination.channel}
                </h2>
                {destination.isDefault ? (
                  <Badge className="gap-1">
                    <Star className="size-3" aria-hidden /> {pt.destinations.default}
                  </Badge>
                ) : null}
                <Badge variant={destination.status === "LINKED" ? "secondary" : "outline"}>
                  {statusLabel()[destination.status]}
                </Badge>
              </div>
              <p className="text-xs text-muted-foreground">
                {destination.channel} · {destination.kind ? kindLabel()[destination.kind] : "—"} ·{" "}
                {pt.destinations.linkedAt} {formatDate(destination.linkedAt)}
              </p>
            </div>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={t(pt.misc.actionsFor, { name: destination.title ?? destination.id })}
                >
                  <MoreHorizontal className="size-4" aria-hidden />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem
                  onSelect={async () => {
                    const title = window.prompt(pt.destinations.rename, destination.title ?? "");
                    if (!title) return;
                    await api.destinations.update(destination.id, { title });
                    refresh();
                  }}
                >
                  {pt.destinations.rename}
                </DropdownMenuItem>
                <DropdownMenuItem
                  onSelect={async () => {
                    await api.destinations.update(destination.id, { isDefault: true });
                    refresh();
                  }}
                >
                  {pt.destinations.setDefault}
                </DropdownMenuItem>
                <DropdownMenuItem
                  onSelect={async () => {
                    try {
                      await api.destinations.test(destination.id);
                      toast.success(pt.destinations.testSent);
                    } catch (error) {
                      toast.error(errorMessage(error));
                    }
                  }}
                >
                  {pt.destinations.sendTest}
                </DropdownMenuItem>
                <DropdownMenuItem
                  onSelect={async () => {
                    await api.destinations.remove(destination.id);
                    refresh();
                  }}
                >
                  {pt.destinations.unlink}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </article>
        ))}
      </div>

      <LinkWizard open={wizardOpen} onOpenChange={setWizardOpen} />
    </div>
  );
}
