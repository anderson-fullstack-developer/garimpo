"use client";

import { PageHeader } from "@/components/states";
import { AlertForm } from "@/features/alerts/AlertForm";
import { pt } from "@/i18n/pt";
import { APP_NAME } from "@/config/brand";

export function NewAlertPage() {
  return (
    <div className="space-y-5">
      <PageHeader title={pt.alerts.newAlert} subtitle={pt.alerts.subtitle} />
      <AlertForm />
    </div>
  );
}
