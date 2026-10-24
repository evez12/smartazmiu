import { House, type LucideIcon } from "lucide-react";

/** Remembers the collapsed desktop navigation so the server renders the same width (no layout jump). */
export const NAV_COOKIE = "sa_nav";

/** Catalogue order (§2); role lists are shown in this order, primary role first. */
export const ROLE_CODES = ["student", "teacher", "staff", "moderator", "admin", "guest"] as const;

export type NavItem = {
  href: string;
  /** Key under `shell.nav` in messages. */
  labelKey: "home";
  icon: LucideIcon;
  /** Shown in the mobile bottom tab bar (§12.6: Ana səhifə, Cədvəl, Çat, Bildirişlər, Profil). */
  inTabBar: boolean;
};

export type NavSection = { labelKey: "main"; items: NavItem[] };

/*
 * Only sections that exist are listed (DECISIONS D-024); schedule, chat, notifications and profile join the
 * navigation and tab bar in the sprints that build them.
 */
export const NAVIGATION: NavSection[] = [
  {
    labelKey: "main",
    items: [{ href: "/", labelKey: "home", icon: House, inTabBar: true }],
  },
];

export function isActive(pathname: string, href: string): boolean {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}
