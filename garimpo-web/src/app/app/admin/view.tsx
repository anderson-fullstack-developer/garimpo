"use client";

import { notFound } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis } from "recharts";
import { ErrorState, LoadingList, PageHeader, errorMessage } from "@/components/states";
import { useAuth } from "@/features/auth/AuthProvider";
import { api } from "@/lib/api";
import { qk } from "@/hooks/useGarimpo";
import { formatDate, formatDuration, formatMoney, formatTime } from "@/lib/format";
import { pt } from "@/i18n/pt";
import { APP_NAME } from "@/config/brand";

const statusLabel = () =>
  ({
    PENDING: pt.admin.statusPENDING,
    ACTIVE: pt.admin.statusACTIVE,
    SUSPENDED: pt.admin.statusSUSPENDED,
  }) as const;

export function AdminPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteDays, setInviteDays] = useState(7);

  if (user && user.role !== "ADMIN") throw notFound();

  const users = useQuery({
    queryKey: qk.adminUsers(search),
    queryFn: () => api.admin.users(search ? { q: search } : {}),
  });
  const invites = useQuery({ queryKey: qk.adminInvites, queryFn: () => api.admin.invites() });
  const runs = useQuery({ queryKey: qk.adminRuns(), queryFn: () => api.admin.runs() });
  const stats = useQuery({ queryKey: qk.adminStats, queryFn: () => api.admin.stats() });

  return (
    <div className="space-y-5">
      <PageHeader title={pt.admin.title} />

      <Tabs defaultValue="users">
        <TabsList>
          <TabsTrigger value="users">{pt.admin.tabUsers}</TabsTrigger>
          <TabsTrigger value="invites">{pt.admin.tabInvites}</TabsTrigger>
          <TabsTrigger value="runs">{pt.admin.tabRuns}</TabsTrigger>
          <TabsTrigger value="business">{pt.admin.tabBusiness}</TabsTrigger>
        </TabsList>

        <TabsContent value="users" className="space-y-4 pt-4">
          <Input
            aria-label={pt.common.search}
            placeholder={pt.common.search}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="max-w-sm"
          />
          {users.isLoading ? <LoadingList rows={3} /> : null}
          {users.isError ? (
            <ErrorState error={users.error} onRetry={() => users.refetch()} />
          ) : null}
          {users.data ? (
            <div className="surface overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>E-mail</TableHead>
                    <TableHead>Plano</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>{pt.admin.createdAt}</TableHead>
                    <TableHead />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {users.data.map((row) => (
                    <TableRow key={row.id}>
                      <TableCell>{row.email}</TableCell>
                      <TableCell>
                        <Badge variant="secondary">{row.plan}</Badge>
                      </TableCell>
                      <TableCell>{statusLabel()[row.status]}</TableCell>
                      <TableCell>{formatDate(row.createdAt)}</TableCell>
                      <TableCell className="space-x-2 text-right">
                        {row.status === "PENDING" ? (
                          <Button
                            size="sm"
                            onClick={async () => {
                              await api.admin.updateUser(row.id, { status: "ACTIVE" });
                              void queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
                            }}
                          >
                            {pt.admin.approve}
                          </Button>
                        ) : null}
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={async () => {
                            await api.admin.updateUser(row.id, {
                              status: row.status === "SUSPENDED" ? "ACTIVE" : "SUSPENDED",
                            });
                            void queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
                          }}
                        >
                          {row.status === "SUSPENDED" ? pt.admin.reactivate : pt.admin.suspend}
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          ) : null}
        </TabsContent>

        <TabsContent value="invites" className="space-y-4 pt-4">
          <form
            className="surface flex flex-wrap items-end gap-3 p-4"
            onSubmit={async (event) => {
              event.preventDefault();
              try {
                await api.admin.createInvite({
                  ...(inviteEmail ? { email: inviteEmail } : {}),
                  expiresInDays: inviteDays,
                });
                setInviteEmail("");
                void queryClient.invalidateQueries({ queryKey: qk.adminInvites });
              } catch (error) {
                toast.error(errorMessage(error));
              }
            }}
          >
            <div className="space-y-2">
              <Label htmlFor="inviteEmail">{pt.admin.inviteEmail}</Label>
              <Input
                id="inviteEmail"
                type="email"
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="inviteDays">{pt.admin.inviteDays}</Label>
              <Input
                id="inviteDays"
                type="number"
                min={1}
                className="w-24"
                value={inviteDays}
                onChange={(e) => setInviteDays(Number(e.target.value))}
              />
            </div>
            <Button type="submit">{pt.admin.newInvite}</Button>
          </form>

          {invites.isLoading ? <LoadingList rows={2} /> : null}
          {invites.data ? (
            <div className="surface overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{pt.admin.code}</TableHead>
                    <TableHead>E-mail</TableHead>
                    <TableHead>{pt.admin.validity}</TableHead>
                    <TableHead />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {invites.data.map((invite) => (
                    <TableRow key={invite.id}>
                      <TableCell className="font-mono text-xs">{invite.code}</TableCell>
                      <TableCell>{invite.email ?? "—"}</TableCell>
                      <TableCell>{formatDate(invite.expiresAt)}</TableCell>
                      <TableCell className="space-x-2 text-right">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={async () => {
                            await navigator.clipboard.writeText(
                              `${window.location.origin}/register?invite=${invite.code}`,
                            );
                            toast.success(pt.common.copied);
                          }}
                        >
                          {pt.admin.copyLink}
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={async () => {
                            await api.admin.revokeInvite(invite.id);
                            void queryClient.invalidateQueries({ queryKey: qk.adminInvites });
                          }}
                        >
                          {pt.admin.revoke}
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          ) : null}
        </TabsContent>

        <TabsContent value="runs" className="space-y-4 pt-4">
          {runs.isLoading ? <LoadingList rows={3} /> : null}
          {runs.data ? (
            <ul className="surface divide-y divide-border p-2 text-sm">
              {runs.data.map((run) => (
                <li key={run.id} className="flex flex-wrap items-center gap-2 p-2">
                  <span className="w-14 text-muted-foreground">{formatTime(run.startedAt)}</span>
                  <Badge variant={run.status === "ok" ? "secondary" : "destructive"}>
                    {run.status}
                  </Badge>
                  <span className="text-muted-foreground">
                    {run.analyzed} analisados · {run.matches} novos · {run.sent} enviados
                  </span>
                </li>
              ))}
            </ul>
          ) : null}
        </TabsContent>

        <TabsContent value="business" className="space-y-4 pt-4">
          {stats.isLoading ? <LoadingList rows={2} /> : null}
          {stats.data ? (
            <>
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="surface p-4">
                  <p className="text-xs text-muted-foreground">{pt.admin.mrr}</p>
                  <p className="text-2xl font-semibold">{formatMoney(stats.data.mrr)}</p>
                </div>
                <div className="surface p-4">
                  <p className="text-xs text-muted-foreground">{pt.admin.detection}</p>
                  <p className="text-2xl font-semibold">
                    {formatDuration(stats.data.detectionP50Seconds)} /{" "}
                    {formatDuration(stats.data.detectionP95Seconds)}
                  </p>
                </div>
                <div className="surface p-4">
                  <p className="text-xs text-muted-foreground">{pt.admin.errorRate}</p>
                  <p className="text-2xl font-semibold">{stats.data.errorRatePct}%</p>
                </div>
              </div>

              <div className="surface p-4">
                <p className="mb-3 text-sm font-semibold">{pt.admin.usersByPlan}</p>
                <div className="h-48 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={Object.entries(stats.data.usersByPlan).map(([plan, total]) => ({
                        plan,
                        total,
                      }))}
                    >
                      <XAxis dataKey="plan" stroke="var(--color-muted-foreground)" fontSize={12} />
                      <Tooltip
                        contentStyle={{
                          background: "var(--color-popover)",
                          border: "1px solid var(--color-border)",
                          borderRadius: "var(--radius-lg)",
                          fontSize: 12,
                        }}
                      />
                      <Bar dataKey="total" fill="var(--color-primary)" radius={4} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </>
          ) : null}
        </TabsContent>
      </Tabs>
    </div>
  );
}
