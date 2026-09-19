import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Clock } from "lucide-react";
import { toast } from "sonner";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { ChipsInput } from "@/components/chips-input";
import { CONDITION_LIST } from "@/features/alerts/constants";
import { errorMessage } from "@/components/states";
import { useAlertMutations, useDestinations } from "@/hooks/useGarimpo";
import { COUNTRIES, EUROPE, countryLabel } from "@/config/countries";
import { pt } from "@/i18n/pt";
import type { Alert, AlertInput, ItemCondition } from "@/lib/api/types";

const schema = z.object({
  query: z.string().trim().min(2, "Informe pelo menos 2 caracteres"),
});

export const emptyDraft: AlertInput = {
  name: "",
  query: "",
  matchType: "PHRASE",
  requiredWords: [],
  excludeWords: [],
  excludePresets: [],
  minPrice: 0,
  maxPrice: null,
  statusFilter: [],
  maxAgeMinutes: null,
  pages: 1,
  country: "pt",
  notifyOnFirstRun: false,
  vintedParams: null,
  sourceUrl: null,
  perfectMin: null,
  perfectMax: null,
  destinationId: null,
  active: true,
};

const toggleButton = (on: boolean) =>
  on
    ? "rounded-full border border-primary bg-accent px-3 py-1 text-xs text-accent-foreground"
    : "rounded-full border border-border px-3 py-1 text-xs hover:bg-muted";

/** Número de um input: vazio vira `null` (ou `fallback`, quando informado). */
function numberOrNull(value: string): number | null {
  return value === "" ? null : Number(value);
}

export function AlertForm({ existing }: { existing?: Alert | undefined }) {
  const router = useRouter();
  const { data: destinations } = useDestinations();
  const { create, update } = useAlertMutations();

  const [dirty, setDirty] = useState(false);
  const [leaving, setLeaving] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [draft, setDraft] = useState<AlertInput>(() => {
    if (!existing) return { ...emptyDraft };
    const { id: _id, createdAt: _createdAt, newToday: _newToday, ...rest } = existing;
    return rest;
  });

  const patch = (next: Partial<AlertInput>) => {
    setDraft((prev) => ({ ...prev, ...next }));
    setDirty(true);
  };

  useEffect(() => {
    if (!dirty) return;
    const handler = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty]);

  const linked = (destinations ?? []).filter((d) => d.status === "LINKED");
  const defaultDestination = linked.find((d) => d.isDefault) ?? linked[0];
  // Alerta novo já vem com o destino padrão selecionado (o usuário só troca se quiser).
  const destinationId = draft.destinationId ?? defaultDestination?.id ?? "";

  const validate = (): boolean => {
    const next: Record<string, string> = {};
    const parsed = schema.safeParse({ query: draft.query });
    if (!parsed.success) next["query"] = parsed.error.issues[0]?.message ?? pt.misc.invalidQuery;
    if (draft.maxPrice !== null && draft.maxPrice < draft.minPrice) {
      next["maxPrice"] = pt.misc.maxBelowMin;
    }
    setErrors(next);
    return Object.keys(next).length === 0;
  };

  const save = async (active: boolean) => {
    if (!validate()) {
      toast.error(pt.misc.checkFields);
      return;
    }
    const payload: AlertInput = {
      ...draft,
      name: draft.name.trim() || draft.query.trim(),
      destinationId: destinationId || null,
      active,
    };
    try {
      if (existing) {
        await update.mutateAsync({ id: existing.id, input: payload });
        toast.success(pt.misc.alertUpdated);
      } else {
        await create.mutateAsync(payload);
        toast.success(pt.misc.alertCreated);
      }
      setDirty(false);
      router.push("/app/alerts");
    } catch (error) {
      toast.error(errorMessage(error));
    }
  };

  const toggleCondition = (condition: ItemCondition) =>
    patch({
      statusFilter: draft.statusFilter.includes(condition)
        ? draft.statusFilter.filter((c) => c !== condition)
        : [...draft.statusFilter, condition],
    });

  const saving = create.isPending || update.isPending;

  return (
    <div className="max-w-2xl">
      <form
        className="space-y-5"
        onSubmit={(event) => {
          event.preventDefault();
          void save(true);
        }}
        noValidate
      >
        <section className="surface space-y-5 p-4 sm:p-5">
          <div className="space-y-2">
            <Label htmlFor="query">{pt.alerts.whatTitle}</Label>
            <Input
              id="query"
              value={draft.query}
              placeholder={pt.alerts.queryHelp}
              autoFocus={!existing}
              onChange={(e) => patch({ query: e.target.value })}
            />
            {errors["query"] ? <p className="text-xs text-destructive">{errors["query"]}</p> : null}
          </div>

          <div className="space-y-2">
            <p className="text-sm font-medium">{pt.alerts.priceTitle}</p>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label htmlFor="minPrice" className="text-xs font-normal text-muted-foreground">
                  {pt.alerts.minPrice}
                </Label>
                <Input
                  id="minPrice"
                  type="number"
                  min={0}
                  value={draft.minPrice}
                  onChange={(e) => patch({ minPrice: numberOrNull(e.target.value) ?? 0 })}
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="maxPrice" className="text-xs font-normal text-muted-foreground">
                  {pt.alerts.maxPrice}
                </Label>
                <Input
                  id="maxPrice"
                  type="number"
                  min={0}
                  value={draft.maxPrice ?? ""}
                  onChange={(e) => patch({ maxPrice: numberOrNull(e.target.value) })}
                />
              </div>
            </div>
            {errors["maxPrice"] ? (
              <p className="text-xs text-destructive">{errors["maxPrice"]}</p>
            ) : null}
          </div>

          <div className="space-y-2">
            <Label htmlFor="country">{pt.alerts.countryTitle}</Label>
            <Select value={draft.country} onValueChange={(v) => patch({ country: v })}>
              <SelectTrigger id="country">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={EUROPE}>{pt.alerts.countryEurope}</SelectItem>
                {COUNTRIES.map((c) => (
                  <SelectItem key={c.code} value={c.code}>
                    {countryLabel(c.code)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {draft.country === EUROPE ? (
              <div
                role="note"
                className="flex items-start gap-2 rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-xs text-amber-900 dark:text-amber-200"
              >
                <Clock className="mt-0.5 size-3.5 shrink-0" aria-hidden />
                <span>{pt.alerts.countryEuropeHelp}</span>
              </div>
            ) : null}
          </div>

          <div className="space-y-3">
            <p className="text-sm font-medium">{pt.alerts.excludeTitle}</p>
            <ChipsInput
              id="exclude"
              label={pt.alerts.excludeWords}
              value={draft.excludeWords}
              onChange={(value) => patch({ excludeWords: value })}
            />
          </div>

          <div className="space-y-2">
            <p className="text-sm font-medium">{pt.alerts.conditionTitle}</p>
            <div className="flex flex-wrap gap-2">
              {CONDITION_LIST.map((condition) => (
                <button
                  key={condition}
                  type="button"
                  onClick={() => toggleCondition(condition)}
                  aria-pressed={draft.statusFilter.includes(condition)}
                  className={toggleButton(draft.statusFilter.includes(condition))}
                >
                  {pt.condition[condition]}
                </button>
              ))}
            </div>
            <p className="text-xs text-muted-foreground">{pt.alerts.conditionHelp}</p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="destination">{pt.alerts.destination}</Label>
            {linked.length ? (
              <Select value={destinationId} onValueChange={(v) => patch({ destinationId: v })}>
                <SelectTrigger id="destination">
                  <SelectValue placeholder={pt.alerts.destination} />
                </SelectTrigger>
                <SelectContent>
                  {linked.map((d) => (
                    <SelectItem key={d.id} value={d.id}>
                      {d.title ?? d.channel}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : (
              <Button asChild type="button" variant="outline">
                <Link href="/app/settings?tab=telegram">{pt.alerts.connectDestination}</Link>
              </Button>
            )}
          </div>

          <div className="flex items-start gap-3">
            <Switch
              id="firstCycle"
              checked={draft.notifyOnFirstRun}
              onCheckedChange={(value) => patch({ notifyOnFirstRun: value })}
            />
            <div className="space-y-1">
              <Label htmlFor="firstCycle" className="font-normal">
                {pt.alerts.firstCycleLabel}
              </Label>
              <p className="text-xs text-muted-foreground">
                {draft.notifyOnFirstRun ? pt.alerts.firstCycleOn : pt.alerts.firstCycleOff}
              </p>
            </div>
          </div>
        </section>

        <div className="flex flex-wrap gap-2">
          <Button type="submit" disabled={saving}>
            {existing ? pt.alerts.saveChanges : pt.alerts.saveAlert}
          </Button>
          <Button
            type="button"
            variant="ghost"
            onClick={() => (dirty ? setLeaving(true) : router.push("/app/alerts"))}
          >
            {pt.common.cancel}
          </Button>
        </div>
      </form>

      <AlertDialog open={leaving} onOpenChange={setLeaving}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{pt.alerts.unsavedTitle}</AlertDialogTitle>
            <AlertDialogDescription>{pt.alerts.unsavedText}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{pt.common.cancel}</AlertDialogCancel>
            <AlertDialogAction onClick={() => router.push("/app/alerts")}>
              {pt.common.confirm}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
