import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Check, Copy, ExternalLink, Loader2 } from "lucide-react";
import { toast } from "sonner";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { errorMessage } from "@/components/states";
import { api } from "@/lib/api";
import { qk, useChannels, useDestinations, usePublicConfig } from "@/hooks/useGarimpo";
import { pt, t } from "@/i18n/pt";
import type { ChannelId, DestinationKind, LinkCode } from "@/lib/api/types";

const KINDS: DestinationKind[] = ["PRIVATE", "GROUP", "CHANNEL"];

const kindLabel = () =>
  ({
    PRIVATE: pt.destinations.kindPRIVATE,
    GROUP: pt.destinations.kindGROUP,
    CHANNEL: pt.destinations.kindCHANNEL,
  }) as const;

export function LinkWizard({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const { data: channels } = useChannels();
  const { data: config } = usePublicConfig();
  const queryClient = useQueryClient();
  const [channel, setChannel] = useState<ChannelId | null>(null);
  const [kind, setKind] = useState<DestinationKind | null>(null);
  const [code, setCode] = useState<LinkCode | null>(null);
  const [loading, setLoading] = useState(false);
  const [secondsLeft, setSecondsLeft] = useState(0);
  const [linked, setLinked] = useState(false);

  const { data: destinations } = useDestinations(code && !linked ? 3000 : undefined);

  // Acompanha o status do destino criado para ESTE código (o backend o cria como PENDING).
  useEffect(() => {
    if (!code || linked) return;
    const target = destinations?.find((d) => d.id === code.destinationId);
    if (target?.status === "LINKED") {
      setLinked(true);
      void queryClient.invalidateQueries({ queryKey: qk.destinations });
    }
  }, [destinations, code, linked, queryClient]);

  useEffect(() => {
    if (!code) return;
    const tick = () =>
      setSecondsLeft(
        Math.max(0, Math.round((new Date(code.expiresAt).getTime() - Date.now()) / 1000)),
      );
    tick();
    const timer = window.setInterval(tick, 1000);
    return () => window.clearInterval(timer);
  }, [code]);

  const reset = () => {
    setChannel(null);
    setKind(null);
    setCode(null);
    setLinked(false);
  };

  const generate = async (selectedKind: DestinationKind) => {
    setKind(selectedKind);
    setLoading(true);
    try {
      setCode(
        await api.destinations.createLinkCode({
          channel: channel ?? "TELEGRAM",
          kind: selectedKind,
        }),
      );
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setLoading(false);
    }
  };

  const info = channels?.find((c) => c.id === (channel ?? "TELEGRAM"));
  const d = pt.destinations;
  const stepsByKind: Record<DestinationKind, string[]> = {
    PRIVATE: [d.stepPrivate1, d.stepPrivate2, d.stepPrivate3],
    GROUP: [d.stepGroup1, d.stepGroup2, d.stepGroup3],
    CHANNEL: [d.stepChannel1, d.stepChannel2],
  };
  const steps = kind ? stepsByKind[kind] : [];
  const mmss = `${String(Math.floor(secondsLeft / 60)).padStart(2, "0")}:${String(secondsLeft % 60).padStart(2, "0")}`;

  return (
    <Dialog
      open={open}
      onOpenChange={(value) => {
        if (!value) reset();
        onOpenChange(value);
      }}
    >
      <DialogContent className="max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{pt.destinations.connect}</DialogTitle>
          <DialogDescription>{pt.destinations.subtitle}</DialogDescription>
        </DialogHeader>

        {!channel ? (
          <div className="grid gap-2">
            <p className="text-sm font-medium">{pt.destinations.wizardChannel}</p>
            {(channels ?? []).map((c) => (
              <button
                key={c.id}
                type="button"
                onClick={() => setChannel(c.id)}
                className="rounded-lg border border-border p-3 text-left text-sm hover:bg-muted"
              >
                <span className="font-medium">{c.name}</span>
                <span className="mt-1 block text-xs text-muted-foreground">
                  {t(pt.misc.channelInfo, { v: c.supportsImages ? pt.misc.yes : pt.misc.no })}
                </span>
              </button>
            ))}
          </div>
        ) : null}

        {channel && !code ? (
          <div className="grid gap-2">
            <p className="text-sm font-medium">{pt.destinations.wizardKind}</p>
            {KINDS.map((k) => (
              <button
                key={k}
                type="button"
                disabled={loading}
                onClick={() => void generate(k)}
                className="rounded-lg border border-border p-3 text-left text-sm hover:bg-muted"
              >
                {kindLabel()[k]}
              </button>
            ))}
          </div>
        ) : null}

        {code && !linked ? (
          <div className="space-y-4">
            <div className="rounded-lg border border-border bg-muted/50 p-4 text-center">
              <p className="text-xs text-muted-foreground">{pt.destinations.wizardCode}</p>
              <p className="mt-1 text-2xl font-semibold tracking-widest">{code.code}</p>
              <div className="mt-3 flex justify-center gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={async () => {
                    await navigator.clipboard.writeText(code.command ?? code.code);
                    toast.success(pt.common.copied);
                  }}
                >
                  <Copy className="mr-1 size-3.5" aria-hidden /> {pt.common.copy}
                </Button>
                {kind === "PRIVATE" && code.deepLink ? (
                  <Button asChild size="sm">
                    <a href={code.deepLink} target="_blank" rel="noopener noreferrer">
                      <ExternalLink className="mr-1 size-3.5" aria-hidden />
                      {pt.destinations.openTelegram}
                    </a>
                  </Button>
                ) : null}
              </div>
            </div>

            <ol className="list-decimal space-y-1 pl-5 text-sm">
              {steps.map((stepText) => (
                <li key={stepText}>
                  {stepText
                    .replace("{bot}", config?.botUsername ?? "GarimpoAlertasBot")
                    .replace("{code}", code.code)}
                </li>
              ))}
            </ol>
            <p className="text-xs text-muted-foreground">{pt.destinations.botLanguageNote}</p>

            {secondsLeft > 0 ? (
              <p className="text-xs text-muted-foreground">
                {t(pt.destinations.wizardExpires, { time: mmss })}
              </p>
            ) : (
              <div className="flex items-center justify-between gap-2">
                <p className="text-xs text-destructive">{pt.destinations.wizardExpired}</p>
                <Button size="sm" variant="outline" onClick={() => kind && void generate(kind)}>
                  {pt.destinations.wizardNewCode}
                </Button>
              </div>
            )}

            <p
              className="inline-flex items-center gap-2 text-sm text-muted-foreground"
              aria-live="polite"
            >
              <Loader2 className="size-4 animate-spin" aria-hidden />
              {pt.destinations.wizardWaiting}
            </p>
          </div>
        ) : null}

        {linked ? (
          <div className="space-y-4 text-center">
            <Check className="mx-auto size-8 text-primary" aria-hidden />
            <p className="text-sm font-medium">{pt.destinations.wizardSuccess}</p>
            <div className="flex justify-center gap-2">
              <Button
                variant="outline"
                onClick={async () => {
                  const target = destinations?.[destinations.length - 1];
                  if (target) await api.destinations.test(target.id);
                  toast.success(pt.destinations.testSent);
                }}
              >
                {pt.destinations.sendTest}
              </Button>
              <Button
                onClick={() => {
                  reset();
                  onOpenChange(false);
                }}
              >
                {pt.common.close}
              </Button>
            </div>
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
