import { CloudOff, UserX } from "lucide-react";
import { cookies, headers } from "next/headers";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { AppShell } from "@/features/shell/app-shell";
import { ApiProvider } from "@/lib/api/provider";
import { NAV_COOKIE } from "@/features/shell/nav";
import { StatusPage } from "@/features/shell/status-page";
import { getCurrentUser } from "@/lib/api/server";
import { PATHNAME_HEADER } from "@/lib/request-headers";

/** Every page in this group requires a signed-in, active user. */
export default async function AuthenticatedLayout({ children }: { children: ReactNode }) {
  const result = await getCurrentUser();
  const pathname = (await headers()).get(PATHNAME_HEADER) ?? "/";

  if (result.status === "signed_out") {
    redirect(`/login?returnTo=${encodeURIComponent(pathname)}`);
  }

  const t = await getTranslations("status");
  if (result.status === "inactive") {
    return (
      <StatusPage
        icon={UserX}
        title={t("inactiveTitle")}
        body={t("inactiveBody")}
        action={<SignOutButton />}
      />
    );
  }
  if (result.status === "unavailable") {
    return (
      <StatusPage
        icon={CloudOff}
        title={t("unavailableTitle")}
        body={t("unavailableBody")}
        action={
          <Button asChild variant="primary">
            <a href={pathname}>{t("retry")}</a>
          </Button>
        }
      />
    );
  }

  const collapsed = (await cookies()).get(NAV_COOKIE)?.value === "collapsed";
  const { user, session } = result;
  return (
    <ApiProvider csrfToken={session.csrfToken}>
      <AppShell
        user={{
          displayName: user.display_name,
          roles: user.roles,
          permissions: user.permissions,
          photoUrl: user.photo_url,
        }}
        csrfToken={session.csrfToken}
        initiallyCollapsed={collapsed}
      >
        {children}
      </AppShell>
    </ApiProvider>
  );
}

async function SignOutButton() {
  const t = await getTranslations("shell");
  const result = await getCurrentUser();
  // An inactive account still has a session cookie; signing out clears it.
  const csrf = "session" in result ? result.session.csrfToken : "";
  return (
    <form action="/auth/signout" method="post">
      <input type="hidden" name="csrf" value={csrf} />
      <Button type="submit">{t("signOut")}</Button>
    </form>
  );
}
