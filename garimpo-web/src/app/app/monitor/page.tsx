import type { Metadata } from "next";

import { serverMessages } from "@/i18n/server";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { APP_NAME } from "@/config/brand";
import { FEATURES } from "@/config/features";
import { MonitorPage } from "./view";

export async function generateMetadata(): Promise<Metadata> {
  const m = await serverMessages();
  return { title: `${m.monitor.title} — ${APP_NAME}`, description: m.meta.monitorDesc };
}

export default function Page() {
  if (!FEATURES.monitorPage) notFound();
  return (
    <Suspense>
      <MonitorPage />
    </Suspense>
  );
}
