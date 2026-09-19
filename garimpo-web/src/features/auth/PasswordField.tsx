import { Eye, EyeOff } from "lucide-react";
import { forwardRef, useState } from "react";

import { Input } from "@/components/ui/input";
import { pt } from "@/i18n/pt";
import { cn } from "@/lib/utils";

export const PasswordField = forwardRef<HTMLInputElement, React.ComponentProps<"input">>(
  function PasswordField({ className, ...props }, ref) {
    const [visible, setVisible] = useState(false);
    return (
      <div className="relative">
        <Input
          ref={ref}
          type={visible ? "text" : "password"}
          className={cn("pr-10", className)}
          {...props}
        />
        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          aria-label={visible ? pt.auth.hidePassword : pt.auth.showPassword}
          className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-muted-foreground hover:text-foreground"
        >
          {visible ? (
            <EyeOff className="size-4" aria-hidden />
          ) : (
            <Eye className="size-4" aria-hidden />
          )}
        </button>
      </div>
    );
  },
);

export function passwordScore(password: string): number {
  let score = 0;
  if (password.length >= 10) score += 1;
  if (password.length >= 14) score += 1;
  if (/[A-Z]/.test(password) && /[a-z]/.test(password)) score += 1;
  if (/\d/.test(password)) score += 1;
  if (/[^A-Za-z0-9]/.test(password)) score += 1;
  return Math.min(score, 4);
}

export function PasswordStrength({ password }: { password: string }) {
  const score = passwordScore(password);
  const labels = [pt.misc.pw0, pt.misc.pw1, pt.misc.pw2, pt.misc.pw3, pt.misc.pw4];
  return (
    <div className="space-y-1" aria-live="polite">
      <div className="flex gap-1">
        {[0, 1, 2, 3].map((i) => (
          <span
            key={i}
            className={cn("h-1 flex-1 rounded-full", i < score ? "bg-primary" : "bg-border")}
          />
        ))}
      </div>
      <p className="text-xs text-muted-foreground">
        {pt.auth.passwordStrength}: {labels[score]} · {pt.auth.passwordRules}
      </p>
    </div>
  );
}
