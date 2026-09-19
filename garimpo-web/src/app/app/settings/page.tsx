import type { Metadata } from "next";

import { serverMessages } from "@/i18n/server";
import { Suspense } from "react";

import { APP_NAME } from "@/config/brand";
import { SettingsPage } from "./view";

export async function generateMetadata(): Promise<Metadata> {
  const m = await serverMessages();
  return { title: `${m.settings.title} — ${APP_NAME}`, description: m.meta.settingsDesc };
}

export default function Page() {
  return (
    <Suspense>
      <SettingsPage />
    </Suspense>
  );
}
