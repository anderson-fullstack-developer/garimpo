import type { Metadata } from "next";

import { serverMessages } from "@/i18n/server";
import { Suspense } from "react";

import { APP_NAME } from "@/config/brand";
import { NewAlertPage } from "./view";

export async function generateMetadata(): Promise<Metadata> {
  const m = await serverMessages();
  return { title: `${m.alerts.newAlert} — ${APP_NAME}`, description: m.meta.alertsNewDesc };
}

export default function Page() {
  return (
    <Suspense>
      <NewAlertPage />
    </Suspense>
  );
}
