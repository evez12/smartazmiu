import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { Banner } from "@/components/ui/banner";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelBody } from "@/components/ui/panel";
import { StudentAdviceDisclaimer } from "@/features/mentorship/disclaimer";
import { OptInForm } from "@/features/mentorship/opt-in-form";
import { ForbiddenState } from "@/features/shell/forbidden-state";
import { loaded, serverApi } from "@/lib/api/server";

type OptInProps = { params: Promise<{ subjectId: string }> };

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("guides");
  return { title: t("becomeTitle") };
}

/** Opt-in as a guide, or edit the profile (§5.2). Eligibility is checked again by the API on save. */
export default async function OptInPage({ params }: OptInProps) {
  const t = await getTranslations("guides");
  const { subjectId } = await params;
  const api = await serverApi();
  const eligible = await api.GET("/api/v1/guides/eligible").then(loaded);
  if (eligible.status !== "ok") return <ForbiddenState />;
  const entry = eligible.data.find((item) => item.subject_id === subjectId);
  const existing = await api.GET("/api/v1/subjects/{subject_id}/guides/me", {
    params: { path: { subject_id: subjectId } },
  });
  const profile = existing.data ?? null;
  if (!entry && !profile) {
    if (existing.response.status !== 404) notFound();
    return (
      <>
        <PageHeader
          title={t("becomeTitle")}
          breadcrumb={[{ label: t("title"), href: "/guides" }, { label: t("becomeTitle") }]}
        />
        <Banner tone="warning" title={t("optInPage.notEligible")} />
      </>
    );
  }
  const subjectName = entry?.subject_name ?? profile?.subject_name ?? "";
  const editing = profile !== null && profile.active;
  return (
    <>
      <PageHeader
        title={
          editing
            ? t("optInPage.editTitle", { subject: subjectName })
            : t("optInPage.title", { subject: subjectName })
        }
        description={t("optInPage.description", {
          semester: entry?.semester ?? profile?.semester ?? "",
        })}
        breadcrumb={[{ label: t("title"), href: "/guides" }, { label: subjectName }]}
      />
      <div className="flex flex-col gap-6">
        <StudentAdviceDisclaimer />
        <Panel>
          <PanelBody className="p-4">
            <OptInForm
              subjectId={subjectId}
              teacherName={entry?.teacher_name ?? null}
              profile={profile}
            />
          </PanelBody>
        </Panel>
      </div>
    </>
  );
}
