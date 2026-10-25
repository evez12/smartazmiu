import { ScrollText } from "lucide-react";
import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Field, Input, Select } from "@/components/ui/field";
import { PageHeader } from "@/components/ui/page-header";
import { pageFromParam, Pagination } from "@/components/ui/pagination";
import { Panel, PanelBody } from "@/components/ui/panel";
import { AuditTable } from "@/features/admin/audit-table";
import { actionKey, AUDIT_ACTIONS, listHref, type AuditAction } from "@/features/admin/model";
import { ForbiddenState } from "@/features/shell/forbidden-state";
import { loaded, serverApi } from "@/lib/api/server";

const PAGE_SIZE = 50;
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("admin.audit");
  return { title: t("title") };
}

type AuditPageProps = {
  searchParams: Promise<{ action?: string; from?: string; to?: string; page?: string }>;
};

export default async function AuditPage({ searchParams }: AuditPageProps) {
  const t = await getTranslations("admin.audit");
  const params = await searchParams;
  const action = AUDIT_ACTIONS.find((value) => value === params.action) as AuditAction | undefined;
  const from = params.from && ISO_DATE.test(params.from) ? params.from : undefined;
  const to = params.to && ISO_DATE.test(params.to) ? params.to : undefined;
  const page = pageFromParam(params.page);

  const result = await loaded(
    await (
      await serverApi()
    ).GET("/api/v1/admin/audit-logs", {
      params: {
        query: {
          action,
          occurred_from: from,
          occurred_to: to,
          offset: (page - 1) * PAGE_SIZE,
          limit: PAGE_SIZE,
        },
      },
    }),
  );
  const header = (
    <PageHeader
      title={t("title")}
      description={t("description")}
      breadcrumb={[{ label: t("title") }]}
    />
  );
  if (result.status === "forbidden") {
    return (
      <>
        {header}
        <ForbiddenState />
      </>
    );
  }

  return (
    <>
      {header}
      <Panel>
        <form
          method="get"
          className="grid gap-4 border-b border-border p-4 md:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_minmax(0,1fr)_auto] md:items-end"
        >
          <Field label={t("action")}>
            <Select name="action" defaultValue={action ?? ""}>
              <option value="">{t("allActions")}</option>
              {AUDIT_ACTIONS.map((value) => (
                <option key={value} value={value}>
                  {t(`actions.${actionKey(value)}`)}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("from")}>
            <Input name="from" type="date" defaultValue={from ?? ""} />
          </Field>
          <Field label={t("to")}>
            <Input name="to" type="date" defaultValue={to ?? ""} />
          </Field>
          <div>
            <Button type="submit">{t("apply")}</Button>
          </div>
        </form>
        {result.data.items.length === 0 ? (
          <PanelBody>
            <EmptyState className="py-0" icon={ScrollText} message={t("empty")} />
          </PanelBody>
        ) : (
          <div className="flex flex-col gap-4 px-4 pb-4">
            <AuditTable entries={result.data.items} caption={t("tableCaption")} />
            <Pagination
              page={page}
              pageSize={PAGE_SIZE}
              total={result.data.total}
              href={(target) => listHref("/admin/audit", { action, from, to, page: target })}
            />
          </div>
        )}
      </Panel>
    </>
  );
}
