import type { Metadata } from "next";
import { Suspense } from "react";

import { APP_NAME } from "@/config/brand";
import { TermsPage } from "./view";

export const metadata: Metadata = {
  title: `Terms of Service — ${APP_NAME}`,
  description: "Terms of Service of the Garimpo alert service.",
};

export default function Page() {
  return (
    <Suspense>
      <TermsPage />
    </Suspense>
  );
}
