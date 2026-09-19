import type { Metadata } from "next";
import { Suspense } from "react";

import { APP_NAME } from "@/config/brand";
import { PrivacyPage } from "./view";

export const metadata: Metadata = {
  title: `Privacy Policy — ${APP_NAME}`,
  description: "Privacy Policy of the Garimpo alert service.",
};

export default function Page() {
  return (
    <Suspense>
      <PrivacyPage />
    </Suspense>
  );
}
