import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  CreditCard,
  History,
  LayoutGrid,
  Radio,
  Send,
  Settings,
  ShieldCheck,
  Siren,
  UserRound,
} from "lucide-react";
import type { ReactNode } from "react";

import { Logo } from "@/components/logo";
import { ThemeToggle } from "@/components/theme-toggle";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { FEATURES } from "@/config/features";
import { TrialBanner } from "@/features/billing/TrialBanner";
import { useAuth } from "@/features/auth/AuthProvider";
import { useDestinations, useMonitor } from "@/hooks/useGarimpo";
import { pt } from "@/i18n/pt";
import { cn } from "@/lib/utils";

type NavPath =
  | "/app/alerts"
  | "/app/results"
  | "/app/settings"
  | "/app/destinations"
  | "/app/monitor"
  | "/app/history"
  | "/app/billing"
  | "/app/admin";

interface NavItem {
  to: NavPath;
  label: string;
  icon: typeof LayoutGrid;
  /** Item escondido enquanto o sinalizador estiver desligado. */
  enabled: boolean;
  adminOnly?: boolean;
}

/** Núcleo do produto primeiro; o resto só aparece se o sinalizador correspondente estiver ligado. */
const navItems = (): NavItem[] => [
  { to: "/app/results", label: pt.nav.results, icon: LayoutGrid, enabled: true },
  { to: "/app/alerts", label: pt.nav.alerts, icon: Siren, enabled: true },
  { to: "/app/settings", label: pt.nav.settings, icon: Settings, enabled: true },
  {
    to: "/app/destinations",
    label: pt.nav.destinations,
    icon: Send,
    enabled: FEATURES.destinationsPage,
  },
  { to: "/app/monitor", label: pt.nav.monitor, icon: Radio, enabled: FEATURES.monitorPage },
  { to: "/app/history", label: pt.nav.history, icon: History, enabled: FEATURES.history },
  { to: "/app/billing", label: pt.nav.billing, icon: CreditCard, enabled: FEATURES.billing },
  {
    to: "/app/admin",
    label: pt.nav.admin,
    icon: ShieldCheck,
    enabled: FEATURES.admin,
    adminOnly: true,
  },
];

function useVisibleNav(): NavItem[] {
  const { user } = useAuth();
  return navItems().filter((item) => item.enabled && (!item.adminOnly || user?.role === "ADMIN"));
}

function MonitorDot() {
  const { data } = useMonitor();
  const state = data?.state ?? "PAUSED";
  const color =
    state === "ACTIVE"
      ? "bg-primary pulse-dot"
      : state === "RATE_LIMITED" || state === "DEGRADED"
        ? "bg-perfect"
        : "bg-muted-foreground";
  return (
    <span className="inline-flex items-center gap-2 text-xs text-muted-foreground">
      <span className={cn("size-2 rounded-full", color)} aria-hidden />
      <span className="hidden sm:inline">{pt.monitorState[state]}</span>
    </span>
  );
}

function Banners() {
  const { data: destinations } = useDestinations();
  const { data: monitor } = useMonitor();
  const banners: ReactNode[] = [];

  if (destinations && destinations.filter((d) => d.status === "LINKED").length === 0) {
    banners.push(
      <div key="dest" className="flex flex-wrap items-center justify-between gap-2">
        <span>{pt.banners.noDestination}</span>
        <Button asChild size="sm" variant="secondary">
          <Link href="/app/settings?tab=telegram">{pt.banners.noDestinationCta}</Link>
        </Button>
      </div>,
    );
  }
  if (monitor?.state === "RATE_LIMITED") {
    banners.push(<div key="rate">{pt.banners.rateLimited}</div>);
  }

  if (!banners.length) return null;
  return (
    <div className="space-y-2 px-4 pt-3" aria-live="polite">
      {banners.map((banner, index) => (
        <div
          key={index}
          className="rounded-lg border border-border bg-accent/60 px-3 py-2 text-sm text-accent-foreground"
        >
          {banner}
        </div>
      ))}
    </div>
  );
}

function isActive(pathname: string, to: NavPath): boolean {
  return pathname === to || pathname.startsWith(`${to}/`);
}

function NavLinks() {
  const items = useVisibleNav();
  const pathname = usePathname();

  return (
    <nav className="space-y-1">
      {items.map((item) => {
        const active = isActive(pathname, item.to);
        return (
          <Link
            key={item.to}
            href={item.to}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
              active
                ? "bg-sidebar-accent font-medium text-sidebar-accent-foreground"
                : "text-sidebar-foreground hover:bg-sidebar-accent/60",
            )}
          >
            <item.icon className="size-4" strokeWidth={1.75} aria-hidden />
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}

function UserMenu() {
  const { user, logout } = useAuth();
  const router = useRouter();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" aria-label={user?.email ?? pt.settings.tabAccount}>
          <UserRound className="size-5" strokeWidth={1.75} aria-hidden />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel className="flex items-center justify-between gap-3">
          <span className="truncate text-xs text-muted-foreground">{user?.email}</span>
          {FEATURES.billing ? <Badge variant="secondary">{user?.plan}</Badge> : null}
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link href="/app/settings">{pt.nav.settings}</Link>
        </DropdownMenuItem>
        {FEATURES.billing ? (
          <DropdownMenuItem asChild>
            <Link href="/app/billing">{pt.nav.billing}</Link>
          </DropdownMenuItem>
        ) : null}
        <DropdownMenuSeparator />
        <DropdownMenuItem
          onSelect={async () => {
            await logout();
            router.push("/login");
          }}
        >
          {pt.common.logout}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const items = useVisibleNav();
  const pathname = usePathname();

  return (
    <div className="min-h-screen bg-background">
      <aside className="fixed inset-y-0 left-0 hidden w-60 flex-col border-r border-sidebar-border bg-sidebar p-4 lg:flex">
        <Link href="/app/results" className="mb-6 px-1" aria-label={pt.brand.name}>
          <Logo />
        </Link>
        <NavLinks />
      </aside>

      <div className="lg:pl-60">
        <header className="sticky top-0 z-30 flex items-center justify-between gap-2 border-b border-border bg-background/90 px-4 py-3 backdrop-blur">
          <div className="flex items-center gap-3">
            <span className="lg:hidden">
              <Logo compact />
            </span>
            <MonitorDot />
          </div>
          <div className="flex items-center gap-1">
            <ThemeToggle />
            <UserMenu />
          </div>
        </header>

        <TrialBanner />
        <Banners />

        <main className="mx-auto w-full max-w-6xl px-4 pb-24 pt-4 lg:pb-12">{children}</main>
      </div>

      <nav className="fixed inset-x-0 bottom-0 z-30 flex border-t border-border bg-background/95 backdrop-blur lg:hidden">
        {items.map((item) => {
          const active = isActive(pathname, item.to);
          return (
            <Link
              key={item.to}
              href={item.to}
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex flex-1 flex-col items-center gap-1 py-2 text-[11px]",
                active ? "text-primary" : "text-muted-foreground",
              )}
            >
              <item.icon className="size-5" strokeWidth={1.75} aria-hidden />
              {item.label}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
