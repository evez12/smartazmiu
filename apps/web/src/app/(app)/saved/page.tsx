import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { PageHeader } from "@/components/ui/page-header";
import { SavedList } from "@/features/chat/saved-list";
import { ForbiddenState } from "@/features/shell/forbidden-state";
import { getCurrentUser } from "@/lib/api/server";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("saved");
  return { title: t("title") };
}

export default async function SavedMessagesPage() {
  const t = await getTranslations("saved");
  const me = await getCurrentUser();
  return (
    <>
      <PageHeader
        title={t("title")}
        description={t("description")}
        breadcrumb={[{ label: t("title") }]}
      />
      {me.status === "ok" ? <SavedList currentUserId={me.user.id} /> : <ForbiddenState />}
    </>
  );
}
