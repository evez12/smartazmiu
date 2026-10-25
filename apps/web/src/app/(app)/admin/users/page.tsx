import { Search } from "lucide-react";
import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Field, Input, Select } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import { PageHeader } from "@/components/ui/page-header";
import { pageFromParam, Pagination } from "@/components/ui/pagination";
import { Panel, PanelBody } from "@/components/ui/panel";
import { TextLink } from "@/components/ui/text-link";
import { ASSIGNABLE_ROLES, listHref, type AssignableRole } from "@/features/admin/model";
import { UserTable } from "@/features/admin/user-table";
import { ForbiddenState } from "@/features/shell/forbidden-state";
import { loaded, serverApi } from "@/lib/api/server";

const PAGE_SIZE = 25;
const STATUSES = ["active", "inactive"] as const;

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("admin.users");
  return { title: t("title") };
}

type UsersPageProps = {
  searchParams: Promise<{ q?: string; role?: string; status?: string; page?: string }>;
};

export default async function UsersPage({ searchParams }: UsersPageProps) {
  const t = await getTranslations("admin.users");
  const tRoles = await getTranslations("roles");
  const params = await searchParams;
  const q = params.q?.trim().slice(0, 100) || undefined;
  const role = ASSIGNABLE_ROLES.find((value) => value === params.role) as
    AssignableRole | undefined;
  const status = STATUSES.find((value) => value === params.status);
  const page = pageFromParam(params.page);

  const result = await loaded(
    await (
      await serverApi()
    ).GET("/api/v1/admin/users", {
      params: { query: { q, role, status, offset: (page - 1) * PAGE_SIZE, limit: PAGE_SIZE } },
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

  const filtered = Boolean(q || role || status);
  return (
    <>
      {header}
      <Panel>
        <form
          method="get"
          role="search"
          className="grid gap-4 border-b border-border p-4 md:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_minmax(0,1fr)_auto] md:items-start"
        >
          <Field label={t("search")} helper={t("searchHelper")}>
            <Input name="q" type="search" defaultValue={q ?? ""} autoComplete="off" />
          </Field>
          <Field label={t("role")}>
            <Select name="role" defaultValue={role ?? ""}>
              <option value="">{t("allRoles")}</option>
              {ASSIGNABLE_ROLES.map((value) => (
                <option key={value} value={value}>
                  {tRoles(value)}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("status")}>
            <Select name="status" defaultValue={status ?? ""}>
              <option value="">{t("allStatuses")}</option>
              {STATUSES.map((value) => (
                <option key={value} value={value}>
                  {t(`statuses.${value}`)}
                </option>
              ))}
            </Select>
          </Field>
          <div className="flex items-center gap-3 md:pt-[26px]">
            <Button type="submit">
              <Icon icon={Search} />
              {t("apply")}
            </Button>
          </div>
        </form>
        {result.data.items.length === 0 ? (
          <PanelBody>
            <EmptyState
              className="py-0"
              icon={Search}
              message={t("empty")}
              action={filtered ? <TextLink href="/admin/users">{t("reset")}</TextLink> : undefined}
            />
          </PanelBody>
        ) : (
          <div className="flex flex-col gap-4 px-4 pb-4">
            <UserTable users={result.data.items} />
            <Pagination
              page={page}
              pageSize={PAGE_SIZE}
              total={result.data.total}
              href={(target) => listHref("/admin/users", { q, role, status, page: target })}
            />
          </div>
        )}
      </Panel>
    </>
  );
}
