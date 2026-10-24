import { LogIn } from "lucide-react";
import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { Wordmark } from "@/components/brand/wordmark";
import { ThemeSwitcher } from "@/components/theme-switcher";
import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Panel, PanelBody } from "@/components/ui/panel";
import { getCurrentUser } from "@/lib/api/server";
import { safeReturnTo } from "@/lib/auth/return-to";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("login");
  return { title: t("metaTitle") };
}

const NOTICES = {
  signed_out: { tone: "success", title: "signedOutTitle", body: "signedOutBody" },
  signin_failed: { tone: "danger", title: "signinFailedTitle", body: "signinFailedBody" },
  signin_expired: { tone: "warning", title: "signinExpiredTitle", body: "signinExpiredBody" },
  session_expired: { tone: "info", title: "sessionExpiredTitle", body: "sessionExpiredBody" },
} as const;

type LoginPageProps = {
  searchParams: Promise<{ error?: string; status?: string; returnTo?: string }>;
};

/** Public sign-in page; the credentials form itself is served by Keycloak (themed, D-019). */
export default async function LoginPage({ searchParams }: LoginPageProps) {
  const { error, status, returnTo } = await searchParams;
  if ((await getCurrentUser()).status === "ok") redirect(safeReturnTo(returnTo));

  const t = await getTranslations("login");
  const shell = await getTranslations("shell");
  const noticeKey = (error ?? status) as keyof typeof NOTICES | undefined;
  const notice = noticeKey && noticeKey in NOTICES ? NOTICES[noticeKey] : null;
  const signInHref = `/auth/signin?returnTo=${encodeURIComponent(safeReturnTo(returnTo))}`;

  return (
    <div className="flex min-h-dvh flex-col bg-bg-subtle">
      <a
        href="#main"
        className="fixed top-2 left-4 z-50 -translate-y-20 rounded-control border border-border-control bg-surface px-3 py-2 text-primary focus:translate-y-0"
      >
        {shell("skipToContent")}
      </a>
      <header className="flex h-14 items-center border-b border-border bg-surface px-4">
        <Wordmark />
      </header>

      <main id="main" tabIndex={-1} className="flex-1 outline-none">
        <div className="mx-auto flex w-full max-w-md flex-col gap-4 px-4 py-12 md:py-16">
          {notice ? (
            <Banner tone={notice.tone} title={t(notice.title)}>
              {t(notice.body)}
            </Banner>
          ) : null}
          <Panel>
            <PanelBody className="flex flex-col gap-4 p-6">
              <h1 className="text-xl font-semibold">{t("title")}</h1>
              <p className="text-muted">{t("description")}</p>
              <Button
                asChild
                variant="primary"
                className="h-auto min-h-9 w-full py-2 whitespace-normal"
              >
                <a href={signInHref}>
                  <Icon icon={LogIn} />
                  {t("signIn")}
                </a>
              </Button>
            </PanelBody>
          </Panel>
          <p className="text-sm text-muted">{t("help")}</p>
        </div>
      </main>

      <footer className="border-t border-border bg-surface">
        <div className="mx-auto flex max-w-[1200px] flex-wrap items-center justify-between gap-3 px-4 py-4">
          <p className="text-sm text-muted">{t("footer")}</p>
          <ThemeSwitcher />
        </div>
      </footer>
    </div>
  );
}
