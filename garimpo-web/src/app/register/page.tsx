import type { Metadata } from "next";

import { serverMessages } from "@/i18n/server";
import { Suspense } from "react";

import { APP_NAME } from "@/config/brand";
import { RegisterPage } from "./view";

export async function generateMetadata(): Promise<Metadata> {
  const m = await serverMessages();
  return { title: `${m.meta.register} — ${APP_NAME}`, description: m.meta.registerDesc };
}

export default function Page() {
  return (
    <Suspense>
      <RegisterPage />
    </Suspense>
  );
}
