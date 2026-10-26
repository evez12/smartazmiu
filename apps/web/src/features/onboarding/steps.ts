export type TourStepKey =
  | "schedule"
  | "chat"
  | "chatTeacher"
  | "materials"
  | "materialsTeacher"
  | "notifications"
  | "imports"
  | "announcements"
  | "reports"
  | "profile";

export type TourStep = { key: TourStepKey; href: string };

/** The tour follows the user's main capacity; staff and admins get the administrative sections. */
export function tourSteps(roles: readonly string[]): TourStep[] {
  if (roles.includes("staff") || roles.includes("admin")) {
    return [
      { key: "imports", href: "/admin/imports" },
      { key: "announcements", href: "/announcements" },
      { key: "reports", href: "/admin/reports" },
      { key: "profile", href: "/profile" },
    ];
  }
  const teacher = roles.includes("teacher");
  return [
    { key: "schedule", href: "/schedule" },
    { key: teacher ? "chatTeacher" : "chat", href: "/chat" },
    { key: teacher ? "materialsTeacher" : "materials", href: "/materials" },
    { key: "notifications", href: "/notifications" },
    { key: "profile", href: "/profile" },
  ];
}
