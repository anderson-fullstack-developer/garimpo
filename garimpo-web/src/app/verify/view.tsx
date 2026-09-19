"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { Copy, ExternalLink, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { AuthLayout } from "@/features/auth/AuthLayout";
import { useAuth } from "@/features/auth/AuthProvider";
import { Button } from "@/components/ui/button";
import { errorMessage } from "@/components/states";
import { usePublicConfig } from "@/hooks/useGarimpo";
import { api } from "@/lib/api";
import type { LinkCode } from "@/lib/api/types";
import { pt, t } from "@/i18n/pt";

/** Ativa a conta: o usuário liga o chat PRIVADO do Telegram (não há verificação por e-mail). */
export function VerifyPage() {
  const { user, loading, reload, logout } = useAuth();
  const { data: config } = usePublicConfig();
  const router = useRouter();
  const [code, setCode] = useState<LinkCode | null>(null);
  const [error, setError] = useState<string | null>(null);
  const requested = useRef(false);
  const language = user?.language;

  const generate = useCallback(async () => {
    setError(null);
    try {
      setCode(
        await api.destinations.createLinkCode({
          channel: "TELEGRAM",
          kind: "PRIVATE",
          language,
        }),
      );
    } catch (err) {
      setError(errorMessage(err));
    }
  }, [language]);

  // Sem sessão -> login; já verificada -> app.
  useEffect(() => {
    if (loading) return;
    if (!user) router.replace("/login?redirect=/verify");
    else if (user.verified) router.replace("/app/results");
  }, [loading, user, router]);

  useEffect(() => {
    if (!user || user.verified || requested.current) return;
    requested.current = true;
    void generate();
  }, [user, generate]);

  // Enquanto espera, consulta a conta a cada 3 s: o vínculo pelo bot a libera.
  useEffect(() => {
    if (!user || user.verified) return;
    const timer = window.setInterval(() => void reload(), 3000);
    return () => window.clearInterval(timer);
  }, [user, reload]);

  if (loading || !user || user.verified) {
    return (
      <AuthLayout title={pt.verify.done}>
        <div className="flex justify-center py-6">
          <Loader2 className="size-6 animate-spin text-primary" aria-hidden />
        </div>
      </AuthLayout>
    );
  }

  const bot = config?.botUsername ? `@${config.botUsername}` : "";
  return (
    <AuthLayout title={pt.verify.title} subtitle={pt.verify.subtitle}>
      <div className="space-y-4">
        {code?.deepLink ? (
          <Button asChild className="w-full">
            <a href={code.deepLink} target="_blank" rel="noopener noreferrer">
              <ExternalLink className="mr-2 size-4" aria-hidden /> {pt.destinations.openTelegram}
            </a>
          </Button>
        ) : (
          <div className="flex justify-center py-2" aria-live="polite">
            {error ? null : <Loader2 className="size-5 animate-spin text-primary" aria-hidden />}
          </div>
        )}
        {error ? (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        ) : null}

        <ol className="list-decimal space-y-1 pl-5 text-sm text-muted-foreground">
          <li>{pt.verify.step1}</li>
          <li>{pt.verify.step2}</li>
          <li>{pt.verify.step3}</li>
        </ol>

        {code ? (
          <div className="rounded-lg border border-border bg-muted/50 p-3 text-center">
            <p className="text-xs text-muted-foreground">{t(pt.verify.manual, { bot })}</p>
            <div className="mt-1 flex items-center justify-center gap-2">
              <span className="text-lg font-semibold tracking-widest">{code.code}</span>
              <Button
                type="button"
                size="icon"
                variant="ghost"
                aria-label={pt.common.copy}
                onClick={async () => {
                  await navigator.clipboard?.writeText(code.code);
                  toast.success(pt.common.copied);
                }}
              >
                <Copy className="size-4" aria-hidden />
              </Button>
            </div>
          </div>
        ) : null}

        <p
          className="flex items-center justify-center gap-2 text-xs text-muted-foreground"
          aria-live="polite"
        >
          <Loader2 className="size-3 animate-spin" aria-hidden /> {pt.verify.waiting}
        </p>

        <div className="flex items-center justify-between text-sm">
          <Button type="button" variant="ghost" size="sm" onClick={() => void generate()}>
            {pt.verify.newCode}
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={async () => {
              await logout();
              router.push("/login");
            }}
          >
            {pt.verify.logout}
          </Button>
        </div>
      </div>
    </AuthLayout>
  );
}
