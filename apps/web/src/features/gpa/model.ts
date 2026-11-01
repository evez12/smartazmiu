import type { components } from "@/lib/api/schema";

import { finalScore, uomg, withAttempts, type CourseResult, type GpaConfig } from "./uomg";

type Grade = components["schemas"]["FinishedCourseOut"];

export type SemesterResult = CourseResult & {
  id: string;
  code: string;
  name: string;
  semesterKey: string;
  semester: { year: number; term: "fall" | "spring" | "summer" };
};

/** The finished courses as calculator input; retakes are numbered by the order of the semesters. */
export function semesterResults(grades: Grade[]): SemesterResult[] {
  const rows = withAttempts(
    grades.map((grade) => ({
      grade,
      subjectId: grade.subject_id,
      semester: { year: grade.semester_year, term: grade.semester_term },
    })),
  );
  return rows.map(({ grade, attempt }) => ({
    id: grade.enrollment_id,
    code: grade.subject_code,
    name: grade.subject_name,
    courseId: grade.subject_id,
    credits: grade.credits,
    score: grade.score,
    attempt,
    semesterKey: `${grade.semester_year}-${grade.semester_term}`,
    semester: { year: grade.semester_year, term: grade.semester_term },
  }));
}

/** A course typed into the simulator: text, so a half-typed number does not jump around. */
export type Draft = { id: number; credits: string; semester: string; exam: string };

function clamp(value: string, max: number): number {
  const parsed = Number(value);
  if (value.trim() === "" || !Number.isFinite(parsed)) return 0;
  return Math.min(max, Math.max(0, parsed));
}

/** ÜOMG before and after adding the typed courses as new subjects. */
export function simulate(grades: Grade[], drafts: Draft[], config: GpaConfig) {
  const real = semesterResults(grades);
  const hypothetical: CourseResult[] = drafts.map((draft) => ({
    courseId: `draft-${draft.id}`,
    credits: Math.round(clamp(draft.credits, 30)),
    score: finalScore(clamp(draft.semester, 50), clamp(draft.exam, 50), config),
    attempt: 1,
  }));
  return { before: uomg(real, config), after: uomg([...real, ...hypothetical], config) };
}
