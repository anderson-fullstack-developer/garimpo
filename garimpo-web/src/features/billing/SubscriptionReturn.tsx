"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef } from "react";
import { toast } from "sonner";

import { useAuth } from "@/features/auth/AuthProvider";
import { pt } from "@/i18n/pt";

/** Na volta do pagamento, espera a Stripe avisar o servidor (alguns segundos) e confirma na tela. */
export function SubscriptionReturn() {
  const params = useSearchParams();
  const router = useRouter();
  const { user, reload } = useAuth();
  const handled = useRef(false);
  const subscribed = params.get("subscribed") === "1";
  const canceled = params.get("canceled") === "1";
  const active = ["active", "trialing"].includes(user?.subscriptionStatus ?? "");

  useEffect(() => {
    if (!canceled || handled.current) return;
    handled.current = true;
    toast.message(pt.trial.canceledReturn);
    router.replace("/app/results");
  }, [canceled, router]);

  useEffect(() => {
    if (!subscribed || active) return;
    const timer = window.setInterval(() => void reload(), 2000);
    const stop = window.setTimeout(() => window.clearInterval(timer), 45000);
    return () => {
      window.clearInterval(timer);
      window.clearTimeout(stop);
    };
  }, [subscribed, active, reload]);

  useEffect(() => {
    if (!subscribed || !active || handled.current) return;
    handled.current = true;
    toast.success(pt.trial.thanks);
    router.replace("/app/results");
  }, [subscribed, active, router]);

  return null;
}
