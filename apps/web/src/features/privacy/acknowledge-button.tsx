"use client";

import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";

import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { unwrap } from "@/lib/api/browser";
import { useApi, useErrorMessage } from "@/lib/api/provider";

/** Records that the user read this notice version (consent record `privacy_notice`). */
export function AcknowledgeButton({ version }: { version: string }) {
  const t = useTranslations("privacy");
  const api = useApi();
  const router = useRouter();
  const toast = useToast();
  const errorMessage = useErrorMessage();
  const acknowledge = useMutation({
    mutationFn: async () =>
      unwrap(await api.POST("/api/v1/me/consents/privacy-notice", { body: { version } })),
    onSuccess: () => {
      toast({ title: t("acknowledged") });
      router.refresh();
    },
  });
  return (
    <div className="flex flex-col items-start gap-3">
      {acknowledge.isError ? (
        <Banner tone="danger" title={t("failedTitle")}>
          {errorMessage(acknowledge.error)}
        </Banner>
      ) : null}
      <Button
        variant="primary"
        loading={acknowledge.isPending}
        onClick={() => acknowledge.mutate()}
      >
        {t("acknowledge")}
      </Button>
    </div>
  );
}
