"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { errorMessage } from "@/components/states";
import { useAuth } from "@/features/auth/AuthProvider";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { pt, t } from "@/i18n/pt";
import { usePaywall } from "./PaywallProvider";

export function SubscriptionCard() {
  const { user } = useAuth();
  const paywall = usePaywall();
  const [loading, setLoading] = useState(false);
  if (!user) return null;

  const status = user.subscriptionStatus;
  const subscribed = ["active", "trialing", "past_due"].includes(status ?? "");
  const line = subscribed
    ? status === "past_due"
      ? pt.trial.statusPastDue
      : pt.trial.statusActive
    : status === "canceled"
      ? pt.trial.statusCanceled
      : user.hasAccess && user.trialEndsAt
        ? t(pt.trial.statusTrial, { date: formatDate(user.trialEndsAt) })
        : pt.trial.statusNone;

  const manage = async () => {
    setLoading(true);
    try {
      const { url } = await api.billing.createPortal();
      window.location.assign(url);
    } catch (error) {
      toast.error(errorMessage(error));
      setLoading(false);
    }
  };

  return (
    <div className="surface flex flex-wrap items-center justify-between gap-3 p-5">
      <div className="space-y-1">
        <h2 className="text-sm font-semibold">{pt.trial.cardTitle}</h2>
        <p className="text-sm text-muted-foreground">{line}</p>
      </div>
      {subscribed ? (
        <Button variant="outline" disabled={loading} onClick={() => void manage()}>
          {pt.trial.manage}
        </Button>
      ) : (
        <Button onClick={paywall.open}>{pt.trial.subscribe}</Button>
      )}
    </div>
  );
}
