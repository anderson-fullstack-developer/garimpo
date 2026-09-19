"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/features/auth/AuthProvider";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { useCallback, useEffect, useState } from "react";
import { z } from "zod";
import { MailCheck } from "lucide-react";

import { AuthLayout } from "@/features/auth/AuthLayout";
import { CaptchaBox } from "@/features/auth/CaptchaBox";
import { PasswordField, PasswordStrength } from "@/features/auth/PasswordField";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { errorMessage } from "@/components/states";
import { usePublicConfig } from "@/hooks/useGarimpo";
import { api } from "@/lib/api";
import { ApiError } from "@/lib/api/types";
import { pt, t } from "@/i18n/pt";
import { APP_NAME } from "@/config/brand";
import { COUNTRIES, countryLabel } from "@/config/countries";
import { useLanguage } from "@/i18n/LanguageProvider";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

/** O servidor responde "validação" para vários motivos; aqui o usuário vê o motivo de verdade. */
function registerError(error: unknown): string {
  if (error instanceof ApiError && error.code === "VALIDATION_ERROR") {
    const message = error.message.toLowerCase();
    if (message.includes("invite")) return pt.auth.inviteInvalid;
    if (message.includes("less common")) return pt.auth.weakPassword;
  }
  return errorMessage(error);
}

// Função (e não constante): os textos precisam sair no idioma atual, que muda depois do carregamento.
const makeSchema = () =>
  z
    .object({
      email: z.string().email(pt.auth.invalidEmail),
      password: z.string().min(10, pt.auth.passwordRules),
      confirm: z.string(),
      country: z.string().min(1, pt.auth.countryPlaceholder),
      inviteCode: z.string().optional(),
      terms: z.boolean().refine((v) => v, pt.auth.mustAcceptTerms),
    })
    .refine((data) => data.password === data.confirm, {
      path: ["confirm"],
      message: pt.auth.passwordsDontMatch,
    });
type FormValues = z.infer<ReturnType<typeof makeSchema>>;

export function RegisterPage() {
  const { data: config } = usePublicConfig();
  const [captchaToken, setCaptchaToken] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const form = useForm<FormValues>({
    resolver: zodResolver(makeSchema()),
    defaultValues: {
      email: "",
      password: "",
      confirm: "",
      country: "",
      inviteCode: "",
      terms: false,
    },
  });
  const password = form.watch("password");
  const { setLanguage } = useLanguage();
  const { login } = useAuth();
  const router = useRouter();

  const onToken = useCallback((token: string) => setCaptchaToken(token), []);

  const onSubmit = form.handleSubmit(async (values) => {
    setFormError(null);
    try {
      await api.auth.register({
        email: values.email.trim().toLowerCase(),
        password: values.password,
        inviteCode: values.inviteCode || undefined,
        country: values.country,
        captchaToken,
      });
    } catch (error) {
      setFormError(registerError(error));
      return;
    }
    // Sem e-mail para confirmar: entra direto e o passo seguinte é ligar o Telegram.
    try {
      await login(values.email.trim().toLowerCase(), values.password);
      router.push("/verify");
    } catch {
      setFormError(pt.auth.registerLoginHint);
    }
  });

  return (
    <AuthLayout
      title={pt.auth.registerTitle}
      subtitle={pt.auth.registerSubtitle}
      footer={
        <>
          {pt.auth.hasAccount}{" "}
          <Link href="/login" className="font-medium text-primary hover:underline">
            {pt.auth.signIn}
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
          <Label htmlFor="password">{pt.auth.password}</Label>
          <PasswordField id="password" autoComplete="new-password" {...form.register("password")} />
          <PasswordStrength password={password} />
          {form.formState.errors.password ? (
            <p className="text-xs text-destructive">{form.formState.errors.password.message}</p>
          ) : null}
        </div>

        <div className="space-y-2">
          <Label htmlFor="confirm">{pt.auth.confirmPassword}</Label>
          <PasswordField id="confirm" autoComplete="new-password" {...form.register("confirm")} />
          {form.formState.errors.confirm ? (
            <p className="text-xs text-destructive">{form.formState.errors.confirm.message}</p>
          ) : null}
        </div>

        <div className="space-y-2">
          <Label htmlFor="country">{pt.auth.country}</Label>
          <Select
            value={form.watch("country")}
            onValueChange={(code) => {
              form.setValue("country", code, { shouldValidate: true });
              setLanguage(code === "pt" ? "pt" : "en", true); // a tela já muda para o idioma sugerido
            }}
          >
            <SelectTrigger id="country">
              <SelectValue placeholder={pt.auth.countryPlaceholder} />
            </SelectTrigger>
            <SelectContent>
              {COUNTRIES.map((c) => (
                <SelectItem key={c.code} value={c.code}>
                  {countryLabel(c.code)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">{pt.auth.countryHelp}</p>
          {form.formState.errors.country ? (
            <p className="text-xs text-destructive">{form.formState.errors.country.message}</p>
          ) : null}
        </div>

        {config?.registrationMode === "INVITE" ? (
          <div className="space-y-2">
            <Label htmlFor="inviteCode">{pt.auth.inviteCode}</Label>
            <Input id="inviteCode" {...form.register("inviteCode")} />
          </div>
        ) : null}

        <CaptchaBox onToken={onToken} />

        <div className="flex items-start gap-2">
          <Checkbox
            id="terms"
            checked={form.watch("terms")}
            onCheckedChange={(v) => form.setValue("terms", v === true, { shouldValidate: true })}
          />
          <Label htmlFor="terms" className="text-sm font-normal leading-snug">
            {pt.auth.acceptTerms}
          </Label>
        </div>
        {form.formState.errors.terms ? (
          <p className="text-xs text-destructive">{form.formState.errors.terms.message}</p>
        ) : null}

        {formError ? (
          <p role="alert" className="text-sm text-destructive">
            {formError}
          </p>
        ) : null}

        <Button
          type="submit"
          className="w-full"
          disabled={form.formState.isSubmitting || !captchaToken}
        >
          {form.formState.isSubmitting ? pt.common.loading : pt.auth.signUp}
        </Button>
      </form>
    </AuthLayout>
  );
}
