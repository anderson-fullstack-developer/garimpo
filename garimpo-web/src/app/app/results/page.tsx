import type { Metadata } from "next";

import { serverMessages } from "@/i18n/server";
import { Suspense } from "react";

import { APP_NAME } from "@/config/brand";
import { ResultsPage } from "./view";

export async function generateMetadata(): Promise<Metadata> {
  const m = await serverMessages();
  return { title: `${m.feed.title} — ${APP_NAME}`, description: m.feed.subtitle };
}

export default function Page() {
  return (
    <Suspense>
      <ResultsPage />
    </Suspense>
  );
}
