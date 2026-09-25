import { ApiError } from "../types";
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
  Item,
  ItemPage,
  ItemQuery,
  MonitorRun,
  MonitorStatus,
  SearchStatus,
  Plan,
  PreviewResult,
  PreviewRow,
  PricePoint,
  PublicConfig,
  Settings,
  Subscription,
  Usage,
  User,
} from "../types";
import { entitlementsFor } from "@/lib/entitlements";
import {
  PRESETS,
  makeItem,
  nextId,
  presetWords,
  seedAlerts,
  seedDestinations,
  seedItems,
  seedMonitor,
  seedSettings,
  seedSubscription,
  seedUsers,
} from "./data";

const STORAGE_KEY = "garimpo.mock.v3";

interface MockState {
  sessionUserId: string | null;
  users: (User & { password: string })[];
  alerts: Alert[];
  destinations: Destination[];
  settings: Settings;
  monitor: MonitorStatus;
  subscription: Subscription;
  registrationMode: PublicConfig["registrationMode"];
}

let items: Item[] = seedItems(seedAlerts);
const priceHistory = new Map<string, PricePoint[]>();
let pendingLink: {
  code: string;
  expiresAt: number;
  kind: Destination["kind"];
  destinationId: string;
} | null = null;

function freshState(): MockState {
  return {
    sessionUserId: null,
    users: seedUsers.map((u) => ({ ...u })),
    alerts: seedAlerts.map((a) => ({ ...a })),
    destinations: seedDestinations.map((d) => ({ ...d })),
    settings: { ...seedSettings },
    monitor: { ...seedMonitor },
    subscription: { ...seedSubscription },
    registrationMode: "OPEN",
  };
}

function load(): MockState {
  if (typeof window === "undefined") return freshState();
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return freshState();
    return { ...freshState(), ...(JSON.parse(raw) as Partial<MockState>) } as MockState;
  } catch {
    return freshState();
  }
}

const state: MockState = load();

function persist(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    /* ignora quota */
  }
}

function delay(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 300 + Math.random() * 600));
}

let searchJob: SearchStatus = { state: "idle", analyzed: 0, newItems: 0 };

async function respond<T>(value: T | (() => T), failRate = 0.02): Promise<T> {
  await delay();
  if (Math.random() < failRate) {
    throw new ApiError(503, "UNKNOWN", "Falha temporária simulada. Tente de novo.");
  }
  const result = typeof value === "function" ? (value as () => T)() : value;
  persist();
  return result;
}

function currentUser(): User {
  const user = state.users.find((u) => u.id === state.sessionUserId);
  if (!user) throw new ApiError(401, "INVALID_CREDENTIALS", "Sessão expirada");
  const { password: _password, ...rest } = user;
  return rest;
}

function publicUser(u: User & { password: string }): User {
  const { password: _password, ...rest } = u;
  return rest;
}

// Novos itens surgindo sozinhos para demonstrar o polling.
if (typeof window !== "undefined") {
  window.setInterval(() => {
    const active = state.alerts.filter((a) => a.active);
    if (!active.length || !state.monitor.enabled) return;
    const alert = active[Math.floor(Math.random() * active.length)]!;
    items = [makeItem(alert, 1), ...items];
  }, 30000);
}

function matchesQuery(alert: AlertInput, title: string): boolean {
  const lower = title.toLowerCase();
  if (alert.matchType === "PHRASE") return lower.includes(alert.query.toLowerCase());
  return alert.query
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean)
    .every((w) => lower.includes(w));
}

function evaluate(alert: AlertInput, item: Item): string[] {
  const reasons: string[] = [];
  const lower = `${item.title} ${item.titlePt ?? ""}`.toLowerCase();
  if (!matchesQuery(alert, lower)) reasons.push("query_not_matched");
  for (const word of alert.requiredWords) {
    if (!lower.includes(word.toLowerCase())) reasons.push(`missing_required_word:${word}`);
  }
  const excludes = [...alert.excludeWords, ...presetWords(alert.excludePresets)];
  for (const word of excludes) {
    if (lower.includes(word.toLowerCase())) reasons.push(`excluded_by_word:${word}`);
  }
  if (item.price < alert.minPrice) reasons.push("below_min_price");
  if (alert.maxPrice !== null && item.price > alert.maxPrice) reasons.push("above_max_price");
  if (alert.statusFilter.length && item.condition && !alert.statusFilter.includes(item.condition)) {
    reasons.push("condition_not_allowed");
  }
  if (alert.maxAgeMinutes !== null && item.postedAt) {
    const ageMin = (Date.now() - new Date(item.postedAt).getTime()) / 60000;
    if (ageMin > alert.maxAgeMinutes) reasons.push("too_old");
  }
  return reasons;
}

function historyFor(itemId: string): PricePoint[] {
  const cached = priceHistory.get(itemId);
  if (cached) return cached;
  const item = items.find((i) => i.id === itemId);
  const base = item?.price ?? 80;
  const points: PricePoint[] = [];
  const count = 6 + Math.floor(Math.random() * 7);
  for (let i = count - 1; i >= 0; i -= 1) {
    points.push({
      at: new Date(Date.now() - i * 6 * 60 * 60 * 1000).toISOString(),
      price: Math.max(5, Math.round(base * (1 + (Math.random() - 0.35) * 0.25))),
    });
  }
  points[points.length - 1] = { at: new Date().toISOString(), price: base };
  priceHistory.set(itemId, points);
  return points;
}

function assertPlanLimit(kind: "alerts" | "destinations"): void {
  const user = currentUser();
  const ent = entitlementsFor(user.plan);
  if (kind === "alerts" && state.alerts.length >= ent.maxAlerts) {
    throw new ApiError(402, "PLAN_LIMIT_REACHED", "Limite de alertas do plano atingido");
  }
  const linked = state.destinations.filter((d) => d.status !== "PENDING").length;
  if (kind === "destinations" && linked >= ent.maxDestinations) {
    throw new ApiError(402, "PLAN_LIMIT_REACHED", "Limite de destinos do plano atingido");
  }
}

const CHANNELS: ChannelInfo[] = [
  {
    id: "TELEGRAM",
    name: "Telegram",
    supportsGroups: true,
    supportsImages: true,
    instructions: {
      PRIVATE: [
        "Toque em “Abrir no Telegram”.",
        "Toque em Iniciar na conversa com o bot.",
        "Pronto: o vínculo é automático.",
      ],
      GROUP: [
        "Adicione o bot @{bot} ao seu grupo.",
        "Envie no grupo: /link {code}",
        "Você precisa ser administrador do grupo.",
      ],
      CHANNEL: [
        "Adicione o bot @{bot} como administrador do canal.",
        "Publique no canal: /link {code}",
      ],
    },
  },
];

export const mockApi: Api = {
  publicConfig: () =>
    respond<PublicConfig>(
      { registrationMode: state.registrationMode, botUsername: "GarimpoAlertasBot" },
      0,
    ),

  auth: {
    register: ({ email, password, country }) =>
      respond<void>(() => {
        if (state.users.some((u) => u.email === email)) return;
        const status: User["status"] = state.registrationMode === "APPROVAL" ? "PENDING" : "ACTIVE";
        const user = {
          id: nextId("u"),
          email,
          password,
          role: "USER" as const,
          plan: "FREE" as const,
          status,
          verified: false,
          trialEndsAt: new Date(Date.now() + 7 * 86400e3).toISOString(),
          subscriptionStatus: null,
          subscriptionEndsAt: null,
          hasAccess: true,
          createdAt: new Date().toISOString(),
          country: country ?? null,
          language: country && country !== "pt" ? "en" : "pt",
          currency: "EUR",
        };
        state.users.push(user);
      }, 0),
    login: ({ email, password }) =>
      respond<User>(() => {
        // O mock ignora espaços/tabs acidentais (comuns ao copiar e colar a senha da demonstração).
        const user = state.users.find((u) => u.email === email.trim().toLowerCase());
        if (!user || user.password !== password.trim()) {
          throw new ApiError(401, "INVALID_CREDENTIALS", "E-mail ou senha inválidos");
        }
        if (user.status === "PENDING") {
          throw new ApiError(403, "ACCOUNT_PENDING", "Conta aguardando aprovação");
        }
        if (user.status === "SUSPENDED") {
          throw new ApiError(403, "ACCOUNT_SUSPENDED", "Conta suspensa");
        }
        state.sessionUserId = user.id;
        state.subscription = { ...state.subscription, plan: user.plan };
        return publicUser(user);
      }, 0),
    logout: () =>
      respond<void>(() => {
        state.sessionUserId = null;
      }, 0),
    refresh: () =>
      respond<void>(() => {
        if (!state.sessionUserId) throw new ApiError(401, "INVALID_CREDENTIALS", "Sem sessão");
      }, 0),
    forgot: () => respond<void>(undefined, 0),
    reset: ({ token }) =>
      respond<void>(() => {
        if (!token || token === "expired") {
          throw new ApiError(400, "TOKEN_EXPIRED", "Link inválido ou expirado");
        }
      }, 0),
  },

  me: {
    get: () => respond<User>(() => currentUser(), 0),
    updatePreferences: (input) =>
      respond<User>(() => {
        const user = state.users.find((u) => u.id === state.sessionUserId);
        if (!user) throw new ApiError(401, "INVALID_CREDENTIALS", "Sessão expirada");
        if (input.country) user.country = input.country;
        if (input.language) user.language = input.language;
        if (input.currency) user.currency = input.currency;
        return currentUser();
      }, 0),
    changePassword: ({ current, next }) =>
      respond<void>(() => {
        const user = state.users.find((u) => u.id === state.sessionUserId);
        if (!user || user.password !== current) {
          throw new ApiError(400, "VALIDATION_ERROR", "Senha atual incorreta");
        }
        user.password = next;
      }, 0),
    delete: () =>
      respond<void>(() => {
        state.users = state.users.filter((u) => u.id !== state.sessionUserId);
        state.sessionUserId = null;
      }, 0),
  },

  alerts: {
    list: () => respond<Alert[]>(() => state.alerts.map((a) => ({ ...a }))),
    get: (id) =>
      respond<Alert>(() => {
        const alert = state.alerts.find((a) => a.id === id);
        if (!alert) throw new ApiError(404, "NOT_FOUND", "Alerta não encontrado");
        return { ...alert };
      }),
    create: (input) =>
      respond<Alert>(() => {
        assertPlanLimit("alerts");
        const alert: Alert = {
          ...input,
          id: nextId("a"),
          createdAt: new Date().toISOString(),
          newToday: 0,
        };
        state.alerts.push(alert);
        return { ...alert };
      }, 0),
    update: (id, patch) =>
      respond<Alert>(() => {
        const alert = state.alerts.find((a) => a.id === id);
        if (!alert) throw new ApiError(404, "NOT_FOUND", "Alerta não encontrado");
        Object.assign(alert, patch);
        return { ...alert };
      }, 0),
    remove: (id) =>
      respond<void>(() => {
        state.alerts = state.alerts.filter((a) => a.id !== id);
      }, 0),
    duplicate: (id) =>
      respond<Alert>(() => {
        assertPlanLimit("alerts");
        const alert = state.alerts.find((a) => a.id === id);
        if (!alert) throw new ApiError(404, "NOT_FOUND", "Alerta não encontrado");
        const copy: Alert = {
          ...alert,
          id: nextId("a"),
          name: `${alert.name} (cópia)`,
          active: false,
          createdAt: new Date().toISOString(),
          newToday: 0,
        };
        state.alerts.push(copy);
        return { ...copy };
      }, 0),
    fromUrl: (url) =>
      respond<Partial<AlertInput>>(() => {
        let parsed: URL;
        try {
          parsed = new URL(url);
        } catch {
          throw new ApiError(400, "VALIDATION_ERROR", "Endereço inválido");
        }
        const params = parsed.searchParams;
        const query = params.get("search_text") ?? params.get("q") ?? "iPhone 12";
        const min = Number(params.get("price_from") ?? 0);
        const max = params.get("price_to") ? Number(params.get("price_to")) : null;
        return {
          query,
          minPrice: Number.isFinite(min) ? min : 0,
          maxPrice: max,
          matchType: "PHRASE",
          statusFilter: [],
          sourceUrl: url,
          vintedParams: {
            catalog: params.get("catalog[]") ?? "telemoveis",
            brand: params.get("brand_id") ?? "apple",
            ...(params.get("size_id") ? { size: params.get("size_id")! } : {}),
          },
        };
      }, 0),
    preview: (draft) =>
      respond<PreviewResult>(() => {
        const pool = items.slice(0, 60);
        const rows: PreviewRow[] = pool.map((item) => {
          const reasons = evaluate(draft, item);
          return { item, matched: reasons.length === 0, reasons };
        });
        return {
          matched: rows.filter((r) => r.matched),
          discarded: rows.filter((r) => !r.matched),
          analyzed: rows.length,
        };
      }, 0),
    presets: () => respond(PRESETS, 0),
  },

  channels: { list: () => respond<ChannelInfo[]>(CHANNELS, 0) },

  destinations: {
    list: () =>
      respond<Destination[]>(() => {
        if (pendingLink) {
          const link = pendingLink;
          const pending = state.destinations.find((d) => d.id === link.destinationId);
          if (Date.now() > link.expiresAt) {
            // Código expirou sem vínculo: some o destino pendente.
            state.destinations = state.destinations.filter((d) => d.id !== link.destinationId);
            pendingLink = null;
          } else if (pending && Date.now() > link.expiresAt - 10 * 60 * 1000 + 8000) {
            // Simula o usuário concluindo o vínculo ~8 s depois.
            pending.status = "LINKED";
            pending.title =
              link.kind === "GROUP"
                ? "Meu grupo"
                : link.kind === "CHANNEL"
                  ? "Meu canal"
                  : "Conversa privada";
            pending.linkedAt = new Date().toISOString();
            pending.isDefault = !state.destinations.some((d) => d.isDefault);
            pendingLink = null;
          }
        }
        return state.destinations.map((d) => ({ ...d }));
      }, 0),
    createLinkCode: ({ channel, kind, language }) =>
      respond(() => {
        const me = state.users.find((u) => u.id === state.sessionUserId);
        if (me && !me.verified) window.setTimeout(() => (me.verified = true), 6000);
        assertPlanLimit("destinations");
        const code = `G-${Math.random().toString(36).slice(2, 8).toUpperCase()}`;
        const expiresAt = Date.now() + 10 * 60 * 1000;
        // Como no backend real: o destino nasce PENDING e o front acompanha o status dele.
        const destination: Destination = {
          id: nextId("d"),
          channel,
          kind,
          title: null,
          status: "PENDING",
          isDefault: false,
          linkedAt: null,
          language: language ?? "pt",
        };
        state.destinations = state.destinations.filter((d) => d.status !== "PENDING");
        state.destinations.push(destination);
        pendingLink = { code, expiresAt, kind, destinationId: destination.id };
        return {
          destinationId: destination.id,
          code,
          expiresAt: new Date(expiresAt).toISOString(),
          deepLink: `https://t.me/GarimpoAlertasBot?start=${code}`,
          command: `/link ${code}`,
        };
      }, 0),
    update: (id, patch) =>
      respond<Destination>(() => {
        const destination = state.destinations.find((d) => d.id === id);
        if (!destination) throw new ApiError(404, "NOT_FOUND", "Destino não encontrado");
        if (patch.isDefault) state.destinations.forEach((d) => (d.isDefault = false));
        Object.assign(destination, patch);
        return { ...destination };
      }, 0),
    remove: (id) =>
      respond<void>(() => {
        state.destinations = state.destinations.filter((d) => d.id !== id);
      }, 0),
    test: () => respond<void>(undefined, 0),
    send: () => respond<void>(undefined, 0),
  },

  items: {
    list: (q: ItemQuery) =>
      respond<ItemPage>(() => {
        const alertById = new Map(state.alerts.map((a) => [a.id, a]));
        let list = items.filter((i) => {
          const alert = alertById.get(i.alertId);
          return alert ? evaluate(alert, i).length === 0 : false;
        });
        if (q.alertIds?.length) list = list.filter((i) => q.alertIds!.includes(i.alertId));
        if (q.minPrice !== undefined) list = list.filter((i) => i.price >= q.minPrice!);
        if (q.maxPrice !== undefined) list = list.filter((i) => i.price <= q.maxPrice!);
        if (q.onlyPerfect) list = list.filter((i) => i.isPerfect);
        if (q.period) {
          const windows = { "1h": 3600e3, today: 86400e3, "7d": 7 * 86400e3 } as const;
          const cutoff = Date.now() - windows[q.period];
          list = list.filter((i) => new Date(i.firstSeenAt).getTime() >= cutoff);
        }
        list.sort((a, b) =>
          q.sort === "price_asc"
            ? a.price - b.price
            : new Date(b.firstSeenAt).getTime() - new Date(a.firstSeenAt).getTime(),
        );
        const start = q.cursor ? Number(q.cursor) : 0;
        const pageSize = 20;
        const page = list.slice(start, start + pageSize);
        return {
          items: page,
          nextCursor: start + pageSize < list.length ? String(start + pageSize) : null,
          total: list.length,
        };
      }),
    history: (itemId) => respond<PricePoint[]>(() => historyFor(itemId)),
  },

  search: {
    status: () =>
      respond<SearchStatus>(() => {
        if (searchJob.state === "running") {
          // Cada consulta simula um ciclo: às vezes aparece um anúncio novo.
          const active = state.alerts.filter((a) => a.active);
          if (active.length && Math.random() < 0.3) {
            items = [makeItem(active[Math.floor(Math.random() * active.length)]!, 1), ...items];
            searchJob = { ...searchJob, newItems: searchJob.newItems + 1 };
          }
          searchJob = { ...searchJob, cycles: (searchJob.cycles ?? 0) + 1, analyzed: 60 };
        }
        return { ...searchJob };
      }, 0),
    run: () =>
      respond<SearchStatus>(() => {
        if (searchJob.state !== "running") {
          searchJob = {
            state: "running",
            analyzed: 0,
            newItems: 0,
            cycles: 0,
            startedAt: new Date().toISOString(),
          };
        }
        return { ...searchJob };
      }, 0),
    stop: () =>
      respond<SearchStatus>(() => {
        if (searchJob.state === "running") {
          searchJob = { ...searchJob, state: "done", finishedAt: new Date().toISOString() };
        }
        return { ...searchJob };
      }, 0),
  },

  monitor: {
    status: () =>
      respond<MonitorStatus>(() => ({
        ...state.monitor,
        state: state.monitor.enabled ? state.monitor.state : "PAUSED",
        intervalMinutes: state.settings.intervalMinutes,
        runs: state.monitor.runs.map((r) => ({ ...r })),
      })),
    start: () =>
      respond<void>(() => {
        state.monitor.enabled = true;
        state.monitor.state = "ACTIVE";
        state.monitor.nextRunAt = new Date(
          Date.now() + state.settings.intervalMinutes * 60000,
        ).toISOString();
      }, 0),
    stop: () =>
      respond<void>(() => {
        state.monitor.enabled = false;
        state.monitor.state = "PAUSED";
      }, 0),
  },

  settings: {
    get: () => respond<Settings>(() => ({ ...state.settings })),
    update: (patch) =>
      respond<Settings>(() => {
        state.settings = { ...state.settings, ...patch };
        return { ...state.settings };
      }, 0),
  },

  billing: {
    subscription: () => respond<Subscription>(() => ({ ...state.subscription })),
    usage: () =>
      respond<Usage>(() => ({
        alerts: state.alerts.length,
        destinations: state.destinations.length,
      })),
    createCheckout: (plan: Plan) => respond({ url: `mock://checkout/${plan}` }, 0),
    createPortal: () => respond({ url: "mock://portal" }, 0),
  },

  admin: {
    overview: () =>
      respond<AdminOverview>({
        users: 3,
        newThisWeek: 2,
        verified: 3,
        unverified: 0,
        inTrial: 1,
        paid: 1,
        expired: 0,
        suspended: 0,
        alerts: 4,
        destinations: 3,
        items: 1200,
        monitorOn: 2,
        runsLastDay: 480,
        runErrorsLastDay: 2,
      }),
    users: () =>
      respond<AdminUser[]>(() => [
        {
          id: "u_demo",
          email: "demo@garimpo.app",
          role: "ADMIN",
          status: "ACTIVE",
          country: "pt",
          language: "pt",
          currency: "EUR",
          verified: true,
          createdAt: new Date(Date.now() - 5 * 86400e3).toISOString(),
          lastLoginAt: new Date().toISOString(),
          trialEndsAt: null,
          subscriptionStatus: "active",
          stripeCustomer: false,
          hasAccess: true,
          access: "admin",
          alerts: 2,
          destinations: 1,
          monitorEnabled: true,
          notified: 1,
          notifyFailed: 0,
          lastNotifiedAt: new Date(Date.now() - 3600e3).toISOString(),
        },
      ]),
    userNotifications: () =>
      respond<AdminUserNotifications>({
        sent: 1,
        failed: 0,
        alerts: [
          {
            id: "a_demo",
            name: "iPhone 11",
            query: "iphone 11",
            country: "pt",
            active: true,
            sent: 1,
            failed: 0,
          },
        ],
        items: [
          {
            id: "n_demo",
            sentAt: new Date(Date.now() - 3600e3).toISOString(),
            ok: true,
            error: null,
            alertName: "iPhone 11",
            title: "iPhone 11 64GB preto",
            price: 180,
            currency: "EUR",
            url: "https://www.vinted.pt/items/1",
            photoUrl: null,
            domain: "pt",
          },
        ],
      }),
    updateUser: () =>
      Promise.reject(new ApiError(400, "VALIDATION_ERROR", "Indisponível no modo demonstração")),
    deleteUser: () =>
      Promise.reject(new ApiError(400, "VALIDATION_ERROR", "Indisponível no modo demonstração")),
    runs: () => respond<AdminRun[]>([]),
  },
};

/** Usado apenas pelo checkout simulado. */
export function mockApproveCheckout(plan: Plan): void {
  state.subscription = {
    plan,
    status: "active",
    currentPeriodEnd: new Date(Date.now() + 30 * 86400e3).toISOString(),
    cancelAtPeriodEnd: false,
  };
  const user = state.users.find((u) => u.id === state.sessionUserId);
  if (user) user.plan = plan;
  persist();
}
