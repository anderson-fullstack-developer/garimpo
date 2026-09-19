"use client";

import { useEffect, useState } from "react";
import { Clock, Lock } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/features/auth/AuthProvider";
import { cn } from "@/lib/utils";
import { pt } from "@/i18n/pt";
import { usePaywall } from "./PaywallProvider";

const pad = (n: number) => String(n).padStart(2, "0");

/** 6d 23h 14min 05s */
export function formatCountdown(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  const days = Math.floor(total / 86400);
  const hours = Math.floor((total % 86400) / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const seconds = total % 60;
  const t = pt.trial;
  return `${days}${t.d} ${pad(hours)}${t.h} ${pad(minutes)}${t.m} ${pad(seconds)}${t.s}`;
}

/**
 * Faixa no topo do app: contagem regressiva do teste grátis (dias, horas, minutos e segundos).
 * Depois que acaba, vira o aviso "teste terminou" com o botão de assinar.
 */
export function TrialBanner() {
  const { user } = useAuth();
  const paywall = usePaywall();
  const [now, setNow] = useState<number | null>(null); // só no navegador (evita diferença com o servidor)

  useEffect(() => {
    setNow(Date.now());
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  if (!user || now === null || user.role === "ADMIN") return null;
  const paid = ["active", "trialing"].includes(user.subscriptionStatus ?? "");
  if (paid || !user.trialEndsAt) return null;

  const left = new Date(user.trialEndsAt).getTime() - now;
  const ended = left <= 0;
  const urgent = !ended && left < 24 * 3600 * 1000;

  return (
    <div className="px-4 pt-3">
      <div
        role={ended ? "alert" : "status"}
        className={cn(
          "flex flex-wrap items-center justify-between gap-2 rounded-lg border px-3 py-2 text-sm",
          ended
            ? "border-destructive/40 bg-destructive/10 text-destructive"
            : urgent
              ? "border-amber-500/40 bg-amber-500/10 text-amber-900 dark:text-amber-200"
              : "border-primary/30 bg-primary/10 text-foreground",
        )}
      >
        <span className="inline-flex items-center gap-2 font-medium">
          {ended ? (
            <Lock className="size-4" aria-hidden />
          ) : (
            <Clock className="size-4" aria-hidden />
          )}
          {ended ? (
            pt.trial.ended
          ) : (
            <>
              {pt.trial.left}{" "}
              <span className="font-mono tabular-nums" aria-live="off">
                {formatCountdown(left)}
              </span>
            </>
          )}
        </span>
        <Button size="sm" variant={ended ? "default" : "secondary"} onClick={paywall.open}>
          {pt.trial.subscribe}
        </Button>
      </div>
    </div>
  );
}
