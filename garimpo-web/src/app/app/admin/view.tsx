"use client";

import { notFound } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { MoreHorizontal } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ErrorState, LoadingList, PageHeader, errorMessage } from "@/components/states";
import { useAuth } from "@/features/auth/AuthProvider";
import { countryLabel } from "@/config/countries";
import { api } from "@/lib/api";
import type { AdminAccess, AdminAction, AdminUser } from "@/lib/api/types";
import { qk } from "@/hooks/useGarimpo";
import { formatDate, formatDateTime, relativeTime } from "@/lib/format";
import { pt } from "@/i18n/pt";

const ACCESS_VARIANT: Record<AdminAccess, "default" | "secondary" | "outline" | "destructive"> = {
  admin: "default",
  paid: "default",
  trial: "secondary",
  expired: "destructive",
  unverified: "outline",
};

function Card({ label, value, warn }: { label: string; value: number; warn?: boolean }) {
  return (
    <div className="surface p-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p
        className={
          warn && value > 0 ? "text-2xl font-semibold text-destructive" : "text-2xl font-semibold"
        }
      >
        {value}
      </p>
    </div>
  );
}

export function AdminPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [access, setAccess] = useState("all");
  const [onlyErrors, setOnlyErrors] = useState(false);

  if (user && user.role !== "ADMIN") throw notFound();

  const overview = useQuery({ queryKey: qk.adminOverview, queryFn: () => api.admin.overview() });
  const users = useQuery({
    queryKey: [...qk.adminUsers(search), access],
    queryFn: () =>
      api.admin.users({
        ...(search ? { q: search } : {}),
        ...(access !== "all" ? { access } : {}),
      }),
  });
  const runs = useQuery({
    queryKey: [...qk.adminRuns(onlyErrors ? "error" : ""), "list"],
    queryFn: () => api.admin.runs(onlyErrors ? { status: "error" } : {}),
    refetchInterval: 15000,
  });

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["admin"] });
  };

  const act = async (target: AdminUser, action: AdminAction) => {
    try {
      await api.admin.updateUser(target.id, { action, days: 7 });
      toast.success(pt.adm.done);
      refresh();
    } catch (error) {
      toast.error(errorMessage(error));
    }
  };

  const remove = async (target: AdminUser) => {
    if (!window.confirm(`${target.email}\n\n${pt.adm.confirmDelete}`)) return;
    try {
      await api.admin.deleteUser(target.id);
      toast.success(pt.adm.done);
      refresh();
    } catch (error) {
      toast.error(errorMessage(error));
    }
  };

  const accessLabel = (value: AdminAccess) => pt.adm[`access_${value}` as const];
  const o = overview.data;
  const t = pt.adm;

  return (
    <div className="space-y-5">
      <PageHeader title={t.title} />

      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">{t.tabOverview}</TabsTrigger>
          <TabsTrigger value="users">{t.tabUsers}</TabsTrigger>
          <TabsTrigger value="runs">{t.tabRuns}</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="pt-4">
          {overview.isLoading ? <LoadingList rows={2} /> : null}
          {overview.isError ? (
            <ErrorState error={overview.error} onRetry={() => overview.refetch()} />
          ) : null}
          {o ? (
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <Card label={t.cardUsers} value={o.users} />
              <Card label={t.cardNew} value={o.newThisWeek} />
              <Card label={t.cardVerified} value={o.verified} />
              <Card label={t.cardUnverified} value={o.unverified} />
              <Card label={t.cardTrial} value={o.inTrial} />
              <Card label={t.cardPaid} value={o.paid} />
              <Card label={t.cardExpired} value={o.expired} />
              <Card label={t.cardSuspended} value={o.suspended} />
              <Card label={t.cardAlerts} value={o.alerts} />
              <Card label={t.cardDestinations} value={o.destinations} />
              <Card label={t.cardItems} value={o.items} />
              <Card label={t.cardMonitor} value={o.monitorOn} />
              <Card label={t.cardRuns} value={o.runsLastDay} />
              <Card label={t.cardErrors} value={o.runErrorsLastDay} warn />
            </div>
          ) : null}
        </TabsContent>

        <TabsContent value="users" className="space-y-3 pt-4">
          <div className="flex flex-wrap items-center gap-2">
            <Input
              className="max-w-xs"
              placeholder={t.search}
              aria-label={t.search}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <Select value={access} onValueChange={setAccess}>
              <SelectTrigger className="w-44" aria-label={t.colAccess}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t.allAccess}</SelectItem>
                {(["trial", "paid", "expired", "unverified", "admin"] as const).map((a) => (
                  <SelectItem key={a} value={a}>
                    {accessLabel(a)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {users.isLoading ? <LoadingList rows={4} /> : null}
          {users.isError ? (
            <ErrorState error={users.error} onRetry={() => users.refetch()} />
          ) : null}
          {users.data ? (
            <div className="surface overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t.colEmail}</TableHead>
                    <TableHead>{t.colAccess}</TableHead>
                    <TableHead>{t.colUntil}</TableHead>
                    <TableHead>{t.colAlerts}</TableHead>
                    <TableHead>{t.colDest}</TableHead>
                    <TableHead>{t.colMonitor}</TableHead>
                    <TableHead>{t.colCreated}</TableHead>
                    <TableHead>{t.colLogin}</TableHead>
                    <TableHead />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {users.data.map((u) => (
                    <TableRow key={u.id}>
                      <TableCell className="font-medium">
                        {u.email}
                        <span className="block text-xs text-muted-foreground">
                          {u.country ? countryLabel(u.country) : "—"} · {u.currency}
                          {u.stripeCustomer ? ` · ${t.stripe}` : ""}
                          {u.status === "SUSPENDED" ? " · ⛔" : ""}
                        </span>
                      </TableCell>
                      <TableCell>
                        <Badge variant={ACCESS_VARIANT[u.access]}>{accessLabel(u.access)}</Badge>
                      </TableCell>
                      <TableCell className="whitespace-nowrap text-xs">
                        {u.access === "trial" || u.access === "expired"
                          ? formatDate(u.trialEndsAt)
                          : "—"}
                      </TableCell>
                      <TableCell>{u.alerts}</TableCell>
                      <TableCell>{u.destinations}</TableCell>
                      <TableCell>{u.monitorEnabled ? t.on : t.off}</TableCell>
                      <TableCell className="whitespace-nowrap text-xs">
                        {formatDate(u.createdAt)}
                      </TableCell>
                      <TableCell className="whitespace-nowrap text-xs">
                        {u.lastLoginAt ? relativeTime(u.lastLoginAt) : t.never}
                      </TableCell>
                      <TableCell>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="icon" aria-label={t.actions}>
                              <MoreHorizontal className="size-4" aria-hidden />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem onSelect={() => void act(u, "grant_access")}>
                              {t.grant}
                            </DropdownMenuItem>
                            <DropdownMenuItem onSelect={() => void act(u, "revoke_access")}>
                              {t.revoke}
                            </DropdownMenuItem>
                            <DropdownMenuItem onSelect={() => void act(u, "extend_trial")}>
                              {t.extend}
                            </DropdownMenuItem>
                            <DropdownMenuItem onSelect={() => void act(u, "end_trial")}>
                              {t.endTrial}
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            {u.status === "SUSPENDED" ? (
                              <DropdownMenuItem onSelect={() => void act(u, "reactivate")}>
                                {t.reactivate}
                              </DropdownMenuItem>
                            ) : (
                              <DropdownMenuItem onSelect={() => void act(u, "suspend")}>
                                {t.suspend}
                              </DropdownMenuItem>
                            )}
                            {u.role === "ADMIN" ? (
                              <DropdownMenuItem onSelect={() => void act(u, "remove_admin")}>
                                {t.removeAdmin}
                              </DropdownMenuItem>
                            ) : (
                              <DropdownMenuItem onSelect={() => void act(u, "make_admin")}>
                                {t.makeAdmin}
                              </DropdownMenuItem>
                            )}
                            <DropdownMenuSeparator />
                            <DropdownMenuItem
                              className="text-destructive"
                              onSelect={() => void remove(u)}
                            >
                              {t.delete}
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    </TableRow>
                  ))}
                  {users.data.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={9} className="text-center text-sm text-muted-foreground">
                        {t.empty}
                      </TableCell>
                    </TableRow>
                  ) : null}
                </TableBody>
              </Table>
            </div>
          ) : null}
        </TabsContent>

        <TabsContent value="runs" className="space-y-3 pt-4">
          <Button
            variant={onlyErrors ? "default" : "outline"}
            size="sm"
            onClick={() => setOnlyErrors((v) => !v)}
          >
            {t.onlyErrors}
          </Button>
          {runs.isLoading ? <LoadingList rows={4} /> : null}
          {runs.isError ? <ErrorState error={runs.error} onRetry={() => runs.refetch()} /> : null}
          {runs.data ? (
            <div className="surface overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t.colWhen}</TableHead>
                    <TableHead>{t.runsCols}</TableHead>
                    <TableHead>{t.colDuration}</TableHead>
                    <TableHead>{t.colAnalyzed}</TableHead>
                    <TableHead>{t.colMatches}</TableHead>
                    <TableHead>{t.colResult}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {runs.data.map((r) => (
                    <TableRow key={r.id}>
                      <TableCell className="whitespace-nowrap text-xs">
                        {formatDateTime(r.startedAt)}
                      </TableCell>
                      <TableCell className="text-xs">{r.searchKey}</TableCell>
                      <TableCell className="text-xs">
                        {(r.durationMs / 1000).toFixed(1)} s
                      </TableCell>
                      <TableCell>{r.analyzed}</TableCell>
                      <TableCell>{r.matches}</TableCell>
                      <TableCell className="text-xs">
                        <Badge variant={r.status === "ok" ? "secondary" : "destructive"}>
                          {r.status}
                        </Badge>
                        {r.error ? (
                          <span className="ml-2 text-muted-foreground">{r.error}</span>
                        ) : null}
                      </TableCell>
                    </TableRow>
                  ))}
                  {runs.data.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={6} className="text-center text-sm text-muted-foreground">
                        {t.empty}
                      </TableCell>
                    </TableRow>
                  ) : null}
                </TableBody>
              </Table>
            </div>
          ) : null}
        </TabsContent>
      </Tabs>
    </div>
  );
}
