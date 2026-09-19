import type { Metadata } from "next";

import { serverMessages } from "@/i18n/server";
import { Suspense } from "react";

import { APP_NAME } from "@/config/brand";
import { AlertsPage } from "./view";

export async function generateMetadata(): Promise<Metadata> {
  const m = await serverMessages();
  return { title: `${m.alerts.title} — ${APP_NAME}`, description: m.meta.alertsDesc };
}

export default function Page() {
  return (
    <Suspense>
      <AlertsPage />
    </Suspense>
  );
}
