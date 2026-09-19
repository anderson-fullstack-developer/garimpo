"use client";

import { useParams } from "next/navigation";

import { ErrorState, LoadingBlock, PageHeader } from "@/components/states";
import { AlertForm } from "@/features/alerts/AlertForm";
import { useAlert } from "@/hooks/useGarimpo";
import { pt } from "@/i18n/pt";
import { APP_NAME } from "@/config/brand";

export function EditAlertPage() {
  const { id } = useParams<{ id: string }>();
  const query = useAlert(id);

  return (
    <div className="space-y-5">
      <PageHeader title={query.data?.name ?? pt.alerts.title} subtitle={pt.alerts.subtitle} />
      {query.isLoading ? <LoadingBlock /> : null}
      {query.isError ? <ErrorState error={query.error} onRetry={() => query.refetch()} /> : null}
      {query.data ? <AlertForm existing={query.data} /> : null}
    </div>
  );
}
