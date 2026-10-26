import type { components } from "@/lib/api/schema";

export type MentorRequest = components["schemas"]["MentorRequestOut"];
export type RequestTopic = MentorRequest["topic"];
export type GuideStats = components["schemas"]["GuideStatsOut"];
export type MyGuideProfile = components["schemas"]["MyGuideProfileOut"];
export type Availability = MyGuideProfile["availability"];
export type GradeVisibility = MyGuideProfile["grade_visibility"];

export const TOPICS: readonly RequestTopic[] = [
  "exam",
  "workload",
  "materials",
  "teacher_expectations",
  "project",
  "other",
] as const;

export const AVAILABILITIES: readonly Availability[] = ["available", "busy", "paused"] as const;
export const GRADE_VISIBILITIES: readonly GradeVisibility[] = ["hidden", "range", "exact"] as const;

export const MAX_REQUEST_BODY = 2000;
export const MAX_BIO = 300;

export const mentorshipKeys = {
  requests: ["mentorship", "requests"] as const,
  channel: (channelId: string) => ["mentorship", "requests", "channel", channelId] as const,
};

export const STATUS_TONE = {
  open: "info",
  accepted: "accent",
  resolved: "success",
  declined: "neutral",
  expired: "neutral",
} as const satisfies Record<MentorRequest["status"], string>;
