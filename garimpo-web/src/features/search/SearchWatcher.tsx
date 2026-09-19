"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useRef } from "react";
import { toast } from "sonner";

import { usePaywall } from "@/features/billing/PaywallProvider";
import { pt, t } from "@/i18n/pt";
import { useManualSearch } from "./useManualSearch";

const ACK_KEY = "garimpo.search.ack";
const FRESH_MS = 15 * 60 * 1000;

function acked(): string | null {
  try {
    return localStorage.getItem(ACK_KEY);
  } catch {
    return null;
  }
}

function ack(value: string): void {
  try {
    localStorage.setItem(ACK_KEY, value);
  } catch {
    /* sem armazenamento: pode avisar de novo, sem problema */
  }
}

/**
 * Fica na área logada. Enquanto a busca contínua roda, atualiza a lista quando aparece anúncio novo;
 * quando ela para (inclusive com o usuário em outra página), avisa uma única vez.
 */
export function SearchWatcher() {
  const qc = useQueryClient();
  const router = useRouter();
  const paywall = usePaywall();
  const { status } = useManualSearch(); // mantém a consulta ativa (a cada 2 s enquanto roda)
  const lastNew = useRef<number | null>(null);

  const state = status?.state;
  const newItems = status?.newItems ?? 0;
  const finishedAt = status?.finishedAt;

  // Chegou anúncio novo: recarrega Resultados na hora.
  useEffect(() => {
    if (state !== "running" && state !== "stopping") {
      lastNew.current = null;
      return;
    }
    if (lastNew.current !== null && newItems !== lastNew.current) {
      void qc.invalidateQueries({ queryKey: ["items"] });
    }
    lastNew.current = newItems;
  }, [state, newItems, qc]);

  // A busca terminou: avisa uma vez.
  useEffect(() => {
    if (!status || !finishedAt || (state !== "done" && state !== "error")) return;
    if (acked() === finishedAt) return;
    ack(finishedAt);
    void qc.invalidateQueries({ queryKey: ["items"] });
    if (Date.now() - new Date(finishedAt).getTime() > FRESH_MS) return; // resultado antigo: não incomoda
    if (state === "error" && status.error?.code === "SUBSCRIPTION_REQUIRED") {
      paywall.open(); // o teste acabou com a busca rodando
    } else if (state === "error") {
      toast.error(status.error?.message ?? pt.alerts.searchFailed);
    } else {
      toast.success(t(pt.alerts.searchStopped, { n: status.newItems }), {
        action: { label: pt.alerts.viewResults, onClick: () => router.push("/app/results") },
      });
    }
  }, [status, state, finishedAt, qc, router, paywall]);

  return null;
}
