import {
  Bell,
  BookOpen,
  CalendarCheck,
  CalendarDays,
  FileUp,
  House,
  Megaphone,
  MessageSquareText,
  MessagesSquare,
  Map as MapIcon,
  Flag,
  ScrollText,
  UserRound,
  Users,
  type LucideIcon,
} from "lucide-react";

/** Remembers the collapsed desktop navigation so the server renders the same width (no layout jump). */
export const NAV_COOKIE = "sa_nav";

/** Catalogue order (§2); role lists are shown in this order, primary role first. */
export const ROLE_CODES = ["student", "teacher", "staff", "moderator", "admin", "guest"] as const;

export type NavItem = {
  href: string;
  /** Key under `shell.nav` in messages. */
  labelKey:
    | "home"
    | "schedule"
    | "chat"
    | "materials"
    | "map"
    | "announcements"
    | "events"
    | "notifications"
    | "profile"
    | "imports"
    | "users"
    | "reports"
    | "feedback"
    | "audit";
  icon: LucideIcon;
  /** Shown in the mobile bottom tab bar (§12.6: Ana səhifə, Cədvəl, Çat, Bildirişlər, Profil). */
  inTabBar: boolean;
  /** Hidden unless the user holds this permission; the API enforces it independently. */
  permission?: string;
};

export type NavSection = { labelKey: "main" | "admin"; items: NavItem[] };

/*
 * Only sections that exist are listed (DECISIONS D-024); the tab bar holds the five of §12.6.
 */
export const NAVIGATION: NavSection[] = [
  {
    labelKey: "main",
    items: [
      { href: "/", labelKey: "home", icon: House, inTabBar: true },
      { href: "/schedule", labelKey: "schedule", icon: CalendarDays, inTabBar: true },
      { href: "/chat", labelKey: "chat", icon: MessagesSquare, inTabBar: true },
      { href: "/materials", labelKey: "materials", icon: BookOpen, inTabBar: false },
      { href: "/map", labelKey: "map", icon: MapIcon, inTabBar: false },
      { href: "/announcements", labelKey: "announcements", icon: Megaphone, inTabBar: false },
      { href: "/events", labelKey: "events", icon: CalendarCheck, inTabBar: false },
      { href: "/notifications", labelKey: "notifications", icon: Bell, inTabBar: true },
      { href: "/profile", labelKey: "profile", icon: UserRound, inTabBar: true },
    ],
  },
  {
    labelKey: "admin",
    items: [
      {
        href: "/admin/users",
        labelKey: "users",
        icon: Users,
        inTabBar: false,
        permission: "admin.users.read",
      },
      {
        href: "/admin/imports",
        labelKey: "imports",
        icon: FileUp,
        inTabBar: false,
        permission: "academics.import",
      },
      {
        href: "/admin/reports",
        labelKey: "reports",
        icon: Flag,
        inTabBar: false,
        permission: "admin.reports.read",
      },
      {
        href: "/admin/feedback",
        labelKey: "feedback",
        icon: MessageSquareText,
        inTabBar: false,
        permission: "admin.feedback.read",
      },
      {
        href: "/admin/audit",
        labelKey: "audit",
        icon: ScrollText,
        inTabBar: false,
        permission: "admin.audit.read",
      },
    ],
  },
];

export function visibleNavigation(permissions: readonly string[]): NavSection[] {
  return NAVIGATION.map((section) => ({
    ...section,
    items: section.items.filter(
      (item) => !item.permission || permissions.includes(item.permission),
    ),
  })).filter((section) => section.items.length > 0);
}

export function isActive(pathname: string, href: string): boolean {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}
