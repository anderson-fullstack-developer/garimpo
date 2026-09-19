import type { Metadata } from "next";

import { serverMessages } from "@/i18n/server";
import { Suspense } from "react";

import { APP_NAME } from "@/config/brand";
import { ResetPage } from "./view";

export async function generateMetadata(): Promise<Metadata> {
  const m = await serverMessages();
  return { title: `${m.meta.reset} — ${APP_NAME}`, description: m.meta.resetDesc };
}

export default function Page() {
  return (
    <Suspense>
      <ResetPage />
    </Suspense>
  );
}
