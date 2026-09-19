"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Check } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ErrorState, LoadingList, PageHeader, errorMessage } from "@/components/states";
import { useSubscription, useUsage, useCheckout } from "@/hooks/useGarimpo";
import { useAuth } from "@/features/auth/AuthProvider";
import { entitlementsFor } from "@/lib/entitlements";
import { mockApproveCheckout } from "@/lib/api/mock";
import { USE_MOCK, api } from "@/lib/api";
import { PLANS } from "@/config/plans";
import { formatDate, formatInterval, formatMoney } from "@/lib/format";
import { pt, t } from "@/i18n/pt";
import { APP_NAME } from "@/config/brand";
import type { Plan } from "@/lib/api/types";

export function BillingPage() {
  const { user, reload } = useAuth();
  const queryClient = useQueryClient();
  const subscription = useSubscription();
  const usage = useUsage();
  const checkout = useCheckout();
  const [interval, setInterval] = useState<"month" | "year">("month");
  const [checkoutPlan, setCheckoutPlan] = useState<Plan | null>(null);

  const currentPlan = subscription.data?.plan ?? user?.plan ?? "FREE";
  const ent = entitlementsFor(currentPlan);

  const rows: { label: string; value: (plan: Plan) => string }[] = [
    {
      label: pt.billing.rowInterval,
      value: (p) => formatInterval(entitlementsFor(p).minIntervalMinutes),
    },
    { label: pt.billing.rowAlerts, value: (p) => String(entitlementsFor(p).maxAlerts) },
    { label: pt.billing.rowDestinations, value: (p) => String(entitlementsFor(p).maxDestinations) },
    { label: pt.billing.rowPriority, value: (p) => entitlementsFor(p).priority },
    { label: pt.billing.rowDomains, value: (p) => String(entitlementsFor(p).domains) },
    {
      label: pt.billing.rowHistory,
      value: (p) => {
        const days = entitlementsFor(p).historyDays;
        return days === null ? pt.billing.unlimited : `${days} dias`;
      },
    },
    { label: pt.billing.rowExtras, value: (p) => (p === "FREE" ? "—" : "Sim") },
  ];

  const startCheckout = async (plan: Plan) => {
    try {
      const { url } = await checkout.mutateAsync({ plan, interval });
      if (USE_MOCK || url.startsWith("mock://")) setCheckoutPlan(plan);
      else window.location.assign(url);
    } catch (error) {
      toast.error(errorMessage(error));
    }
  };

  return (
    <div className="space-y-5">
      <PageHeader
        title={pt.billing.title}
        subtitle={pt.billing.subtitle}
        actions={
          <div className="flex gap-1 rounded-lg border border-border p-1">
            <Button
              size="sm"
              variant={interval === "month" ? "secondary" : "ghost"}
              onClick={() => setInterval("month")}
            >
              {pt.billing.monthly}
            </Button>
            <Button
              size="sm"
              variant={interval === "year" ? "secondary" : "ghost"}
              onClick={() => setInterval("year")}
            >
              {pt.billing.yearly}
            </Button>
          </div>
        }
      />

      <div className="grid gap-4 md:grid-cols-3">
        {PLANS.map((plan) => (
          <article
            key={plan.id}
            className={
              plan.recommended ? "surface space-y-3 border-primary p-5" : "surface space-y-3 p-5"
            }
          >
            <div className="flex items-center justify-between gap-2">
              <h2 className="text-base font-semibold">{plan.name}</h2>
              {plan.id === currentPlan ? (
                <Badge>{pt.billing.current}</Badge>
              ) : plan.recommended ? (
                <Badge variant="secondary">{pt.billing.recommended}</Badge>
              ) : null}
            </div>
            <p className="text-2xl font-semibold">
              {formatMoney(interval === "month" ? plan.monthly : plan.yearly)}
              <span className="text-sm font-normal text-muted-foreground">
                {interval === "month" ? pt.billing.perMonth : pt.billing.perYear}
              </span>
            </p>
            <p className="text-sm text-muted-foreground">{plan.description}</p>
            {interval === "year" && plan.monthly > 0 ? (
              <p className="text-xs text-primary">{pt.billing.yearlyHint}</p>
            ) : null}
            {plan.id === currentPlan && plan.id === "FREE" ? (
              <Button variant="outline" className="w-full" disabled>
                {pt.billing.current}
              </Button>
            ) : plan.id === currentPlan ? (
              <Button
                variant="outline"
                className="w-full"
                onClick={async () => {
                  const { url } = await api.billing.createPortal();
                  if (!url.startsWith("mock://")) window.location.assign(url);
                  else toast.info(pt.billing.checkoutText);
                }}
              >
                {pt.billing.managePlan}
              </Button>
            ) : (
              <Button className="w-full" onClick={() => void startCheckout(plan.id)}>
                {t(pt.billing.subscribe, { plan: plan.name })}
              </Button>
            )}
          </article>
        ))}
      </div>

      <div className="surface overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Recurso</TableHead>
              {PLANS.map((plan) => (
                <TableHead key={plan.id}>{plan.name}</TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.label}>
                <TableCell className="font-medium">{row.label}</TableCell>
                {PLANS.map((plan) => (
                  <TableCell key={plan.id}>{row.value(plan.id)}</TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <section className="surface space-y-4 p-5">
        <h2 className="text-sm font-semibold">{pt.billing.usageTitle}</h2>
        {usage.isLoading || subscription.isLoading ? <LoadingList rows={2} /> : null}
        {usage.isError ? <ErrorState error={usage.error} onRetry={() => usage.refetch()} /> : null}
        {usage.data ? (
          <div className="space-y-4">
            <div className="space-y-1">
              <p className="text-sm">
                {t(pt.alerts.usage, { used: usage.data.alerts, max: ent.maxAlerts })}
              </p>
              <Progress value={Math.min(100, (usage.data.alerts / ent.maxAlerts) * 100)} />
            </div>
            <div className="space-y-1">
              <p className="text-sm">
                {t(pt.destinations.usage, {
                  used: usage.data.destinations,
                  max: ent.maxDestinations,
                })}
              </p>
              <Progress
                value={Math.min(100, (usage.data.destinations / ent.maxDestinations) * 100)}
              />
            </div>
            {subscription.data?.currentPeriodEnd ? (
              <p className="text-sm text-muted-foreground">
                {subscription.data.cancelAtPeriodEnd
                  ? pt.billing.cancelScheduled
                  : pt.billing.nextCharge}
                : {formatDate(subscription.data.currentPeriodEnd)}
              </p>
            ) : null}
          </div>
        ) : null}
      </section>

      <Dialog open={Boolean(checkoutPlan)} onOpenChange={(open) => !open && setCheckoutPlan(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{pt.billing.checkoutTitle}</DialogTitle>
            <DialogDescription>{pt.billing.checkoutText}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCheckoutPlan(null)}>
              {pt.common.cancel}
            </Button>
            <Button
              onClick={async () => {
                if (checkoutPlan) mockApproveCheckout(checkoutPlan);
                setCheckoutPlan(null);
                await reload();
                await queryClient.invalidateQueries();
                toast.success(pt.misc.planUpdated);
              }}
            >
              <Check className="mr-1 size-4" aria-hidden /> {pt.billing.checkoutApprove}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
