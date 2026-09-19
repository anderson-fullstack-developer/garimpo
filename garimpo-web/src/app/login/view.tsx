"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { useState } from "react";
import { z } from "zod";

import { AuthLayout } from "@/features/auth/AuthLayout";
import { PasswordField } from "@/features/auth/PasswordField";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/features/auth/AuthProvider";
import { errorMessage } from "@/components/states";
import { pt } from "@/i18n/pt";
import { APP_NAME } from "@/config/brand";
import { safeRedirect } from "@/lib/safe-redirect";

// Função: os textos saem no idioma atual (que pode mudar depois do carregamento).
const makeSchema = () =>
  z.object({
    email: z.string().email(pt.auth.invalidEmail),
    password: z.string().min(1, pt.misc.enterPassword),
  });
type FormValues = z.infer<ReturnType<typeof makeSchema>>;

export function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const redirect = safeRedirect(useSearchParams().get("redirect"));
  const [formError, setFormError] = useState<string | null>(null);

  const form = useForm<FormValues>({
    resolver: zodResolver(makeSchema()),
    defaultValues: { email: "", password: "" },
  });

  const onSubmit = form.handleSubmit(async (values) => {
    setFormError(null);
    try {
      const user = await login(values.email.trim().toLowerCase(), values.password);
      if (user.status === "PENDING") {
        router.push("/pending");
        return;
      }
      if (!user.verified) {
        router.push("/verify");
        return;
      }
      router.push(redirect ?? "/app");
    } catch (error) {
      setFormError(errorMessage(error));
    }
  });

  return (
    <AuthLayout
      title={pt.auth.loginTitle}
      subtitle={pt.auth.loginSubtitle}
      footer={
        <>
          {pt.auth.noAccount}{" "}
          <Link href="/register" className="font-medium text-primary hover:underline">
            {pt.auth.signUp}
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        <div className="space-y-2">
          <Label htmlFor="email">{pt.auth.email}</Label>
          <Input id="email" type="email" autoComplete="email" {...form.register("email")} />
          {form.formState.errors.email ? (
            <p className="text-xs text-destructive">{form.formState.errors.email.message}</p>
          ) : null}
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label htmlFor="password">{pt.auth.password}</Label>
            <Link href="/forgot" className="text-xs text-primary hover:underline">
              {pt.auth.forgotLink}
            </Link>
          </div>
          <PasswordField
            id="password"
            autoComplete="current-password"
            {...form.register("password")}
          />
          {form.formState.errors.password ? (
            <p className="text-xs text-destructive">{form.formState.errors.password.message}</p>
          ) : null}
        </div>

        {formError ? (
          <p role="alert" aria-live="assertive" className="text-sm text-destructive">
            {formError}
          </p>
        ) : null}

        <Button type="submit" className="w-full" disabled={form.formState.isSubmitting}>
          {form.formState.isSubmitting ? pt.common.loading : pt.auth.signIn}
        </Button>
      </form>
    </AuthLayout>
  );
}
