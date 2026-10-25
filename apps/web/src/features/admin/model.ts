import type { components } from "@/lib/api/schema";

export type AdminUser = components["schemas"]["AdminUserOut"];
export type AdminUserDetail = components["schemas"]["AdminUserDetail"];
export type AuditEntry = components["schemas"]["AuditEntryOut"];
export type AuditAction = components["schemas"]["AuditAction"];
export type AssignableRole = components["schemas"]["AssignableRole"];

export const USERS_READ = "admin.users.read";
export const ROLES_ASSIGN = "admin.roles.assign";
export const AUDIT_READ = "admin.audit.read";

/** Catalogue order (§2), which is also the order roles are listed in. */
export const ASSIGNABLE_ROLES = [
  "student",
  "teacher",
  "staff",
  "moderator",
  "admin",
] as const satisfies readonly AssignableRole[];

export const AUDIT_ACTIONS = [
  "user.roles_changed",
  "user.roles_synced",
  "user.account_linked",
  "import.applied",
  "user.data_exported",
] as const satisfies readonly AuditAction[];

/** Message key of an action code: next-intl reads dots as nesting. */
export function actionKey(action: AuditAction) {
  return action.replaceAll(".", "_") as
    | "user_roles_changed"
    | "user_roles_synced"
    | "user_account_linked"
    | "import_applied"
    | "user_data_exported";
}

/** Query string for list pages: drops empty values and the first page. */
export function listHref(
  path: string,
  params: Record<string, string | number | undefined>,
): string {
  const query = new URLSearchParams();
  for (const [name, value] of Object.entries(params)) {
    if (value !== undefined && value !== "" && !(name === "page" && value === 1)) {
      query.set(name, String(value));
    }
  }
  const search = query.toString();
  return search ? `${path}?${search}` : path;
}
