"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { DestinationsPage } from "@/app/app/destinations/view";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
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
import { PageHeader, errorMessage } from "@/components/states";
import { PasswordField } from "@/features/auth/PasswordField";
import { useAuth } from "@/features/auth/AuthProvider";
import { api } from "@/lib/api";
import { pt, t } from "@/i18n/pt";
import { APP_NAME } from "@/config/brand";
import { SubscriptionCard } from "@/features/billing/SubscriptionCard";
import { RegionSettings } from "@/features/settings/RegionSettings";

export function SettingsPage() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const tabParam = useSearchParams().get("tab");
  const initialTab = ["telegram", "account", "region", "privacy"].includes(tabParam ?? "")
    ? (tabParam as string)
    : "telegram";
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteWord, setDeleteWord] = useState("");

  return (
    <div className="space-y-5">
      <PageHeader title={pt.settings.title} />

      <Tabs key={initialTab} defaultValue={initialTab}>
        <TabsList className="h-auto w-full flex-wrap justify-start">
          <TabsTrigger value="telegram">{pt.settings.tabTelegram}</TabsTrigger>
          <TabsTrigger value="account">{pt.settings.tabAccount}</TabsTrigger>
          <TabsTrigger value="region">{pt.settings.tabRegion}</TabsTrigger>
          <TabsTrigger value="privacy">{pt.settings.tabPrivacy}</TabsTrigger>
        </TabsList>

        <TabsContent value="telegram" className="space-y-4 pt-4">
          <DestinationsPage embedded />
        </TabsContent>

        <TabsContent value="account" className="space-y-4 pt-4">
          <SubscriptionCard />
          <div className="surface space-y-4 p-5">
            <div className="space-y-2">
              <Label htmlFor="email">{pt.settings.email}</Label>
              <Input id="email" value={user?.email ?? ""} readOnly />
            </div>
          </div>

          <form
            className="surface space-y-4 p-5"
            onSubmit={async (event) => {
              event.preventDefault();
              if (next.length < 10) {
                toast.error(pt.auth.passwordRules);
                return;
              }
              if (next !== confirm) {
                toast.error(pt.auth.passwordsDontMatch);
                return;
              }
              try {
                await api.me.changePassword({ current, next });
                toast.success(pt.settings.saved);
                setCurrent("");
                setNext("");
                setConfirm("");
              } catch (error) {
                toast.error(errorMessage(error));
              }
            }}
          >
            <h2 className="text-sm font-semibold">{pt.settings.changePassword}</h2>
            <div className="space-y-2">
              <Label htmlFor="current">{pt.settings.currentPassword}</Label>
              <PasswordField
                id="current"
                value={current}
                onChange={(e) => setCurrent(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="next">{pt.settings.newPassword}</Label>
              <PasswordField id="next" value={next} onChange={(e) => setNext(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirm">{pt.auth.confirmPassword}</Label>
              <PasswordField
                id="confirm"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
              />
            </div>
            <div className="flex flex-wrap gap-2">
              <Button type="submit">{pt.common.save}</Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => toast.success(pt.misc.sessionsEnded)}
              >
                {pt.settings.endSessions}
              </Button>
            </div>
          </form>
        </TabsContent>

        <TabsContent value="region" className="space-y-4 pt-4">
          <RegionSettings />
        </TabsContent>

        <TabsContent value="privacy" className="space-y-4 pt-4">
          <div className="surface space-y-3 p-5 text-sm">
            <div className="flex gap-4">
              <Link href="/terms" className="text-primary hover:underline">
                {pt.legal.terms}
              </Link>
              <Link href="/privacy" className="text-primary hover:underline">
                {pt.legal.privacy}
              </Link>
            </div>
            <p className="text-muted-foreground">{pt.settings.deleteAccountText}</p>
            <Button variant="destructive" onClick={() => setDeleteOpen(true)}>
              {pt.settings.deleteAccount}
            </Button>
          </div>
        </TabsContent>
      </Tabs>

      <AlertDialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{pt.settings.deleteAccount}</AlertDialogTitle>
            <AlertDialogDescription>{pt.settings.deleteAccountText}</AlertDialogDescription>
          </AlertDialogHeader>
          <div className="space-y-2">
            <Label htmlFor="deleteWord">
              {t(pt.settings.deleteConfirmLabel, { word: pt.settings.deleteConfirmWord })}
            </Label>
            <Input
              id="deleteWord"
              value={deleteWord}
              onChange={(e) => setDeleteWord(e.target.value)}
            />
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel>{pt.common.cancel}</AlertDialogCancel>
            <AlertDialogAction
              disabled={deleteWord !== pt.settings.deleteConfirmWord}
              onClick={async () => {
                try {
                  await api.me.delete();
                  await logout();
                  router.push("/");
                } catch (error) {
                  toast.error(errorMessage(error));
                }
              }}
            >
              {pt.common.delete}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
