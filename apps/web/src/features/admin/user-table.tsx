import { useTranslations } from "next-intl";

import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tag } from "@/components/ui/tag";
import { TextLink } from "@/components/ui/text-link";

import type { AdminUser } from "./model";

export function RoleTags({ roles }: { roles: string[] }) {
  const t = useTranslations("admin.users");
  const tRoles = useTranslations("roles");
  if (roles.length === 0) return <span className="text-muted">{t("noRoles")}</span>;
  return (
    <span className="flex flex-wrap gap-1 max-md:justify-end">
      {roles.map((role) => (
        <Tag key={role}>{tRoles.has(role as "student") ? tRoles(role as "student") : role}</Tag>
      ))}
    </span>
  );
}

export function StatusTag({ status }: { status: AdminUser["status"] }) {
  const t = useTranslations("admin.users.statuses");
  return <Tag tone={status === "active" ? "success" : "warning"}>{t(status)}</Tag>;
}

export function UserTable({ users }: { users: AdminUser[] }) {
  const t = useTranslations("admin.users");
  return (
    <Table>
      <TableCaption>{t("tableCaption")}</TableCaption>
      <TableHeader>
        <TableRow>
          <TableHead>{t("columns.name")}</TableHead>
          <TableHead>{t("columns.universityId")}</TableHead>
          <TableHead>{t("columns.group")}</TableHead>
          <TableHead>{t("columns.roles")}</TableHead>
          <TableHead>{t("columns.status")}</TableHead>
          <TableHead>{t("columns.access")}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {users.map((user) => (
          <TableRow key={user.id}>
            <TableCell label={t("columns.name")}>
              <span className="flex flex-col max-md:items-end">
                <TextLink href={`/admin/users/${user.id}`}>{user.display_name}</TextLink>
                {user.email ? (
                  <span className="text-sm break-all text-muted">{user.email}</span>
                ) : null}
              </span>
            </TableCell>
            <TableCell label={t("columns.universityId")} className="tabular">
              {user.university_id ?? "—"}
            </TableCell>
            <TableCell label={t("columns.group")}>{user.group_code ?? "—"}</TableCell>
            <TableCell label={t("columns.roles")}>
              <RoleTags roles={user.roles} />
            </TableCell>
            <TableCell label={t("columns.status")}>
              <StatusTag status={user.status} />
            </TableCell>
            <TableCell label={t("columns.access")} className="text-sm">
              {user.linked ? t("linked") : t("notLinked")}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
