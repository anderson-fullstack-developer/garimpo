"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { toast } from "sonner";

import { errorMessage } from "@/components/states";
import { useAuth } from "@/features/auth/AuthProvider";
import { usePaywall } from "@/features/billing/PaywallProvider";
import { api } from "@/lib/api";
import { ApiError } from "@/lib/api/types";
import type { SearchStatus } from "@/lib/api/types";

export const searchKey = ["search"] as const;

const BUSY = ["running", "stopping"];

/**
 * Botão "Buscar": liga uma busca contínua no servidor, que segue até alguém mandar parar.
 * Sair da página ou recarregar não a interrompe; qualquer página vê o botão girando.
 */
export function useManualSearch() {
  const qc = useQueryClient();
  const { user } = useAuth();
  const paywall = usePaywall();
  const status = useQuery({
    queryKey: searchKey,
    queryFn: () => api.search.status(),
    refetchInterval: (query) => (BUSY.includes(query.state.data?.state ?? "") ? 2000 : false),
  });
  const start = useMutation({
    mutationFn: () => api.search.run({ mode: "alerts" }),
    onSuccess: (data: SearchStatus) => qc.setQueryData(searchKey, data),
    onError: (error) => {
      if (error instanceof ApiError && error.code === "SUBSCRIPTION_REQUIRED") paywall.open();
      else toast.error(errorMessage(error));
    },
  });
  const stop = useMutation({
    mutationFn: () => api.search.stop(),
    onSuccess: (data: SearchStatus) => qc.setQueryData(searchKey, data),
  });
  const state = status.data?.state;
  // "Parando" já conta como parado para o usuário: o texto volta a "Buscar agora" no mesmo instante.
  const running = (state === "running" && !stop.isPending) || start.isPending;
  return {
    running,
    /** Um clique liga; outro clique desliga. */
    toggle: () => {
      if (running) return stop.mutate();
      if (user && !user.hasAccess) return paywall.open(); // teste acabou: pede a assinatura
      start.mutate();
    },
    status: status.data,
  };
}
