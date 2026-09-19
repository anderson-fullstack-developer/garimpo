import type { Metadata } from "next";
import { Suspense } from "react";

import { APP_NAME } from "@/config/brand";
import { serverMessages } from "@/i18n/server";
import { Landing } from "./view";

export async function generateMetadata(): Promise<Metadata> {
  const m = await serverMessages();
  return { title: `${APP_NAME} — ${m.landing.heroTitle}`, description: m.meta.tagline };
}

export default function Page() {
  return (
    <Suspense>
      <Landing />
    </Suspense>
  );
}
