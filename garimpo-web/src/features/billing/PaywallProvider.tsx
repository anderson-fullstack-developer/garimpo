"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { Loader2, Lock } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { errorMessage } from "@/components/states";
import { useAuth } from "@/features/auth/AuthProvider";
import { api } from "@/lib/api";
import { ApiError } from "@/lib/api/types";
import { pt } from "@/i18n/pt";

interface PaywallContextValue {
  /** Abre o pedido de assinatura (teste acabou ou o usuário quer assinar já). */
  open: () => void;
}

const PaywallContext = createContext<PaywallContextValue | null>(null);

/** Abre a Stripe: leva o usuário à página de pagamento (o app nunca toca no cartão). */
export async function startCheckout(): Promise<void> {
  try {
    const { url } = await api.billing.createCheckout("PRO", "month");
    window.location.assign(url);
  } catch (error) {
    if (error instanceof ApiError && error.code === "NOT_CONFIGURED") {
      toast.error(pt.trial.unavailable);
    } else {
      toast.error(errorMessage(error));
    }
    throw error;
  }
}

export function PaywallProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const openPaywall = useCallback(() => setOpen(true), []);
  const value = useMemo(() => ({ open: openPaywall }), [openPaywall]);
  const ended = !user?.hasAccess;

  return (
    <PaywallContext.Provider value={value}>
      {children}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <div className="mx-auto mb-2 grid size-10 place-items-center rounded-full bg-primary/10 text-primary">
              <Lock className="size-5" aria-hidden />
            </div>
            <DialogTitle className="text-center">
              {ended ? pt.trial.paywallTitle : pt.trial.cardTitle}
            </DialogTitle>
            <DialogDescription className="text-center">
              {ended ? pt.trial.paywallText : pt.trial.paywallTrialText}
            </DialogDescription>
          </DialogHeader>
          <div className="rounded-lg border border-border bg-muted/50 p-4 text-center">
            <p className="text-xl font-semibold">Garimpo Pro · {pt.trial.price}</p>
            <p className="mt-1 text-xs text-muted-foreground">{pt.trial.perks}</p>
          </div>
          <DialogFooter className="gap-2 sm:justify-center">
            <Button variant="ghost" onClick={() => setOpen(false)}>
              {pt.trial.notNow}
            </Button>
            <Button
              disabled={loading}
              onClick={async () => {
                setLoading(true);
                try {
                  await startCheckout();
                } catch {
                  setLoading(false);
                }
              }}
            >
              {loading ? <Loader2 className="mr-2 size-4 animate-spin" aria-hidden /> : null}
              {pt.trial.subscribeCta}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PaywallContext.Provider>
  );
}

export function usePaywall(): PaywallContextValue {
  const ctx = useContext(PaywallContext);
  if (!ctx) throw new Error("usePaywall precisa estar dentro de PaywallProvider");
  return ctx;
}
