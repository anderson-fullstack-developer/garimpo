"use client";

import Link from "next/link";
import { useState } from "react";
import { Send } from "lucide-react";

import { AuthLayout } from "@/features/auth/AuthLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import { pt } from "@/i18n/pt";

export function ForgotPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);

  return (
    <AuthLayout
      title={pt.auth.forgotTitle}
      subtitle={pt.auth.forgotSubtitle}
      footer={
        <Link href="/login" className="font-medium text-primary hover:underline">
          {pt.auth.signIn}
        </Link>
      }
    >
      {sent ? (
        <div className="space-y-4 text-center">
          <p aria-live="polite" className="text-sm text-muted-foreground">
            {pt.auth.forgotSentTelegram}
          </p>
          <Button asChild variant="outline" className="w-full">
            <Link href="/reset">{pt.auth.resetCode}</Link>
          </Button>
        </div>
      ) : (
        <form
          className="space-y-4"
          onSubmit={async (event) => {
            event.preventDefault();
            setLoading(true);
            try {
              await api.auth.forgot(email.trim().toLowerCase());
            } finally {
              setLoading(false);
              setSent(true);
            }
          }}
        >
          <div className="space-y-2">
            <Label htmlFor="email">{pt.auth.email}</Label>
            <Input
              id="email"
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <Button type="submit" className="w-full" disabled={loading}>
            <Send className="mr-2 size-4" aria-hidden />
            {loading ? pt.common.loading : pt.auth.forgotViaTelegram}
          </Button>
          <p className="text-center text-xs text-muted-foreground">{pt.auth.forgotTelegramHint}</p>
        </form>
      )}
    </AuthLayout>
  );
}
