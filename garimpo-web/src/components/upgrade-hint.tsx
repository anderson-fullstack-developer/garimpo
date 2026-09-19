import Link from "next/link";
import { Sparkles } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { FEATURES } from "@/config/features";
import { pt } from "@/i18n/pt";
import { useAuth } from "@/features/auth/AuthProvider";
import { entitlementsFor, nextPlan } from "@/lib/entitlements";
import { formatInterval } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Plan } from "@/lib/api/types";

export type UpgradeFeature =
  "minInterval" | "maxAlerts" | "maxDestinations" | "historyDays" | "maxPages";

function describe(feature: UpgradeFeature, plan: Plan): string {
  const ent = entitlementsFor(plan);
  switch (feature) {
    case "minInterval":
      return `No plano ${plan} verificamos a cada ${formatInterval(ent.minIntervalMinutes)}`;
    case "maxAlerts":
      return `No plano ${plan} você cria até ${ent.maxAlerts} alertas`;
    case "maxDestinations":
      return `No plano ${plan} você conecta até ${ent.maxDestinations} destinos`;
    case "maxPages":
      return `No plano ${plan} varremos até ${ent.maxPages} páginas`;
    case "historyDays":
      return ent.historyDays === null
        ? `No plano ${plan} o histórico é ilimitado`
        : `No plano ${plan} o histórico vai até ${ent.historyDays} dias`;
  }
}

export function UpgradeHint({
  feature,
  className,
}: {
  feature: UpgradeFeature;
  className?: string;
}) {
  const { user } = useAuth();
  const target = nextPlan(user?.plan ?? "FREE");
  if (!FEATURES.billing || !target) return null;

  return (
    <div
      className={cn(
        "flex flex-wrap items-center justify-between gap-2 rounded-lg border border-primary/30 bg-accent/60 px-3 py-2 text-sm",
        className,
      )}
    >
      <span className="inline-flex items-center gap-2 text-accent-foreground">
        <Sparkles className="size-4" aria-hidden />
        {describe(feature, target)}
      </span>
      <Button asChild size="sm" variant="default">
        <Link href="/app/billing">{pt.banners.planLimitCta}</Link>
      </Button>
    </div>
  );
}

export function PlanGate({
  plan,
  feature,
  children,
}: {
  plan: Plan;
  feature: UpgradeFeature;
  children: ReactNode;
}) {
  const { user } = useAuth();
  const order: Plan[] = ["FREE", "PRO", "ELITE"];
  const allowed = order.indexOf(user?.plan ?? "FREE") >= order.indexOf(plan);
  if (allowed) return <>{children}</>;
  return (
    <div className="space-y-2">
      <div className="pointer-events-none opacity-40" aria-hidden>
        {children}
      </div>
      <UpgradeHint feature={feature} />
    </div>
  );
}
