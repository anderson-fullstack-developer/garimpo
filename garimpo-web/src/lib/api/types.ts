export type Role = "USER" | "ADMIN";
export type UserStatus = "PENDING" | "ACTIVE" | "SUSPENDED";
export type Plan = "FREE" | "PRO" | "ELITE";
export type MatchType = "PHRASE" | "ALL_WORDS";
export type ExcludePreset = "PHONES" | "CONSOLES_GAMES" | "AUDIO_VIDEO";
export type ChannelId = "TELEGRAM";
export type DestinationKind = "PRIVATE" | "GROUP" | "CHANNEL";
export type MonitorState = "ACTIVE" | "PAUSED" | "DEGRADED" | "RATE_LIMITED";
export type ItemCondition =
  "new_with_tags" | "new_without_tags" | "very_good" | "good" | "satisfactory";

export interface User {
  id: string;
  email: string;
  role: Role;
  plan: Plan;
  status: UserStatus;
  /** Telegram vinculado: só então a conta é liberada. */
  verified: boolean;
  /** Fim do teste grátis (7 dias a partir da ativação). */
  trialEndsAt: string | null;
  subscriptionStatus: string | null;
  subscriptionEndsAt: string | null;
  /** Teste em andamento ou assinatura ativa: pode buscar. */
  hasAccess: boolean;
  createdAt: string;
  country: string | null;
  language: string;
  currency: string;
}

export interface PublicConfig {
  registrationMode: "OPEN" | "APPROVAL";
  botUsername: string;
}

export interface Alert {
  id: string;
  name: string;
  query: string;
  matchType: MatchType;
  requiredWords: string[];
  excludeWords: string[];
  excludePresets: ExcludePreset[];
  minPrice: number;
  maxPrice: number | null;
  statusFilter: ItemCondition[];
  maxAgeMinutes: number | null;
  pages: number;
  /** Código do país ("pt", "fr"...) ou "eu" para todos os países da Europa. */
  country: string;
  /** Enviar também os anúncios que já existem quando o alerta é criado/ligado. */
  notifyOnFirstRun: boolean;
  vintedParams: Record<string, string | number | number[]> | null;
  sourceUrl: string | null;
  perfectMin: number | null;
  perfectMax: number | null;
  destinationId: string | null;
  active: boolean;
  createdAt: string;
  newToday: number;
}
export type AlertInput = Omit<Alert, "id" | "createdAt" | "newToday">;

export interface Destination {
  id: string;
  channel: ChannelId;
  kind: DestinationKind | null;
  title: string | null;
  status: "LINKED" | "PENDING" | "DISCONNECTED";
  isDefault: boolean;
  linkedAt: string | null;
  /** Idioma dos avisos deste destino (o da conta, se não escolher outro). */
  language: string;
}

export interface ChannelInfo {
  id: ChannelId;
  name: string;
  supportsGroups: boolean;
  supportsImages: boolean;
  instructions: Record<DestinationKind, string[]>;
}

export interface LinkCode {
  /** Destino criado com status PENDING; vira LINKED quando o usuário conclui o vínculo. */
  destinationId: string;
  code: string;
  expiresAt: string;
  deepLink: string | null;
  command: string | null;
}

export interface Item {
  id: string;
  title: string;
  titlePt: string | null;
  price: number;
  /** Preço na moeda escolhida pelo usuário (Configurações). */
  priceUser: number;
  userCurrency: string;
  /** Preço em euros (os alertas filtram em EUR; o anúncio vem na moeda do país). */
  priceEur: number;
  currency: string;
  condition: ItemCondition | null;
  sellerLogin: string;
  url: string;
  photoUrl: string | null;
  postedAt: string | null;
  firstSeenAt: string;
  alertId: string;
  alertName: string;
  isPerfect: boolean;
}

export interface ItemPage {
  items: Item[];
  nextCursor: string | null;
  total: number;
}

export interface ItemQuery {
  alertIds?: string[] | undefined;
  minPrice?: number | undefined;
  maxPrice?: number | undefined;
  onlyPerfect?: boolean | undefined;
  period?: "1h" | "today" | "7d" | undefined;
  sort?: "newest" | "price_asc" | undefined;
  cursor?: string | undefined;
}

export interface PreviewRow {
  item: Item;
  matched: boolean;
  reasons: string[];
}
export interface PreviewResult {
  matched: PreviewRow[];
  discarded: PreviewRow[];
  analyzed: number;
}

export interface MonitorStatus {
  state: MonitorState;
  enabled: boolean;
  intervalMinutes: number;
  lastRunAt: string | null;
  nextRunAt: string | null;
  lastError: string | null;
  runs: MonitorRun[];
  medianDetectionSeconds: number | null;
}

export interface MonitorRun {
  id: string;
  startedAt: string;
  durationMs: number;
  analyzed: number;
  matches: number;
  sent: number;
  status: "ok" | "error" | "rate_limited";
  error: string | null;
}

export interface PricePoint {
  at: string;
  price: number;
}

export interface Settings {
  intervalMinutes: number;
}

export interface Subscription {
  plan: Plan;
  status: "active" | "past_due" | "canceled" | "trialing";
  currentPeriodEnd: string | null;
  cancelAtPeriodEnd: boolean;
}

export interface Usage {
  alerts: number;
  destinations: number;
}

export type AdminAccess = "admin" | "paid" | "trial" | "expired" | "unverified";

export interface AdminUser {
  id: string;
  email: string;
  role: Role;
  status: UserStatus;
  country: string | null;
  language: string;
  currency: string;
  verified: boolean;
  createdAt: string;
  lastLoginAt: string | null;
  trialEndsAt: string | null;
  subscriptionStatus: string | null;
  stripeCustomer: boolean;
  hasAccess: boolean;
  access: AdminAccess;
  alerts: number;
  destinations: number;
  monitorEnabled: boolean;
}

export interface AdminOverview {
  users: number;
  newThisWeek: number;
  verified: number;
  unverified: number;
  inTrial: number;
  paid: number;
  expired: number;
  suspended: number;
  alerts: number;
  destinations: number;
  items: number;
  monitorOn: number;
  runsLastDay: number;
  runErrorsLastDay: number;
}

export interface AdminRun {
  id: string;
  searchKey: string;
  startedAt: string;
  durationMs: number;
  status: string;
  analyzed: number;
  matches: number;
  error: string | null;
}

export type AdminAction =
  | "grant_access"
  | "revoke_access"
  | "extend_trial"
  | "end_trial"
  | "suspend"
  | "reactivate"
  | "make_admin"
  | "remove_admin";

export type ApiErrorCode =
  | "INVALID_CREDENTIALS"
  | "TELEGRAM_NOT_VERIFIED"
  | "ACCOUNT_PENDING"
  | "ACCOUNT_SUSPENDED"
  | "PLAN_LIMIT_REACHED"
  | "SUBSCRIPTION_REQUIRED"
  | "RATE_LIMITED"
  | "VALIDATION_ERROR"
  | "NOT_FOUND"
  | "TOKEN_EXPIRED"
  | "UNKNOWN";

export class ApiError extends Error {
  status: number;
  code: ApiErrorCode | string;
  constructor(status: number, code: ApiErrorCode | string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

export interface ExcludePresetInfo {
  id: ExcludePreset;
  label: string;
  words: string[];
}

export interface Api {
  publicConfig(): Promise<PublicConfig>;
  auth: {
    register(input: {
      email: string;
      password: string;
      country?: string | undefined;
      captchaToken: string;
    }): Promise<void>;
    login(input: { email: string; password: string }): Promise<User>;
    logout(): Promise<void>;
    refresh(): Promise<void>;
    forgot(email: string): Promise<void>;
    reset(input: { token: string; password: string }): Promise<void>;
  };
  me: {
    get(): Promise<User>;
    updatePreferences(input: {
      country?: string;
      language?: string;
      currency?: string;
    }): Promise<User>;
    changePassword(input: { current: string; next: string }): Promise<void>;
    delete(): Promise<void>;
  };
  alerts: {
    list(): Promise<Alert[]>;
    get(id: string): Promise<Alert>;
    create(input: AlertInput): Promise<Alert>;
    update(id: string, input: Partial<AlertInput>): Promise<Alert>;
    remove(id: string): Promise<void>;
    duplicate(id: string): Promise<Alert>;
    fromUrl(url: string): Promise<Partial<AlertInput>>;
    preview(draft: AlertInput): Promise<PreviewResult>;
    presets(): Promise<ExcludePresetInfo[]>;
  };
  channels: { list(): Promise<ChannelInfo[]> };
  destinations: {
    list(): Promise<Destination[]>;
    createLinkCode(input: {
      channel: ChannelId;
      kind: DestinationKind;
      language?: string | undefined;
    }): Promise<LinkCode>;
    update(
      id: string,
      patch: {
        title?: string | undefined;
        isDefault?: boolean | undefined;
        language?: string | undefined;
      },
    ): Promise<Destination>;
    remove(id: string): Promise<void>;
    test(id: string): Promise<void>;
    send(id: string, itemIds: string[]): Promise<void>;
  };
  items: {
    list(q: ItemQuery): Promise<ItemPage>;
    history(itemId: string): Promise<PricePoint[]>;
  };
  search: {
    /** Dá a partida: a busca roda no servidor, mesmo que o usuário saia da tela. */
    run(input: { mode: "alerts" | "all" }): Promise<SearchStatus>;
    status(): Promise<SearchStatus>;
    /** Para a busca contínua. */
    stop(): Promise<SearchStatus>;
  };
  monitor: {
    status(): Promise<MonitorStatus>;
    start(): Promise<void>;
    stop(): Promise<void>;
  };
  settings: {
    get(): Promise<Settings>;
    update(patch: Partial<Settings>): Promise<Settings>;
  };
  billing: {
    subscription(): Promise<Subscription>;
    usage(): Promise<Usage>;
    createCheckout(plan: Plan, interval: "month" | "year"): Promise<{ url: string }>;
    createPortal(): Promise<{ url: string }>;
  };
  admin: {
    overview(): Promise<AdminOverview>;
    users(params?: { q?: string | undefined; access?: string | undefined }): Promise<AdminUser[]>;
    updateUser(id: string, input: { action: AdminAction; days?: number }): Promise<AdminUser>;
    deleteUser(id: string): Promise<void>;
    runs(params?: { status?: string | undefined }): Promise<AdminRun[]>;
  };
}

export interface SearchStatus {
  state: "idle" | "running" | "stopping" | "done" | "error";
  analyzed: number;
  /** Novos desde que o usuário clicou em buscar (soma de todos os ciclos). */
  newItems: number;
  cycles?: number;
  error?: { code: string; message: string } | null;
  startedAt?: string | null;
  finishedAt?: string | null;
}
