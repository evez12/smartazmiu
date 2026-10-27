import { NotebookPen } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { Tag } from "@/components/ui/tag";
import { TextLink } from "@/components/ui/text-link";
import { TipActions } from "@/features/knowledge/tip-actions";
import { StudentAdviceDisclaimer } from "@/features/mentorship/disclaimer";
import { ForbiddenState } from "@/features/shell/forbidden-state";
import { loaded, serverApi } from "@/lib/api/server";

type TipsPageProps = { params: Promise<{ subjectId: string }> };

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("guides.tips");
  return { title: t("link") };
}

/** The subject page of §5.2 flow 5: published cards only, aggregated; no author names or grades (D-084). */
export default async function SubjectTipsPage({ params }: TipsPageProps) {
  const t = await getTranslations("guides.tips");
  const tGuides = await getTranslations("guides");
  const { subjectId } = await params;
  const result = await (
    await serverApi()
  )
    .GET("/api/v1/subjects/{subject_id}/tips", { params: { path: { subject_id: subjectId } } })
    .then(loaded);
  if (result.status !== "ok") {
    return (
      <>
        <PageHeader title={t("link")} breadcrumb={[{ label: tGuides("title"), href: "/guides" }]} />
        <ForbiddenState />
      </>
    );
  }
  const page = result.data;
  const maxBand = Math.max(1, ...page.workload.map((band) => band.count));
  return (
    <>
      <PageHeader
        title={t("title", { subject: page.subject_name })}
        description={t("description")}
        breadcrumb={[
          { label: tGuides("title"), href: "/guides" },
          { label: page.subject_name, href: `/guides/${page.subject_id}` },
          { label: t("link") },
        ]}
      />
      <div className="flex flex-col gap-6">
        <StudentAdviceDisclaimer />
        {page.tip_count === 0 ? (
          <Panel className="px-4">
            <EmptyState icon={NotebookPen} message={t("empty")} />
          </Panel>
        ) : (
          <>
            <Panel>
              <PanelHeader title={t("summary")} />
              <PanelBody className="grid gap-6 p-4 sm:grid-cols-2">
                <div className="flex flex-col gap-1">
                  <p className="text-sm text-muted tabular">
                    {t("count", { count: page.tip_count })}
                  </p>
                  {page.average_difficulty !== null ? (
                    <p className="text-lg font-semibold tabular">
                      {t("difficulty", { value: page.average_difficulty.toFixed(1) })}
                    </p>
                  ) : null}
                </div>
                <div className="flex flex-col gap-2">
                  <h3 className="font-medium">{t("workload")}</h3>
                  <ul className="flex flex-col gap-1 text-sm">
                    {page.workload.map((band) => (
                      <li key={band.weekly_hours} className="flex items-center gap-2">
                        <span className="w-28 shrink-0">{t(`hours.${band.weekly_hours}`)}</span>
                        <span aria-hidden className="h-2 flex-1 rounded-control bg-bg-subtle">
                          <span
                            className="block h-full rounded-control bg-primary"
                            style={{ width: `${(band.count / maxBand) * 100}%` }}
                          />
                        </span>
                        <span className="w-8 text-right tabular">{band.count}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </PanelBody>
            </Panel>
            {page.resources.length > 0 ? (
              <Panel>
                <PanelHeader title={t("resources")} />
                <ul className="divide-y divide-border">
                  {page.resources.map((resource) => (
                    <li
                      key={`${resource.title}-${resource.url}-${resource.material_id}`}
                      className="flex flex-wrap items-center gap-3 px-4 py-3"
                    >
                      <span className="min-w-0 flex-1 break-words">
                        {resource.material_id ? (
                          <TextLink href={`/materials/${page.subject_id}/${resource.material_id}`}>
                            {resource.title}
                          </TextLink>
                        ) : resource.url ? (
                          <TextLink href={resource.url} target="_blank" rel="noopener noreferrer">
                            {resource.title}
                          </TextLink>
                        ) : (
                          resource.title
                        )}
                      </span>
                      {resource.material_id ? <Tag tone="info">{t("material")}</Tag> : null}
                      <span className="text-sm text-muted tabular">
                        {t("resourceMentions", { count: resource.mentions })}
                      </span>
                    </li>
                  ))}
                </ul>
              </Panel>
            ) : null}
            <section aria-labelledby="top-tips" className="flex flex-col gap-4">
              <h2 id="top-tips" className="text-lg font-semibold">
                {t("topTips")}
              </h2>
              <ul className="flex flex-col gap-4">
                {page.tips.map((tip) => (
                  <li key={tip.id}>
                    <Panel>
                      <PanelBody className="flex flex-col gap-3 p-4">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-sm text-muted">
                            {t("semester", { semester: tip.semester })}
                          </span>
                          <Tag tone="neutral">{t(`hours.${tip.weekly_hours}`)}</Tag>
                          <Tag tone="neutral">
                            {t("difficulty", { value: String(tip.difficulty) })}
                          </Tag>
                          {tip.mine ? <Tag tone="accent">{t("mine")}</Tag> : null}
                        </div>
                        <TipSection title={t("keyTopics")} body={tip.key_topics} />
                        <TipSection title={t("examAdvice")} body={tip.exam_advice} />
                        <TipSection title={t("retrospective")} body={tip.retrospective} />
                        <TipActions
                          tipId={tip.id}
                          upvotes={tip.upvotes}
                          upvoted={tip.upvoted}
                          mine={tip.mine}
                        />
                      </PanelBody>
                    </Panel>
                  </li>
                ))}
              </ul>
            </section>
          </>
        )}
        <p>
          <Link href="/guides" className="text-primary underline">
            {tGuides("title")}
          </Link>
        </p>
      </div>
    </>
  );
}

function TipSection({ title, body }: { title: string; body: string }) {
  return (
    <div className="flex flex-col gap-1">
      <h3 className="text-sm font-medium">{title}</h3>
      <p className="break-words whitespace-pre-wrap">{body}</p>
    </div>
  );
}
