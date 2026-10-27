import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { Banner } from "@/components/ui/banner";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelBody } from "@/components/ui/panel";
import { TipForm } from "@/features/knowledge/tip-form";
import { StudentAdviceDisclaimer } from "@/features/mentorship/disclaimer";
import { ForbiddenState } from "@/features/shell/forbidden-state";
import { loaded, serverApi } from "@/lib/api/server";

type WriteTipProps = {
  params: Promise<{ subjectId: string }>;
  searchParams: Promise<{ semester?: string }>;
};

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("guides.tips");
  return { title: t("write") };
}

/** Write or edit the card for a subject; only semesters the person passed are offered (server checks too). */
export default async function WriteTipPage({ params, searchParams }: WriteTipProps) {
  const t = await getTranslations("guides.tips");
  const tGuides = await getTranslations("guides");
  const { subjectId } = await params;
  const { semester } = await searchParams;
  const api = await serverApi();
  const [eligible, mine] = await Promise.all([
    api.GET("/api/v1/tips/eligible").then(loaded),
    api
      .GET("/api/v1/subjects/{subject_id}/tips/mine", {
        params: { path: { subject_id: subjectId } },
      })
      .then(loaded),
  ]);
  if (eligible.status !== "ok" || mine.status !== "ok") return <ForbiddenState />;
  const passed = eligible.data.filter((item) => item.subject_id === subjectId);
  const breadcrumb = [{ label: tGuides("title"), href: "/guides" }, { label: t("write") }];
  if (passed.length === 0) {
    return (
      <>
        <PageHeader title={t("write")} breadcrumb={breadcrumb} />
        <Banner tone="warning" title={t("notEligible")} />
      </>
    );
  }
  const chosen = passed.find((item) => item.semester_id === semester) ?? passed[0]!;
  // Materials of the subject the author may link to; an unreadable catalogue just offers none.
  const catalog = await api.GET("/api/v1/subjects/{subject_id}/materials", {
    params: { path: { subject_id: subjectId } },
  });
  const materials = (catalog.data?.materials ?? []).map((item) => ({
    id: item.id,
    title: item.title,
  }));
  return (
    <>
      <PageHeader
        title={t("writeTitle", { subject: chosen.subject_name })}
        description={t("writeDescription", { semester: chosen.semester })}
        breadcrumb={breadcrumb}
      />
      <div className="flex flex-col gap-6">
        <StudentAdviceDisclaimer />
        <Panel>
          <PanelBody className="p-4">
            <TipForm
              subjectId={subjectId}
              semesters={passed.map((item) => ({ id: item.semester_id, label: item.semester }))}
              initialSemester={chosen.semester_id}
              existing={mine.data}
              materials={materials}
            />
          </PanelBody>
        </Panel>
      </div>
    </>
  );
}
