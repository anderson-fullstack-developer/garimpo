import type { Metadata } from "next";

import { serverMessages } from "@/i18n/server";

import { APP_NAME } from "@/config/brand";
import { VerifyPage } from "./view";

export async function generateMetadata(): Promise<Metadata> {
  const m = await serverMessages();
  return { title: `${m.meta.verify} — ${APP_NAME}`, description: m.meta.verifyDesc };
}

export default function Page() {
  return <VerifyPage />;
}
