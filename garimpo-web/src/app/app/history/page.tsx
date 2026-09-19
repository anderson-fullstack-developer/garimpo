import type { Metadata } from "next";

import { serverMessages } from "@/i18n/server";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { APP_NAME } from "@/config/brand";
import { FEATURES } from "@/config/features";
import { HistoryPage } from "./view";

export async function generateMetadata(): Promise<Metadata> {
  const m = await serverMessages();
  return { title: `${m.history.title} — ${APP_NAME}`, description: m.meta.historyDesc };
}

export default function Page() {
  if (!FEATURES.history) notFound();
  return (
    <Suspense>
      <HistoryPage />
    </Suspense>
  );
}
