import { useEffect, useState } from "react";
import { ShieldCheck, Loader2 } from "lucide-react";

import { pt } from "@/i18n/pt";

/** Placeholder do Turnstile/CAPTCHA: no modo mock sempre passa. */
export function CaptchaBox({ onToken }: { onToken: (token: string) => void }) {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setReady(true);
      onToken("mock-captcha-token");
    }, 700);
    return () => window.clearTimeout(timer);
  }, [onToken]);

  return (
    <div
      aria-live="polite"
      className="flex items-center gap-2 rounded-lg border border-border bg-muted/50 px-3 py-3 text-sm"
    >
      {ready ? (
        <>
          <ShieldCheck className="size-4 text-primary" aria-hidden />
          <span>{pt.auth.captchaOk}</span>
        </>
      ) : (
        <>
          <Loader2 className="size-4 animate-spin" aria-hidden />
          <span>{pt.auth.captchaLabel}</span>
        </>
      )}
    </div>
  );
}
