import type { Metadata } from "next";

import { serverMessages } from "@/i18n/server";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { APP_NAME } from "@/config/brand";
import { FEATURES } from "@/config/features";
import { BillingPage } from "./view";

export async function generateMetadata(): Promise<Metadata> {
  const m = await serverMessages();
  return { title: `${m.billing.title} — ${APP_NAME}`, description: m.meta.billingDesc };
}

export default function Page() {
  if (!FEATURES.billing) notFound();
  return (
    <Suspense>
      <BillingPage />
    </Suspense>
  );
}
