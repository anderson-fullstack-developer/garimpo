"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";

import { AuthLayout } from "@/features/auth/AuthLayout";
import { PasswordField, PasswordStrength } from "@/features/auth/PasswordField";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { errorMessage } from "@/components/states";
import { api } from "@/lib/api";
import { pt } from "@/i18n/pt";
import { APP_NAME } from "@/config/brand";

export function ResetPage() {
  const urlToken = useSearchParams().get("token") ?? undefined;
  const [pasted, setPasted] = useState("");
  const token = urlToken ?? (pasted.trim() || undefined);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  return (
    <AuthLayout
      title={pt.auth.resetTitle}
      footer={
        <Link href="/login" className="font-medium text-primary hover:underline">
          {pt.auth.signIn}
        </Link>
      }
    >
      {done ? (
        <p aria-live="polite" className="text-center text-sm text-muted-foreground">
          {pt.auth.resetDone}
        </p>
      ) : (
        <form
          className="space-y-4"
          onSubmit={async (event) => {
            event.preventDefault();
            setError(null);
            if (!token) return setError(pt.auth.resetCodeHelp);
            if (password.length < 10) return setError(pt.auth.passwordRules);
            if (password !== confirm) return setError(pt.auth.passwordsDontMatch);
            setLoading(true);
            try {
              await api.auth.reset({ token: token ?? "", password });
              setDone(true);
            } catch (err) {
              setError(errorMessage(err));
            } finally {
              setLoading(false);
            }
          }}
        >
          {!urlToken ? (
            <div className="space-y-2">
              <Label htmlFor="code">{pt.auth.resetCode}</Label>
              <Input
                id="code"
                autoComplete="off"
                spellCheck={false}
                value={pasted}
                onChange={(e) => setPasted(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">{pt.auth.resetCodeHelp}</p>
            </div>
          ) : null}
          <div className="space-y-2">
            <Label htmlFor="password">{pt.auth.password}</Label>
            <PasswordField
              id="password"
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <PasswordStrength password={password} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="confirm">{pt.auth.confirmPassword}</Label>
            <PasswordField
              id="confirm"
              autoComplete="new-password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
            />
          </div>
          {error ? (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          ) : null}
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? pt.common.saving : pt.common.save}
          </Button>
        </form>
      )}
    </AuthLayout>
  );
}
