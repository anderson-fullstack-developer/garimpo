import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { Alert, AlertInput, ItemQuery, MonitorStatus, Plan, Settings } from "@/lib/api/types";

export const qk = {
  publicConfig: ["publicConfig"] as const,
  alerts: ["alerts"] as const,
  alert: (id: string) => ["alerts", id] as const,
  presets: ["alerts", "presets"] as const,
  channels: ["channels"] as const,
  destinations: ["destinations"] as const,
  items: (q: ItemQuery) => ["items", q] as const,
  history: (id: string) => ["history", id] as const,
  monitor: ["monitor"] as const,
  settings: ["settings"] as const,
  subscription: ["billing", "subscription"] as const,
  usage: ["billing", "usage"] as const,
  adminUsers: (q?: string) => ["admin", "users", q ?? ""] as const,
  adminInvites: ["admin", "invites"] as const,
  adminRuns: (status?: string) => ["admin", "runs", status ?? ""] as const,
  adminStats: ["admin", "stats"] as const,
};

export const usePublicConfig = () =>
  useQuery({ queryKey: qk.publicConfig, queryFn: () => api.publicConfig() });

export const useAlerts = () => useQuery({ queryKey: qk.alerts, queryFn: () => api.alerts.list() });

export const useAlert = (id: string | undefined) =>
  useQuery({
    queryKey: qk.alert(id ?? ""),
    queryFn: () => api.alerts.get(id!),
    enabled: Boolean(id),
  });

export const usePresets = () =>
  useQuery({ queryKey: qk.presets, queryFn: () => api.alerts.presets(), staleTime: Infinity });

export const useChannels = () =>
  useQuery({ queryKey: qk.channels, queryFn: () => api.channels.list(), staleTime: Infinity });

export const useDestinations = (pollMs?: number) =>
  useQuery({
    queryKey: qk.destinations,
    queryFn: () => api.destinations.list(),
    ...(pollMs ? { refetchInterval: pollMs } : {}),
  });

export const useMonitor = () =>
  useQuery({ queryKey: qk.monitor, queryFn: () => api.monitor.status(), refetchInterval: 30000 });

export const useSettings = () =>
  useQuery({ queryKey: qk.settings, queryFn: () => api.settings.get() });

export const useSubscription = () =>
  useQuery({ queryKey: qk.subscription, queryFn: () => api.billing.subscription() });

export const useUsage = () => useQuery({ queryKey: qk.usage, queryFn: () => api.billing.usage() });

export function useAlertMutations() {
  const qc = useQueryClient();
  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: qk.alerts });
    void qc.invalidateQueries({ queryKey: qk.usage });
  };

  return {
    create: useMutation({
      mutationFn: (input: AlertInput) => api.alerts.create(input),
      onSuccess: invalidate,
    }),
    update: useMutation({
      mutationFn: ({ id, input }: { id: string; input: Partial<AlertInput> }) =>
        api.alerts.update(id, input),
      onSuccess: invalidate,
    }),
    remove: useMutation({
      mutationFn: (id: string) => api.alerts.remove(id),
      onSuccess: invalidate,
    }),
    duplicate: useMutation({
      mutationFn: (id: string) => api.alerts.duplicate(id),
      onSuccess: invalidate,
    }),
    toggle: useMutation({
      mutationFn: ({ id, active }: { id: string; active: boolean }) =>
        api.alerts.update(id, { active }),
      onMutate: async ({ id, active }) => {
        await qc.cancelQueries({ queryKey: qk.alerts });
        const previous = qc.getQueryData<Alert[]>(qk.alerts);
        qc.setQueryData<Alert[]>(qk.alerts, (old) =>
          old?.map((a) => (a.id === id ? { ...a, active } : a)),
        );
        return { previous };
      },
      onError: (_e, _v, context) => {
        if (context?.previous) qc.setQueryData(qk.alerts, context.previous);
      },
      onSettled: invalidate,
    }),
  };
}

export function useSettingsMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (patch: Partial<Settings>) => api.settings.update(patch),
    onSuccess: (data) => {
      qc.setQueryData(qk.settings, data);
      void qc.invalidateQueries({ queryKey: qk.monitor });
    },
  });
}

export function useMonitorMutations() {
  const qc = useQueryClient();

  /** Atualiza a tela na hora e desfaz se o servidor recusar. */
  const optimistic = (enabled: boolean) => ({
    onMutate: async () => {
      await qc.cancelQueries({ queryKey: qk.monitor });
      const previous = qc.getQueryData<MonitorStatus>(qk.monitor);
      qc.setQueryData<MonitorStatus>(qk.monitor, (old) =>
        old ? { ...old, enabled, state: enabled ? "ACTIVE" : "PAUSED" } : old,
      );
      return { previous };
    },
    onError: (_error: unknown, _vars: void, context?: { previous?: MonitorStatus | undefined }) => {
      if (context?.previous) qc.setQueryData(qk.monitor, context.previous);
    },
    onSettled: () => void qc.invalidateQueries({ queryKey: qk.monitor }),
  });

  return {
    start: useMutation({ mutationFn: () => api.monitor.start(), ...optimistic(true) }),
    stop: useMutation({ mutationFn: () => api.monitor.stop(), ...optimistic(false) }),
  };
}

export function useCheckout() {
  return useMutation({
    mutationFn: ({ plan, interval }: { plan: Plan; interval: "month" | "year" }) =>
      api.billing.createCheckout(plan, interval),
  });
}
