import type { components } from "@/lib/api/schema";

export type Announcement = components["schemas"]["AnnouncementOut"];
export type AnnouncementPage = components["schemas"]["AnnouncementPageOut"];
export type ManagedAnnouncementPage = components["schemas"]["ManagedAnnouncementPageOut"];

export const PUBLISH_PERMISSION = "announcements.publish";
/** Announcements per page on the list; the dashboard shows the newest few. */
export const PAGE_SIZE = 20;
export const DASHBOARD_COUNT = 3;
export const TITLE_MAX = 200;
export const BODY_MAX = 5000;
