import { Compass } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { Avatar } from "@/components/ui/avatar";
import { buttonVariants } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Field, Select } from "@/components/ui/field";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelBody } from "@/components/ui/panel";
import { Tag } from "@/components/ui/tag";
import { StudentAdviceDisclaimer } from "@/features/mentorship/disclaimer";
import { GuideStatsLine } from "@/features/mentorship/guide-stats";
import { RequestButton } from "@/features/mentorship/request-dialog";
import { ForbiddenState } from "@/features/shell/forbidden-state";
import { loaded, serverApi } from "@/lib/api/server";

type DirectoryProps = {
  params: Promise<{ subjectId: string }>;
  searchParams: Promise<{ specialty?: string; semester?: string; teacher?: string }>;
};

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("guides");
  return { title: t("findTitle") };
}

/** "Bələdçi tap" (§5.2): available guides of one subject, ranked by the API, filterable. */
export default async function GuideDirectoryPage({ params, searchParams }: DirectoryProps) {
  const t = await getTranslations("guides");
  const { subjectId } = await params;
  const filters = await searchParams;
  const result = await (
    await serverApi()
  )
    .GET("/api/v1/subjects/{subject_id}/guides", {
      params: {
        path: { subject_id: subjectId },
        query: {
          specialty: filters.specialty || undefined,
          semester: filters.semester || undefined,
          teacher: filters.teacher || undefined,
        },
      },
    })
    .then(loaded);
  if (result.status !== "ok") {
    return (
      <>
        <PageHeader
          title={t("findTitle")}
          breadcrumb={[{ label: t("title"), href: "/guides" }, { label: t("findTitle") }]}
        />
        <ForbiddenState />
      </>
    );
  }
  const directory = result.data;
  const select = (
    name: "specialty" | "semester" | "teacher",
    options: { id: string; label: string }[],
  ) => (
    <Field label={t(`directory.${name}`)}>
      <Select name={name} defaultValue={filters[name] ?? ""}>
        <option value="">{t("directory.all")}</option>
        {options.map((option) => (
          <option key={option.id} value={option.id}>
            {option.label}
          </option>
        ))}
      </Select>
    </Field>
  );
  return (
    <>
      <PageHeader
        title={directory.subject_name}
        description={t("directory.description", { code: directory.subject_code })}
        breadcrumb={[{ label: t("title"), href: "/guides" }, { label: directory.subject_name }]}
        actions={
          <>
            <Link
              href={`/guides/${directory.subject_id}/tips`}
              className={buttonVariants({ variant: "secondary" })}
            >
              {t("tips.link")}
            </Link>
            <RequestButton subjectId={directory.subject_id} variant="primary" />
          </>
        }
      />
      <div className="flex flex-col gap-6">
        <StudentAdviceDisclaimer />
        <Panel>
          <PanelBody className="p-4">
            <form
              method="get"
              aria-label={t("directory.filters")}
              className="grid gap-4 sm:grid-cols-3 sm:items-end"
            >
              {select("specialty", directory.specialties)}
              {select("semester", directory.semesters)}
              {select("teacher", directory.teachers)}
              <div>
                <button type="submit" className={buttonVariants({ variant: "secondary" })}>
                  {t("directory.apply")}
                </button>
              </div>
            </form>
          </PanelBody>
        </Panel>
        {directory.guides.length === 0 ? (
          <Panel className="px-4">
            <EmptyState icon={Compass} message={t("directory.empty")} />
          </Panel>
        ) : (
          <ul aria-label={t("directory.listLabel")} className="flex flex-col gap-4">
            {directory.guides.map((guide) => (
              <li key={guide.user.id}>
                <Panel>
                  <PanelBody className="flex flex-col gap-3 p-4">
                    <div className="flex items-start gap-3">
                      <Avatar
                        name={guide.user.display_name}
                        src={guide.user.photo_url ?? undefined}
                        size={40}
                        decorative
                      />
                      <div className="flex min-w-0 flex-1 flex-col gap-1">
                        <span className="font-medium break-words">{guide.user.display_name}</span>
                        <span className="flex flex-wrap gap-2">
                          <Tag tone="accent" icon={Compass}>
                            {t("directory.badge", { semester: guide.semester })}
                          </Tag>
                          {guide.same_teacher ? (
                            <Tag tone="info">{t("directory.sameTeacher")}</Tag>
                          ) : null}
                          {guide.same_specialty ? (
                            <Tag tone="info">{t("directory.sameSpecialty")}</Tag>
                          ) : null}
                        </span>
                      </div>
                    </div>
                    <p className="flex flex-wrap gap-x-4 text-sm text-muted">
                      {guide.specialty_name ? <span>{guide.specialty_name}</span> : null}
                      {guide.teacher_name ? (
                        <span>{t("directory.takenWith", { name: guide.teacher_name })}</span>
                      ) : null}
                      {guide.grade_exact !== null ? (
                        <span className="tabular">
                          {t("directory.grade", { grade: String(guide.grade_exact) })}
                        </span>
                      ) : guide.grade_range ? (
                        <span className="tabular">
                          {t("directory.grade", { grade: guide.grade_range })}
                        </span>
                      ) : null}
                    </p>
                    {guide.bio ? <p className="break-words">{guide.bio}</p> : null}
                    <GuideStatsLine stats={guide.stats} />
                    <div>
                      <RequestButton
                        subjectId={directory.subject_id}
                        guide={{ id: guide.user.id, display_name: guide.user.display_name }}
                      />
                    </div>
                  </PanelBody>
                </Panel>
              </li>
            ))}
          </ul>
        )}
      </div>
    </>
  );
}
