import type { components } from "@/lib/api/schema";

export type Audience = components["schemas"]["AudienceOut"];
export type AudienceType = components["schemas"]["AudienceType"];
export type AudienceOption = components["schemas"]["AudienceOptionOut"];

export const AUDIENCE_TYPES = [
  "university",
  "faculty",
  "specialty",
  "group",
  "course_offering",
] as const satisfies readonly AudienceType[];
