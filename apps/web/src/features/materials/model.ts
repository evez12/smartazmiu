import type { components } from "@/lib/api/schema";

export type Material = components["schemas"]["MaterialOut"];
export type MaterialDetail = components["schemas"]["MaterialDetailOut"];
export type MaterialVersion = components["schemas"]["VersionOut"];
export type MaterialType = Material["type"];
export type Semester = components["schemas"]["SemesterOut"];

/** Display order of types; mirrors the catalogue's ordering on the server. */
export const MATERIAL_TYPES: readonly MaterialType[] = [
  "lecture",
  "seminar",
  "lab",
  "syllabus",
  "exam_prep",
  "other",
] as const;

/** Mirrors the server's limit (D-071); the server checks again, this only spares a useless upload. */
export const MAX_MATERIAL_BYTES = 50 * 1024 * 1024;

export const STATUS_TONE = {
  pending: "info",
  clean: "success",
  infected: "danger",
  failed: "danger",
} as const;

export function materialHref(subjectId: string, materialId?: string): string {
  return materialId ? `/materials/${subjectId}/${materialId}` : `/materials/${subjectId}`;
}
