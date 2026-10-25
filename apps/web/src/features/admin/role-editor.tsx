"use client";

import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState, type FormEvent } from "react";

import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/choice";
import { ConfirmDialog } from "@/components/ui/overlay";
import { useToast } from "@/components/ui/toast";
import { unwrap } from "@/lib/api/browser";
import { useApi, useErrorMessage } from "@/lib/api/provider";

import { ASSIGNABLE_ROLES, type AdminUserDetail, type AssignableRole } from "./model";

type RoleEditorProps = { user: AdminUserDetail; isSelf: boolean };

/** Role changes are confirmed with the exact difference first; Keycloak and the audit log follow (D-035). */
export function RoleEditor({ user, isSelf }: RoleEditorProps) {
  const t = useTranslations("admin.user");
  const tRoles = useTranslations("roles");
  const api = useApi();
  const router = useRouter();
  const toast = useToast();
  const errorMessage = useErrorMessage();
  const initial = new Set(user.roles.filter((role): role is AssignableRole => role !== "guest"));
  const [selected, setSelected] = useState<Set<AssignableRole>>(initial);
  const [confirmOpen, setConfirmOpen] = useState(false);

  const added = ASSIGNABLE_ROLES.filter((role) => selected.has(role) && !initial.has(role));
  const removed = ASSIGNABLE_ROLES.filter((role) => !selected.has(role) && initial.has(role));
  const names = (roles: readonly AssignableRole[]) => roles.map((role) => tRoles(role)).join(", ");

  const save = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.PUT("/api/v1/admin/users/{user_id}/roles", {
          params: { path: { user_id: user.id } },
          body: { roles: ASSIGNABLE_ROLES.filter((role) => selected.has(role)) },
        }),
      ),
    onSuccess: () => {
      setConfirmOpen(false);
      toast({ title: t("saved") });
      router.refresh();
    },
    onError: () => setConfirmOpen(false),
  });

  if (!user.linked) {
    return (
      <Banner tone="info" title={t("notLinkedTitle")}>
        {t("notLinkedBody")}
      </Banner>
    );
  }

  const toggle = (role: AssignableRole, checked: boolean) =>
    setSelected((current) => {
      const next = new Set(current);
      if (checked) next.add(role);
      else next.delete(role);
      return next;
    });

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setConfirmOpen(true);
  };

  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      {save.isError ? (
        <Banner tone="danger" title={t("saveFailedTitle")}>
          {errorMessage(save.error)}
        </Banner>
      ) : null}
      <fieldset className="flex flex-col gap-3">
        <legend className="sr-only">{t("rolesTitle")}</legend>
        {ASSIGNABLE_ROLES.map((role) => {
          const locked = isSelf && role === "admin";
          return (
            <Checkbox
              key={role}
              label={tRoles(role)}
              description={locked ? t("ownAdmin") : t(`roleHints.${role}`)}
              checked={selected.has(role)}
              disabled={locked}
              onCheckedChange={(checked) => toggle(role, checked === true)}
            />
          );
        })}
      </fieldset>
      <div>
        <Button
          type="submit"
          variant="primary"
          disabled={added.length === 0 && removed.length === 0}
          loading={save.isPending}
        >
          {t("save")}
        </Button>
      </div>
      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title={t("confirmTitle")}
        consequence={[
          added.length ? t("confirmAdded", { roles: names(added) }) : null,
          removed.length ? t("confirmRemoved", { roles: names(removed) }) : null,
          t("confirmNote"),
        ]
          .filter(Boolean)
          .join(" ")}
        confirmLabel={t("save")}
        pending={save.isPending}
        onConfirm={() => save.mutate()}
      />
    </form>
  );
}
