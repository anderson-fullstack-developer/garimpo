import { ApiError } from "./types";
import type {
  AdminUser,
  AdminUserNotifications,
  Alert,
  AlertInput,
  Api,
  AdminOverview,
  AdminRun,
  ChannelInfo,
  Destination,
  ExcludePresetInfo,
  ItemPage,
  ItemQuery,
  LinkCode,
  MonitorRun,
  MonitorStatus,
  SearchStatus,
  Plan,
  PreviewResult,
  PricePoint,
  PublicConfig,
  Settings,
  Subscription,
  Usage,
  User,
  UserStatus,
} from "./types";

// Só o acesso literal `process.env.NEXT_PUBLIC_*` é substituído pelo Next no build.
const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "/api";

type Method = "GET" | "POST" | "PATCH" | "DELETE";

interface RequestOptions {
  method?: Method | undefined;
  body?: unknown;
  query?: Record<string, unknown> | undefined;
  /** Não tenta renovar a sessão em 401 (login, cadastro, refresh...). */
  skipRefresh?: boolean | undefined;
  /** Em 401 não redireciona para /login (ex.: sondagem de sessão no carregamento). */
  silent?: boolean | undefined;
}

/** Endpoints em que um 401 significa "credencial inválida", nunca "sessão expirada". */
const AUTH: RequestOptions = { skipRefresh: true, silent: true };

function buildUrl(path: string, query?: Record<string, unknown>): string {
  const url = `${BASE_URL}${path}`;
  if (!query) return url;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null) continue;
    if (Array.isArray(value)) value.forEach((v) => params.append(key, String(v)));
    else params.append(key, String(value));
  }
  const qs = params.toString();
  return qs ? `${url}?${qs}` : url;
}

/**
 * Só redireciona quando a sessão cai dentro da área logada. Em páginas públicas
 * (/login, /register...) um redirect causaria recarga em loop.
 */
function redirectToLogin(): void {
  if (typeof window === "undefined") return;
  const { pathname, search } = window.location;
  if (!pathname.startsWith("/app")) return;
  // Recarga completa de propósito: descarta todo o estado em memória da sessão expirada.
  // eslint-disable-next-line @next/next/no-location-assign-relative-destination
  window.location.assign(`/login?redirect=${encodeURIComponent(pathname + search)}`);
}

/**
 * Renovação de sessão "single-flight": vários 401 simultâneos compartilham UMA chamada a
 * /auth/refresh. Com refresh rotativo e detecção de reuso no backend, chamadas paralelas
 * seriam tratadas como roubo de token e derrubariam a sessão.
 */
let refreshInFlight: Promise<void> | null = null;

function refreshSession(): Promise<void> {
  refreshInFlight ??= request<void>("/auth/refresh", { method: "POST", ...AUTH }).finally(() => {
    refreshInFlight = null;
  });
  return refreshInFlight;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, query, skipRefresh = false, silent = false } = options;

  const init: RequestInit = { method, credentials: "include" };
  if (body !== undefined) {
    init.headers = { "content-type": "application/json" };
    init.body = JSON.stringify(body);
  }
  const response = await fetch(buildUrl(path, query), init);

  if (response.status === 401 && !skipRefresh) {
    try {
      await refreshSession();
    } catch {
      if (!silent) redirectToLogin();
      throw new ApiError(401, "TOKEN_EXPIRED", "Sessão expirada");
    }
    return request<T>(path, { ...options, skipRefresh: true });
  }

  if (!response.ok) {
    let code = "UNKNOWN";
    let message = "Algo deu errado";
    try {
      const data = (await response.json()) as { code?: string; message?: string };
      if (data.code) code = data.code;
      if (data.message) message = data.message;
    } catch {
      /* corpo não é JSON */
    }
    if (response.status === 401 && !silent) redirectToLogin();
    throw new ApiError(response.status, code, message);
  }

  if (response.status === 204) return undefined as T;
  const text = await response.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

export const httpApi: Api = {
  publicConfig: () => request<PublicConfig>("/public/config"),
  auth: {
    register: (input) => request<void>("/auth/register", { method: "POST", body: input, ...AUTH }),
    login: (input) => request<User>("/auth/login", { method: "POST", body: input, ...AUTH }),
    logout: () => request<void>("/auth/logout", { method: "POST", ...AUTH }),
    refresh: () => refreshSession(),
    forgot: (email) => request<void>("/auth/forgot", { method: "POST", body: { email }, ...AUTH }),
    reset: (input) => request<void>("/auth/reset", { method: "POST", body: input, ...AUTH }),
  },
  me: {
    // Sondagem de sessão feita em todas as páginas (inclusive públicas): tenta renovar
    // uma vez, mas nunca redireciona.
    get: () => request<User>("/me", { silent: true }),
    updatePreferences: (input) =>
      request<User>("/me/preferences", { method: "PATCH", body: input }),
    changePassword: (input) => request<void>("/me/password", { method: "POST", body: input }),
    delete: () => request<void>("/me", { method: "DELETE" }),
  },
  alerts: {
    list: () => request<Alert[]>("/alerts"),
    get: (id) => request<Alert>(`/alerts/${id}`),
    create: (input: AlertInput) => request<Alert>("/alerts", { method: "POST", body: input }),
    update: (id, input) => request<Alert>(`/alerts/${id}`, { method: "PATCH", body: input }),
    remove: (id) => request<void>(`/alerts/${id}`, { method: "DELETE" }),
    duplicate: (id) => request<Alert>(`/alerts/${id}/duplicate`, { method: "POST" }),
    fromUrl: (url) =>
      request<Partial<AlertInput>>("/alerts/from-url", { method: "POST", body: { url } }),
    preview: (draft) => request<PreviewResult>("/alerts/preview", { method: "POST", body: draft }),
    presets: () => request<ExcludePresetInfo[]>("/alerts/presets"),
  },
  channels: { list: () => request<ChannelInfo[]>("/channels") },
  destinations: {
    list: () => request<Destination[]>("/destinations"),
    createLinkCode: (input) =>
      request<LinkCode>("/destinations/link-code", { method: "POST", body: input }),
    update: (id, patch) =>
      request<Destination>(`/destinations/${id}`, { method: "PATCH", body: patch }),
    remove: (id) => request<void>(`/destinations/${id}`, { method: "DELETE" }),
    test: (id) => request<void>(`/destinations/${id}/test`, { method: "POST" }),
    send: (id, itemIds) =>
      request<void>(`/destinations/${id}/send`, { method: "POST", body: { itemIds } }),
  },
  items: {
    list: (q: ItemQuery) => request<ItemPage>("/items", { query: q as Record<string, unknown> }),
    history: (itemId) => request<PricePoint[]>(`/items/${itemId}/history`),
  },
  search: {
    run: (input) =>
      request<SearchStatus>("/search/run", {
        method: "POST",
        body: input,
      }),
    status: () => request<SearchStatus>("/search/status"),
    stop: () => request<SearchStatus>("/search/stop", { method: "POST" }),
  },
  monitor: {
    status: () => request<MonitorStatus>("/monitor/status"),
    start: () => request<void>("/monitor/start", { method: "POST" }),
    stop: () => request<void>("/monitor/stop", { method: "POST" }),
  },
  settings: {
    get: () => request<Settings>("/settings"),
    update: (patch) => request<Settings>("/settings", { method: "PATCH", body: patch }),
  },
  billing: {
    subscription: () => request<Subscription>("/billing/subscription"),
    usage: () => request<Usage>("/billing/usage"),
    createCheckout: (plan: Plan, interval) =>
      request<{ url: string }>("/billing/checkout", { method: "POST", body: { plan, interval } }),
    createPortal: () => request<{ url: string }>("/billing/portal", { method: "POST" }),
  },
  admin: {
    overview: () => request<AdminOverview>("/admin/overview"),
    users: (params) => request<AdminUser[]>("/admin/users", { query: params }),
    updateUser: (id, input) =>
      request<AdminUser>(`/admin/users/${id}`, { method: "PATCH", body: input }),
    deleteUser: (id) => request<void>(`/admin/users/${id}`, { method: "DELETE" }),
    userNotifications: (id) => request<AdminUserNotifications>(`/admin/users/${id}/notifications`),
    runs: (params) => request<AdminRun[]>("/admin/runs", { query: params }),
  },
};

export type { UserStatus };
