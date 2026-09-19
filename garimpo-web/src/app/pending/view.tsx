"use client";

import { useRouter } from "next/navigation";
import { Clock } from "lucide-react";

import { AuthLayout } from "@/features/auth/AuthLayout";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/features/auth/AuthProvider";
import { pt } from "@/i18n/pt";
import { APP_NAME } from "@/config/brand";

export function PendingPage() {
  const { logout } = useAuth();
  const router = useRouter();

  return (
    <AuthLayout title={pt.auth.pendingTitle}>
      <div className="space-y-4 text-center">
        <Clock className="mx-auto size-8 text-primary" aria-hidden />
        <p className="text-sm text-muted-foreground">{pt.auth.pendingText}</p>
        <Button
          variant="outline"
          className="w-full"
          onClick={async () => {
            await logout();
            router.push("/login");
          }}
        >
          {pt.common.logout}
        </Button>
      </div>
    </AuthLayout>
  );
}
