import type {
  AdminUser,
  Alert,
  Destination,
  ExcludePreset,
  ExcludePresetInfo,
  Invite,
  Item,
  ItemCondition,
  MonitorRun,
  MonitorStatus,
  Settings,
  Subscription,
  User,
} from "../types";

export const PRESETS: ExcludePresetInfo[] = [
  {
    id: "PHONES",
    label: "Telemóveis / iPhones",
    words: ["capa", "película", "carregador", "cabo", "peças", "ecrã", "tela", "case", "vidro"],
  },
  {
    id: "CONSOLES_GAMES",
    label: "Consolas e jogos",
    words: ["comando", "controle", "jogo", "game", "suporte", "base", "dock", "avariada", "peças"],
  },
  {
    id: "AUDIO_VIDEO",
    label: "Áudio e vídeo",
    words: ["almofada", "espuma", "cabo", "adaptador", "capa", "estojo", "peças"],
  },
];

export const CONDITIONS: ItemCondition[] = [
  "new_with_tags",
  "new_without_tags",
  "very_good",
  "good",
  "satisfactory",
];

const nowIso = (offsetMs = 0) => new Date(Date.now() + offsetMs).toISOString();

export const seedUsers: (User & { password: string })[] = [
  {
    id: "u_demo",
    email: "demo@garimpo.app",
    password: "demo12345678",
    role: "USER",
    plan: "PRO",
    status: "ACTIVE",
    verified: true,
    trialEndsAt: nowIso(1000 * 60 * 60 * 24 * 7),
    subscriptionStatus: null,
    subscriptionEndsAt: null,
    hasAccess: true,
    createdAt: nowIso(-1000 * 60 * 60 * 24 * 40),
    country: "pt",
    language: "pt",
    currency: "EUR",
  },
  {
    id: "u_admin",
    email: "admin@garimpo.app",
    password: "demo12345678",
    role: "ADMIN",
    plan: "PRO",
    status: "ACTIVE",
    verified: true,
    trialEndsAt: nowIso(1000 * 60 * 60 * 24 * 7),
    subscriptionStatus: null,
    subscriptionEndsAt: null,
    hasAccess: true,
    createdAt: nowIso(-1000 * 60 * 60 * 24 * 120),
    country: "pt",
    language: "pt",
    currency: "EUR",
  },
];

export const seedDestinations: Destination[] = [
  {
    id: "d_1",
    channel: "TELEGRAM",
    kind: "GROUP",
    title: "Grupo Revenda",
    status: "LINKED",
    isDefault: true,
    linkedAt: nowIso(-1000 * 60 * 60 * 24 * 12),
    language: "pt",
  },
];

export const seedAlerts: Alert[] = [
  {
    id: "a_iphone",
    name: "iPhone 12 barato",
    query: "iPhone 12",
    matchType: "PHRASE",
    requiredWords: [],
    excludeWords: [],
    excludePresets: ["PHONES"],
    minPrice: 60,
    maxPrice: 90,
    statusFilter: ["very_good", "good", "new_without_tags"],
    maxAgeMinutes: 120,
    pages: 1,
    country: "pt",
    notifyOnFirstRun: false,
    vintedParams: null,
    sourceUrl: null,
    perfectMin: 65,
    perfectMax: 75,
    destinationId: "d_1",
    active: true,
    createdAt: nowIso(-1000 * 60 * 60 * 24 * 20),
    newToday: 4,
  },
  {
    id: "a_ps5",
    name: "PS5 completo",
    query: "PS5",
    matchType: "PHRASE",
    requiredWords: [],
    excludeWords: [],
    excludePresets: ["CONSOLES_GAMES"],
    minPrice: 250,
    maxPrice: 380,
    statusFilter: ["very_good", "good"],
    maxAgeMinutes: null,
    pages: 2,
    country: "pt",
    notifyOnFirstRun: false,
    vintedParams: null,
    sourceUrl: null,
    perfectMin: 250,
    perfectMax: 290,
    destinationId: "d_1",
    active: true,
    createdAt: nowIso(-1000 * 60 * 60 * 24 * 9),
    newToday: 2,
  },
  {
    id: "a_nike",
    name: "Nike Air Max 90",
    query: "Nike Air Max 90",
    matchType: "ALL_WORDS",
    requiredWords: [],
    excludeWords: ["réplica"],
    excludePresets: [],
    minPrice: 40,
    maxPrice: 90,
    statusFilter: ["new_with_tags", "very_good", "good"],
    maxAgeMinutes: null,
    pages: 1,
    country: "pt",
    notifyOnFirstRun: false,
    vintedParams: null,
    sourceUrl: null,
    perfectMin: null,
    perfectMax: null,
    destinationId: "d_1",
    active: false,
    createdAt: nowIso(-1000 * 60 * 60 * 24 * 3),
    newToday: 0,
  },
];

const TITLES: Record<string, string[]> = {
  a_iphone: [
    "iPhone 12 64GB preto desbloqueado",
    "iPhone 12 mini azul como novo",
    "iPhone 12 128GB branco",
    "iPhone 12 con caja original",
    "iPhone 12 très bon état 64 Go",
    "iPhone 12 zwart, goede staat",
    "Capa iPhone 12 silicone",
    "Película iPhone 12 vidro temperado",
  ],
  a_ps5: [
    "PS5 Digital Edition com garantia",
    "PlayStation 5 completa com caixa",
    "PS5 Slim casi nueva",
    "PS5 avec 2 manettes",
    "Comando PS5 DualSense",
    "Suporte vertical PS5",
  ],
  a_nike: [
    "Nike Air Max 90 branco 42",
    "Nike Air Max 90 essential preto",
    "Zapatillas Nike Air Max 90 talla 41",
    "Nike Air Max 90 blanche 43",
    "Nike Air Max 90 réplica AAA",
  ],
};

const TITLES_PT: Record<string, string> = {
  "iPhone 12 con caja original": "iPhone 12 com caixa original",
  "iPhone 12 très bon état 64 Go": "iPhone 12 em muito bom estado 64 GB",
  "iPhone 12 zwart, goede staat": "iPhone 12 preto, bom estado",
  "PS5 Slim casi nueva": "PS5 Slim quase nova",
  "PS5 avec 2 manettes": "PS5 com 2 comandos",
  "Zapatillas Nike Air Max 90 talla 41": "Tênis Nike Air Max 90 tamanho 41",
  "Nike Air Max 90 blanche 43": "Nike Air Max 90 branco 43",
};

const SELLERS = [
  "marta_p",
  "joaoLX",
  "revendaPT",
  "sofia.m",
  "luis_2020",
  "anna_shop",
  "kbd_store",
];

let counter = 0;
function nextId(prefix: string): string {
  counter += 1;
  return `${prefix}_${Date.now().toString(36)}${counter}`;
}

function priceForAlert(alertId: string): number {
  if (alertId === "a_iphone") return Math.round(45 + Math.random() * 70);
  if (alertId === "a_ps5") return Math.round(220 + Math.random() * 200);
  return Math.round(30 + Math.random() * 80);
}

export function makeItem(alert: Alert, ageMinutes: number): Item {
  const titles = TITLES[alert.id] ?? [alert.query];
  const title = titles[Math.floor(Math.random() * titles.length)]!;
  const price = priceForAlert(alert.id);
  const id = nextId("i");
  const postedAt = nowIso(-ageMinutes * 60 * 1000);
  return {
    id,
    title,
    titlePt: TITLES_PT[title] ?? null,
    price,
    priceEur: price,
    priceUser: price,
    userCurrency: "EUR",
    currency: "EUR",
    condition: CONDITIONS[Math.floor(Math.random() * CONDITIONS.length)]!,
    sellerLogin: SELLERS[Math.floor(Math.random() * SELLERS.length)]!,
    url: `https://marketplace.example/items/${id}`,
    photoUrl: `https://picsum.photos/seed/${id}/480/360`,
    postedAt,
    firstSeenAt: nowIso(-(ageMinutes - 0.5) * 60 * 1000),
    alertId: alert.id,
    alertName: alert.name,
    isPerfect:
      alert.perfectMin !== null &&
      alert.perfectMax !== null &&
      price >= alert.perfectMin &&
      price <= alert.perfectMax,
  };
}

export function seedItems(alerts: Alert[]): Item[] {
  const items: Item[] = [];
  for (const alert of alerts) {
    const count = alert.id === "a_nike" ? 10 : 15;
    for (let i = 0; i < count; i += 1) {
      // Demo realista: há sempre anúncios de poucos minutos no topo e a maioria nas últimas
      // horas (distribuição enviesada para o recente), como num mercado real.
      const ageMinutes =
        i === 0
          ? Math.round(2 + Math.random() * 18)
          : i === 1
            ? Math.round(20 + Math.random() * 60)
            : Math.round(1 + Math.random() ** 3 * 60 * 24 * 3);
      items.push(makeItem(alert, ageMinutes));
    }
  }
  return items.sort(
    (a, b) => new Date(b.firstSeenAt).getTime() - new Date(a.firstSeenAt).getTime(),
  );
}

export function seedRuns(): MonitorRun[] {
  const runs: MonitorRun[] = [];
  for (let i = 0; i < 24; i += 1) {
    const failing = i === 5 || i === 17;
    runs.push({
      id: `r_${i}`,
      startedAt: nowIso(-i * 60 * 60 * 1000),
      durationMs: Math.round(800 + Math.random() * 4200),
      analyzed: Math.round(40 + Math.random() * 120),
      matches: Math.round(Math.random() * 6),
      sent: Math.round(Math.random() * 4),
      status: failing ? (i === 5 ? "error" : "rate_limited") : "ok",
      error: failing ? "Marketplace respondeu 429 — reduzimos o ritmo" : null,
    });
  }
  return runs;
}

export const seedMonitor: MonitorStatus = {
  state: "ACTIVE",
  enabled: true,
  intervalMinutes: 5,
  lastRunAt: nowIso(-1000 * 60 * 4),
  nextRunAt: nowIso(1000 * 60 * 11),
  lastError: null,
  runs: seedRuns(),
  medianDetectionSeconds: 42,
};

export const seedSettings: Settings = {
  intervalMinutes: 5,
};

export const seedSubscription: Subscription = {
  plan: "PRO",
  status: "active",
  currentPeriodEnd: nowIso(1000 * 60 * 60 * 24 * 12),
  cancelAtPeriodEnd: false,
};

export const seedAdminUsers: AdminUser[] = [
  ...seedUsers.map(({ password: _password, ...u }) => u),
  {
    id: "u_3",
    email: "carla@exemplo.com",
    role: "USER",
    plan: "PRO",
    status: "ACTIVE",
    createdAt: nowIso(-1000 * 60 * 60 * 24 * 14),
  },
  {
    id: "u_4",
    email: "pedro@exemplo.com",
    role: "USER",
    plan: "FREE",
    status: "PENDING",
    createdAt: nowIso(-1000 * 60 * 60 * 20),
  },
  {
    id: "u_5",
    email: "ines@exemplo.com",
    role: "USER",
    plan: "ELITE",
    status: "SUSPENDED",
    createdAt: nowIso(-1000 * 60 * 60 * 24 * 60),
  },
];

export const seedInvites: Invite[] = [
  {
    id: "inv_1",
    code: "GARIMPO-7K4D",
    email: null,
    expiresAt: nowIso(1000 * 60 * 60 * 24 * 5),
    usedAt: null,
  },
  {
    id: "inv_2",
    code: "GARIMPO-9XQ2",
    email: "amigo@exemplo.com",
    expiresAt: nowIso(-1000 * 60 * 60 * 24),
    usedAt: nowIso(-1000 * 60 * 60 * 30),
  },
];

export function presetWords(presets: ExcludePreset[]): string[] {
  return presets.flatMap((p) => PRESETS.find((x) => x.id === p)?.words ?? []);
}

export { nextId };
