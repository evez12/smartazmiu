import type { components } from "@/lib/api/schema";

export type Assignment = components["schemas"]["AssignmentOut"];
export type Submission = components["schemas"]["SubmissionOut"];

export const ASSIGNMENTS_MANAGE_PERMISSION = "assignments.manage";
export const ASSIGNMENTS_GRADE_PERMISSION = "assignments.grade";
