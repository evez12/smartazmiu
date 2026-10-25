import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { cache } from "react";

import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { AuditTable } from "@/features/admin/audit-table";
import { AUDIT_READ, ROLES_ASSIGN } from "@/features/admin/model";
import { RoleEditor } from "@/features/admin/role-editor";
import { RoleTags, StatusTag } from "@/features/admin/user-table";
import { ForbiddenState } from "@/features/shell/forbidden-state";
import { getCurrentUser, loaded, serverApi } from "@/lib/api/server";
import { formatDateTime } from "@/lib/format";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// Shared by generateMetadata and the page, so the user is fetched once per request.
const loadUser = cache(async (id: string) => {
  if (!UUID.test(id)) notFound();
  return loaded(
    await (
      await serverApi()
    ).GET("/api/v1/admin/users/{user_id}", { params: { path: { user_id: id } } }),
  );
});

type UserPageProps = { params: Promise<{ id: string }> };

export async function generateMetadata({ params }: UserPageProps): Promise<Metadata> {
  const result = await loadUser((await params).id);
  const t = await getTranslations("admin.users");
  return { title: result.status === "ok" ? result.data.display_name : t("title") };
}

export default async function UserPage({ params }: UserPageProps) {
  const t = await getTranslations("admin");
  const result = await loadUser((await params).id);
  if (result.status === "forbidden") {
    return (
      <>
        <PageHeader title={t("users.title")} breadcrumb={[{ label: t("users.title") }]} />
        <ForbiddenState />
      </>
    );
  }

  const user = result.data;
  const me = await getCurrentUser();
  const permissions = me.status === "ok" ? me.user.permissions : [];
  const facts = [
    { label: t("user.email"), value: user.email ?? t("user.none") },
    { label: t("user.universityId"), value: user.university_id ?? t("user.none") },
    {
      label: t("user.personType"),
      value: user.person_type ? t(`users.personTypes.${user.person_type}`) : t("user.none"),
    },
    { label: t("user.group"), value: user.group_code ?? t("user.none") },
    { label: t("user.access"), value: user.linked ? t("users.linked") : t("users.notLinked") },
    { label: t("user.createdAt"), value: formatDateTime(user.created_at) },
  ];

  return (
    <>
      <PageHeader
        title={user.display_name}
        breadcrumb={[
          { label: t("users.title"), href: "/admin/users" },
          { label: user.display_name },
        ]}
      />
      <div className="flex flex-col gap-6">
        <Panel>
          <PanelHeader
            title={t("user.factsTitle")}
            action={
              <span className="flex flex-wrap items-center gap-2">
                <StatusTag status={user.status} />
                <RoleTags roles={user.roles} />
              </span>
            }
          />
          <PanelBody>
            <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-3">
              {facts.map((fact) => (
                <div key={fact.label} className="flex min-w-0 flex-col">
                  <dt className="text-sm text-muted">{fact.label}</dt>
                  <dd className="break-all text-text tabular">{fact.value}</dd>
                </div>
              ))}
            </dl>
          </PanelBody>
        </Panel>

        {permissions.includes(ROLES_ASSIGN) ? (
          <Panel>
            <PanelHeader title={t("user.rolesTitle")} description={t("user.rolesDescription")} />
            <PanelBody className="p-6">
              <RoleEditor
                key={user.roles.join()}
                user={user}
                isSelf={me.status === "ok" && me.user.id === user.id}
              />
            </PanelBody>
          </Panel>
        ) : null}

        {permissions.includes(AUDIT_READ) ? (
          <Panel>
            <PanelHeader title={t("user.activityTitle")} />
            {user.recent_activity.length ? (
              <div className="px-4 pb-2">
                <AuditTable entries={user.recent_activity} caption={t("user.activityTitle")} />
              </div>
            ) : (
              <PanelBody>
                <EmptyState className="py-0" message={t("user.activityEmpty")} />
              </PanelBody>
            )}
          </Panel>
        ) : null}
      </div>
    </>
  );
}
