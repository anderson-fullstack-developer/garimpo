import Link from "next/link";
import { Send } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { errorMessage } from "@/components/states";
import { useAuth } from "@/features/auth/AuthProvider";
import { usePaywall } from "@/features/billing/PaywallProvider";
import { ApiError } from "@/lib/api/types";
import { useDestinations, useMonitor, useMonitorMutations } from "@/hooks/useGarimpo";
import { relativeTime } from "@/lib/format";
import { pt, t } from "@/i18n/pt";

/** Liga/desliga o monitor automático e mostra para onde os avisos estão indo. */
export function MonitorCard() {
  const { data: monitor } = useMonitor();
  const { data: destinations } = useDestinations();
  const { start, stop } = useMonitorMutations();
  const { user } = useAuth();
  const paywall = usePaywall();

  const enabled = monitor?.enabled ?? false;
  const busy = start.isPending || stop.isPending;
  const linked = (destinations ?? []).filter((d) => d.status === "LINKED");
  const target = linked.find((d) => d.isDefault) ?? linked[0];

  const toggle = (next: boolean) => {
    if (next && user && !user.hasAccess) return paywall.open(); // teste acabou: pede a assinatura
    (next ? start : stop).mutate(undefined, {
      onError: (error) => {
        if (error instanceof ApiError && error.code === "SUBSCRIPTION_REQUIRED") paywall.open();
        else toast.error(errorMessage(error));
      },
    });
  };

  return (
    <section className="surface space-y-3 p-4">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 space-y-1">
          <h2 className="text-sm font-semibold">{pt.alerts.monitorTitle}</h2>
          <p className="text-sm text-muted-foreground">
            {enabled ? pt.alerts.monitorOnText : pt.alerts.monitorOffText}
          </p>
          {enabled && monitor?.lastRunAt ? (
            <p className="text-xs text-muted-foreground">
              {t(pt.alerts.lastCheck, { when: relativeTime(monitor.lastRunAt) })}
            </p>
          ) : null}
        </div>
        <Switch
          checked={enabled}
          disabled={!monitor || busy}
          onCheckedChange={toggle}
          aria-label={pt.alerts.monitorTitle}
        />
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border pt-3 text-sm">
        <span className="inline-flex items-center gap-2 text-muted-foreground">
          <Send className="size-4" aria-hidden />
          {target
            ? t(pt.alerts.telegramConnected, { name: target.title ?? target.channel })
            : pt.alerts.telegramNone}
        </span>
        {!target && destinations ? (
          <Button asChild size="sm" variant="outline">
            <Link href="/app/settings?tab=telegram">{pt.alerts.telegramConnect}</Link>
          </Button>
        ) : null}
      </div>
    </section>
  );
}
