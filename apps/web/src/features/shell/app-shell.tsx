"use client";

import {
  LogOut,
  Menu as MenuIcon,
  Bookmark,
  LifeBuoy,
  MessageSquareText,
  Signpost,
  PanelLeftClose,
  PanelLeftOpen,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import { useTheme } from "next-themes";
import { useRef, useState, type ReactNode } from "react";

import { Wordmark } from "@/components/brand/wordmark";
import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { touchTarget } from "@/components/ui/touch-target";
import {
  Menu,
  MenuContent,
  MenuGroup,
  MenuItem,
  MenuLabel,
  MenuRadioGroup,
  MenuRadioItem,
  MenuSeparator,
  MenuTrigger,
  Sheet,
  Tooltip,
} from "@/components/ui/overlay";
import { NotificationBell } from "@/features/notifications/bell";
import { FeedbackDialog } from "@/features/feedback/feedback-dialog";
import { useRestartTour } from "@/features/onboarding/onboarding-tour";
import { cn } from "@/lib/cn";

import {
  isActive,
  NAV_COOKIE,
  ROLE_CODES,
  visibleNavigation,
  type NavItem,
  type NavSection,
} from "./nav";

export type ShellUser = {
  displayName: string;
  roles: string[];
  permissions: string[];
  photoUrl: string | null;
};

type AppShellProps = {
  user: ShellUser;
  csrfToken: string;
  initiallyCollapsed: boolean;
  children: ReactNode;
};

/**
 * App shell (§12.4, §12.6): 56 px top bar, 240 px collapsible left navigation on desktop, navigation sheet and
 * bottom tab bar below `lg`, content limited to 1200 px.
 */
export function AppShell({ user, csrfToken, initiallyCollapsed, children }: AppShellProps) {
  const t = useTranslations("shell");
  const [collapsed, setCollapsed] = useState(initiallyCollapsed);
  const [sheetOpen, setSheetOpen] = useState(false);
  const signOutForm = useRef<HTMLFormElement>(null);
  const navigation = visibleNavigation(user.permissions);

  const toggleCollapsed = () => {
    const next = !collapsed;
    setCollapsed(next);
    // A cookie (not localStorage) so the server renders the same width and the layout does not jump.
    document.cookie = `${NAV_COOKIE}=${next ? "collapsed" : "expanded"}; path=/; max-age=31536000; samesite=lax`;
  };

  return (
    <div className="flex min-h-dvh flex-col bg-bg-subtle">
      <a
        href="#main"
        className="fixed top-2 left-4 z-[70] -translate-y-20 rounded-control border border-border-control bg-surface px-3 py-2 text-primary focus:translate-y-0"
      >
        {t("skipToContent")}
      </a>

      <header className="sticky top-0 z-40 flex h-14 shrink-0 items-center gap-2 border-b border-border bg-surface px-2 lg:px-4">
        <Button
          variant="tertiary"
          size="icon"
          className="text-text lg:hidden"
          aria-label={t("openNavigation")}
          onClick={() => setSheetOpen(true)}
        >
          <Icon icon={MenuIcon} size={20} />
        </Button>
        <Button
          variant="tertiary"
          size="icon"
          className="hidden text-text lg:inline-flex"
          aria-label={collapsed ? t("expandNavigation") : t("collapseNavigation")}
          aria-expanded={!collapsed}
          aria-controls="side-navigation"
          onClick={toggleCollapsed}
        >
          <Icon icon={collapsed ? PanelLeftOpen : PanelLeftClose} size={20} />
        </Button>
        <Link href="/" className={cn("rounded-control px-1", touchTarget)}>
          <Wordmark />
        </Link>
        <div className="flex-1" />
        <NotificationBell />
        <ProfileMenu user={user} onSignOut={() => signOutForm.current?.requestSubmit()} />
        <form ref={signOutForm} action="/auth/signout" method="post" hidden>
          <input type="hidden" name="csrf" value={csrfToken} />
        </form>
      </header>

      <div className="flex flex-1">
        <nav
          id="side-navigation"
          aria-label={t("mainNavigation")}
          className={cn(
            "sticky top-14 hidden h-[calc(100dvh-56px)] shrink-0 overflow-y-auto border-r border-border bg-surface transition-[width] lg:block",
            collapsed ? "w-16" : "w-60",
          )}
        >
          <NavList sections={navigation} collapsed={collapsed} />
        </nav>

        <main
          id="main"
          tabIndex={-1}
          className="min-w-0 flex-1 outline-none max-lg:pb-[calc(64px+env(safe-area-inset-bottom))]"
        >
          <div className="mx-auto w-full max-w-[1200px] px-4 py-6 md:px-6 lg:py-8">{children}</div>
        </main>
      </div>

      <Sheet open={sheetOpen} onOpenChange={setSheetOpen} title={t("navigationTitle")}>
        <nav aria-label={t("mainNavigation")}>
          <NavList sections={navigation} collapsed={false} onNavigate={() => setSheetOpen(false)} />
        </nav>
      </Sheet>

      <BottomTabs sections={navigation} />
    </div>
  );
}

function NavList({
  sections,
  collapsed,
  onNavigate,
}: {
  sections: NavSection[];
  collapsed: boolean;
  onNavigate?: () => void;
}) {
  const t = useTranslations("shell");
  const pathname = usePathname();
  return (
    <div className="flex flex-col gap-4 p-2">
      {sections.map((section) => (
        <div key={section.labelKey} className="flex flex-col gap-1">
          <p
            className={cn("px-3 pt-2 pb-1 text-xs font-medium text-muted", collapsed && "sr-only")}
          >
            {t(`sections.${section.labelKey}`)}
          </p>
          <ul className="flex flex-col gap-0.5">
            {section.items.map((item) => (
              <li key={item.href}>
                <NavLink
                  item={item}
                  active={isActive(pathname, item.href)}
                  collapsed={collapsed}
                  onNavigate={onNavigate}
                />
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

function NavLink({
  item,
  active,
  collapsed,
  onNavigate,
}: {
  item: NavItem;
  active: boolean;
  collapsed: boolean;
  onNavigate?: () => void;
}) {
  const t = useTranslations("shell.nav");
  const label = t(item.labelKey);
  const link = (
    <Link
      href={item.href}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      aria-label={collapsed ? label : undefined}
      className={cn(
        "relative flex h-9 items-center gap-3 rounded-control px-3 text-text transition-colors hover:bg-bg-subtle pointer-coarse:h-11",
        active && "bg-bg-subtle font-medium",
        collapsed && "justify-center px-0",
      )}
    >
      {/* The bar marks the current page in addition to the background, so colour is not the only cue. */}
      {active ? (
        <span aria-hidden="true" className="absolute inset-y-1.5 left-0 w-0.5 bg-primary" />
      ) : null}
      <Icon icon={item.icon} size={20} className={active ? "text-primary" : "text-muted"} />
      {collapsed ? null : <span className="truncate">{label}</span>}
    </Link>
  );
  return collapsed ? <Tooltip content={label}>{link}</Tooltip> : link;
}

function BottomTabs({ sections }: { sections: NavSection[] }) {
  const t = useTranslations("shell");
  const pathname = usePathname();
  const items = sections.flatMap((section) => section.items).filter((item) => item.inTabBar);
  return (
    <nav
      aria-label={t("mainNavigation")}
      className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-surface pb-[env(safe-area-inset-bottom)] lg:hidden"
    >
      <ul className="mx-auto flex max-w-md">
        {items.map((item) => {
          const active = isActive(pathname, item.href);
          return (
            <li key={item.href} className="flex-1">
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex h-16 flex-col items-center justify-center gap-1 text-xs",
                  active ? "font-medium text-primary" : "text-muted",
                )}
              >
                <Icon icon={item.icon} size={20} />
                {t(`nav.${item.labelKey}`)}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

function ProfileMenu({ user, onSignOut }: { user: ShellUser; onSignOut: () => void }) {
  const t = useTranslations("shell");
  const tFeedback = useTranslations("feedback");
  const tTour = useTranslations("onboarding");
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const restartTour = useRestartTour();
  const tRoles = useTranslations("roles");
  const tTheme = useTranslations("theme");
  const { theme, setTheme } = useTheme();
  const roles = ROLE_CODES.filter((code) => user.roles.includes(code));
  const roleLabel = roles.length ? roles.map((code) => tRoles(code)).join(" · ") : tRoles("none");

  return (
    <>
      <Menu>
        <MenuTrigger asChild>
          <button
            type="button"
            className={cn(
              "flex h-10 items-center gap-2 rounded-control px-1.5 text-left hover:bg-bg-subtle",
              touchTarget,
            )}
          >
            <Avatar name={user.displayName} src={user.photoUrl ?? undefined} size={32} decorative />
            {/* Visible text is part of the accessible name (WCAG 2.5.3); on phones it is read but not shown. */}
            <span className="flex max-w-48 flex-col leading-tight max-md:sr-only">
              <span className="truncate font-medium">{user.displayName}</span>
              <span className="truncate text-xs text-muted">{roleLabel}</span>
            </span>
            <span className="sr-only">{t("profileMenu")}</span>
          </button>
        </MenuTrigger>
        <MenuContent className="w-64">
          <MenuLabel className="flex flex-col py-2">
            <span className="font-medium text-text">{user.displayName}</span>
            <span>{roleLabel}</span>
          </MenuLabel>
          <MenuSeparator />
          <MenuGroup>
            <MenuLabel>{tTheme("label")}</MenuLabel>
            <MenuRadioGroup value={theme ?? "system"} onValueChange={setTheme}>
              <MenuRadioItem value="light">{tTheme("light")}</MenuRadioItem>
              <MenuRadioItem value="dark">{tTheme("dark")}</MenuRadioItem>
              <MenuRadioItem value="system">{tTheme("system")}</MenuRadioItem>
            </MenuRadioGroup>
          </MenuGroup>
          <MenuSeparator />
          <MenuItem asChild>
            <Link href="/saved">
              <Icon icon={Bookmark} />
              {t("saved")}
            </Link>
          </MenuItem>
          <MenuItem asChild>
            <Link href="/support">
              <Icon icon={LifeBuoy} />
              {t("support")}
            </Link>
          </MenuItem>
          <MenuItem onSelect={() => setFeedbackOpen(true)}>
            <Icon icon={MessageSquareText} />
            {tFeedback("action")}
          </MenuItem>
          <MenuItem onSelect={() => restartTour.mutate()}>
            <Icon icon={Signpost} />
            {tTour("restart")}
          </MenuItem>
          <MenuItem onSelect={onSignOut}>
            <Icon icon={LogOut} />
            {t("signOut")}
          </MenuItem>
        </MenuContent>
      </Menu>
      <FeedbackDialog open={feedbackOpen} onOpenChange={setFeedbackOpen} />
    </>
  );
}
