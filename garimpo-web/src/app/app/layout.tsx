"use client";

import { usePathname, useRouter } from "next/navigation";
import { Suspense, useEffect, type ReactNode } from "react";

import { AppShell } from "@/components/app-shell";
import { LoadingBlock } from "@/components/states";
import { PaywallProvider } from "@/features/billing/PaywallProvider";
import { SubscriptionReturn } from "@/features/billing/SubscriptionReturn";
import { SearchWatcher } from "@/features/search/SearchWatcher";
import { useAuth } from "@/features/auth/AuthProvider";

/** Área logada: exige sessão e leva contas pendentes para /pending. */
export default function AppLayout({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (loading) return;
    if (!user) router.replace(`/login?redirect=${encodeURIComponent(pathname)}`);
    else if (user.status === "PENDING") router.replace("/pending");
    else if (!user.verified) router.replace("/verify"); // conta liberada só depois do Telegram
  }, [loading, user, router, pathname]);

  if (loading || !user || !user.verified) return <LoadingBlock className="min-h-screen" />;

  return (
    <PaywallProvider>
      <AppShell>
        <SearchWatcher />
        <Suspense>
          <SubscriptionReturn />
        </Suspense>
        {children}
      </AppShell>
    </PaywallProvider>
  );
}
