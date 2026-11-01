/** ÜOMG, the Azerbaijani credit-weighted average on a 100-point scale (docs/uomg-gpa-spec.md). */

export type GpaConfig = {
  /** Whether courses below the pass threshold stay in the denominator. */
  includeFailed: boolean;
  /** "replace": the latest attempt of a subject counts; "average": every attempt counts. */
  retakePolicy: "replace" | "average";
  roundDigits: number;
  /** An exam below this score adds nothing to the semester points. */
  minExamScore: number;
  /** The lowest score that earns the credits. */
  passThreshold: number;
};

export const GPA_DEFAULTS: GpaConfig = {
  includeFailed: true,
  retakePolicy: "replace",
  roundDigits: 2,
  minExamScore: 17,
  passThreshold: 51,
};

export type CourseResult = {
  courseId: string;
  credits: number;
  score: number;
  /** 1 for the first time a subject was taken, 2 for the retake, and so on. */
  attempt: number;
};

export type Letter = "A" | "B" | "C" | "D" | "E" | "F";

/** Social-loan thresholds the screen highlights (§4 of the spec). */
export const NO_LOAN_INTEREST_FROM = 71;
export const TOP_TIER_FROM = 91;

const LETTER_SCALE: [number, Letter][] = [
  [91, "A"],
  [81, "B"],
  [71, "C"],
  [61, "D"],
  [51, "E"],
];

export function letterGrade(score: number): Letter {
  return LETTER_SCALE.find(([threshold]) => score >= threshold)?.[1] ?? "F";
}

export function finalScore(
  semester: number,
  exam: number,
  config: GpaConfig = GPA_DEFAULTS,
): number {
  return exam >= config.minExamScore ? semester + exam : semester;
}

export function resolveRetakes(results: CourseResult[], config: GpaConfig): CourseResult[] {
  if (config.retakePolicy === "average") return results;
  const latest = new Map<string, CourseResult>();
  for (const result of results) {
    const known = latest.get(result.courseId);
    if (!known || result.attempt > known.attempt) latest.set(result.courseId, result);
  }
  return [...latest.values()];
}

/** The results that take part in the average under the rules in force. */
export function counted(results: CourseResult[], config: GpaConfig): CourseResult[] {
  const pool = resolveRetakes(results, config);
  return config.includeFailed ? pool : pool.filter((r) => r.score >= config.passThreshold);
}

function round(value: number, digits: number): number {
  const factor = 10 ** digits;
  return Math.round(value * factor) / factor;
}

/** Credit-weighted average; an empty list is 0, not an error. */
export function uomg(results: CourseResult[], config: GpaConfig = GPA_DEFAULTS): number {
  const pool = counted(results, config);
  const credits = pool.reduce((sum, r) => sum + r.credits, 0);
  if (credits === 0) return 0;
  const points = pool.reduce((sum, r) => sum + r.credits * r.score, 0);
  return round(points / credits, config.roundDigits);
}

/** Credits of the courses that were passed under the rules in force (a replaced attempt earns none). */
export function earnedCredits(results: CourseResult[], config: GpaConfig = GPA_DEFAULTS): number {
  return resolveRetakes(results, config)
    .filter((r) => r.score >= config.passThreshold)
    .reduce((sum, r) => sum + r.credits, 0);
}

export type SemesterKey = { year: number; term: "spring" | "summer" | "fall" };

const TERM_ORDER = { fall: 0, spring: 1, summer: 2 } as const;

export function compareSemesters(a: SemesterKey, b: SemesterKey): number {
  return a.year - b.year || TERM_ORDER[a.term] - TERM_ORDER[b.term];
}

/** Numbers each subject's results 1, 2, … in the order the semesters were taken. */
export function withAttempts<T extends { subjectId: string; semester: SemesterKey }>(
  rows: T[],
): (T & { attempt: number })[] {
  const ordered = [...rows].sort((a, b) => compareSemesters(a.semester, b.semester));
  const seen = new Map<string, number>();
  return ordered.map((row) => {
    const attempt = (seen.get(row.subjectId) ?? 0) + 1;
    seen.set(row.subjectId, attempt);
    return { ...row, attempt };
  });
}
