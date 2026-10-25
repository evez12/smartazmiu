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
import { TextLink } from "@/components/ui/text-link";
import { formatDateTime } from "@/lib/format";

import { actionKey, type AuditEntry } from "./model";

function useDetailsText() {
  const t = useTranslations("admin.audit");
  const tRoles = useTranslations("roles");
  const tKinds = useTranslations("imports.kinds");
  const roleList = (codes: unknown) =>
    Array.isArray(codes) && codes.length
      ? codes.map((code) => (tRoles.has(code) ? tRoles(code) : String(code))).join(", ")
      : null;

  return (entry: AuditEntry): string => {
    const details = entry.details as Record<string, unknown>;
    if (entry.action === "user.roles_changed" || entry.action === "user.roles_synced") {
      const added = roleList(details.added);
      const removed = roleList(details.removed);
      return [
        added ? t("rolesAdded", { roles: added }) : null,
        removed ? t("rolesRemoved", { roles: removed }) : null,
      ]
        .filter(Boolean)
        .join("; ");
    }
    if (entry.action === "import.applied" && typeof details.kind === "string") {
      const kind = details.kind as Parameters<typeof tKinds>[0];
      return t("importResult", {
        kind: tKinds.has(kind) ? tKinds(kind) : details.kind,
        created: Number(details.created ?? 0),
        updated: Number(details.updated ?? 0),
        unchanged: Number(details.unchanged ?? 0),
      });
    }
    return "";
  };
}

function targetHref(entry: AuditEntry): string | null {
  if (!entry.target_id) return null;
  if (entry.target_type === "user") return `/admin/users/${entry.target_id}`;
  if (entry.target_type === "import") return `/admin/imports/${entry.target_id}`;
  return null;
}

/** Audit entries with localized actions and readable details; never shows raw codes (§12.8). */
export function AuditTable({ entries, caption }: { entries: AuditEntry[]; caption: string }) {
  const t = useTranslations("admin.audit");
  const details = useDetailsText();
  return (
    <Table>
      <TableCaption>{caption}</TableCaption>
      <TableHeader>
        <TableRow>
          <TableHead>{t("columns.time")}</TableHead>
          <TableHead>{t("columns.action")}</TableHead>
          <TableHead>{t("columns.actor")}</TableHead>
          <TableHead>{t("columns.target")}</TableHead>
          <TableHead>{t("columns.details")}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {entries.map((entry) => {
          const href = targetHref(entry);
          const label = entry.target_label ?? entry.target_id ?? "—";
          return (
            <TableRow key={entry.id}>
              <TableCell label={t("columns.time")} className="whitespace-nowrap tabular">
                {formatDateTime(entry.occurred_at)}
              </TableCell>
              <TableCell label={t("columns.action")}>
                {t(`actions.${actionKey(entry.action)}`)}
              </TableCell>
              <TableCell label={t("columns.actor")}>
                {entry.actor ? (
                  <TextLink href={`/admin/users/${entry.actor.id}`}>
                    {entry.actor.display_name}
                  </TextLink>
                ) : (
                  t("system")
                )}
              </TableCell>
              <TableCell label={t("columns.target")} className="max-w-56">
                {href ? (
                  <TextLink href={href} className="break-all">
                    {label}
                  </TextLink>
                ) : (
                  label
                )}
              </TableCell>
              <TableCell label={t("columns.details")} className="text-sm">
                {details(entry) || "—"}
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
