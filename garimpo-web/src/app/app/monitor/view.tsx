"use client";

import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis } from "recharts";
import { Pause, Play } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { ErrorState, LoadingList, PageHeader } from "@/components/states";
import { UpgradeHint } from "@/components/upgrade-hint";
import {
  useMonitor,
  useMonitorMutations,
  useSettings,
  useSettingsMutation,
} from "@/hooks/useGarimpo";
import { useAuth } from "@/features/auth/AuthProvider";
import { entitlementsFor } from "@/lib/entitlements";
import { formatInterval, formatTime, relativeTime, untilTime } from "@/lib/format";
import { pt, t } from "@/i18n/pt";
import { APP_NAME } from "@/config/brand";

export function MonitorPage() {
  const { user } = useAuth();
  const monitor = useMonitor();
  const settings = useSettings();
  const updateSettings = useSettingsMutation();
  const { start, stop } = useMonitorMutations();
  const ent = entitlementsFor(user?.plan ?? "FREE");
  const interval = settings.data?.intervalMinutes ?? 15;

  const chartData = (monitor.data?.runs ?? [])
    .slice()
    .reverse()
    .map((run) => ({
      time: formatTime(run.startedAt),
      analyzed: run.analyzed,
    }));

  return (
    <div className="space-y-5">
      <PageHeader title={pt.monitor.title} subtitle={pt.monitor.subtitle} />

      {monitor.isLoading ? <LoadingList rows={3} /> : null}
      {monitor.isError ? (
        <ErrorState error={monitor.error} onRetry={() => monitor.refetch()} />
      ) : null}

      {monitor.data ? (
        <>
          <section className="surface space-y-4 p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="space-y-1">
                <Badge variant={monitor.data.enabled ? "default" : "secondary"}>
                  {pt.monitorState[monitor.data.state]}
                </Badge>
                <p className="text-sm text-muted-foreground">
                  {pt.monitor.lastRun}: {relativeTime(monitor.data.lastRunAt)} ·{" "}
                  {pt.monitor.nextRun} {untilTime(monitor.data.nextRunAt)}
                </p>
              </div>
              <Button
                size="lg"
                variant={monitor.data.enabled ? "outline" : "default"}
                onClick={() => (monitor.data.enabled ? stop.mutate() : start.mutate())}
              >
                {monitor.data.enabled ? (
                  <>
                    <Pause className="mr-2 size-4" aria-hidden /> {pt.monitor.stop}
                  </>
                ) : (
                  <>
                    <Play className="mr-2 size-4" aria-hidden /> {pt.monitor.start}
                  </>
                )}
              </Button>
            </div>

            <div className="space-y-2">
              <Label htmlFor="interval">
                {pt.monitor.interval}: {t(pt.monitor.intervalMinutes, { n: interval })}
              </Label>
              <Slider
                id="interval"
                min={Math.max(1, Math.round(ent.minIntervalMinutes))}
                max={60}
                step={1}
                value={[interval]}
                onValueChange={([value]) =>
                  updateSettings.mutate({ intervalMinutes: value ?? interval })
                }
              />
              <p className="text-xs text-muted-foreground">
                {t(pt.monitor.planFloor, { n: formatInterval(ent.minIntervalMinutes) })}
              </p>
              {ent.minIntervalMinutes > 1 ? <UpgradeHint feature="minInterval" /> : null}
            </div>
          </section>

          <section className="surface space-y-4 p-5">
            <h2 className="text-sm font-semibold">{pt.monitor.health}</h2>
            <div className="h-32 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData}>
                  <XAxis dataKey="time" fontSize={10} stroke="var(--color-muted-foreground)" />
                  <Tooltip
                    contentStyle={{
                      background: "var(--color-popover)",
                      border: "1px solid var(--color-border)",
                      borderRadius: "var(--radius-lg)",
                      fontSize: 12,
                    }}
                  />
                  <Bar dataKey="analyzed" fill="var(--color-primary)" radius={3} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            <ul className="divide-y divide-border text-sm">
              {monitor.data.runs.map((run) => (
                <li key={run.id} className="flex flex-wrap items-center gap-2 py-2">
                  <span className="w-14 text-muted-foreground">{formatTime(run.startedAt)}</span>
                  <Badge
                    variant={
                      run.status === "ok"
                        ? "secondary"
                        : run.status === "rate_limited"
                          ? "outline"
                          : "destructive"
                    }
                  >
                    {run.status === "ok"
                      ? "ok"
                      : run.status === "rate_limited"
                        ? pt.monitorState.RATE_LIMITED
                        : pt.common.error}
                  </Badge>
                  <span className="text-muted-foreground">
                    {run.analyzed} {pt.monitor.runAnalyzed} · {run.matches} {pt.monitor.runMatches}{" "}
                    · {run.sent} {pt.monitor.runSent} · {Math.round(run.durationMs / 100) / 10}s
                  </span>
                  {run.error ? (
                    <span className="w-full text-xs text-destructive">{run.error}</span>
                  ) : null}
                </li>
              ))}
            </ul>
          </section>
        </>
      ) : null}
    </div>
  );
}
