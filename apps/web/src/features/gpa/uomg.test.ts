import { describe, expect, it } from "vitest";

import {
  earnedCredits,
  finalScore,
  GPA_DEFAULTS,
  letterGrade,
  resolveRetakes,
  uomg,
  withAttempts,
  type CourseResult,
} from "./uomg";

const result = (courseId: string, credits: number, score: number, attempt = 1): CourseResult => ({
  courseId,
  credits,
  score,
  attempt,
});

describe("ÜOMG", () => {
  it("reproduces the transcript case: 2343 / 30 = 78.1", () => {
    const transcript = [
      result("a", 5, 81),
      result("b", 8, 74),
      result("c", 5, 78),
      result("d", 8, 75),
      result("e", 4, 89),
    ];
    expect(uomg(transcript, { ...GPA_DEFAULTS, roundDigits: 1 })).toBe(78.1);
    expect(uomg(transcript)).toBe(78.1);
  });

  it("ignores an exam below the threshold", () => {
    expect(finalScore(30, 16)).toBe(30);
    expect(finalScore(30, 17)).toBe(47);
    expect(finalScore(30, 16, { ...GPA_DEFAULTS, minExamScore: 10 })).toBe(46);
  });

  it("maps the letter boundaries", () => {
    const letters = [50, 51, 60, 61, 70, 71, 80, 81, 90, 91, 100].map(letterGrade);
    expect(letters).toEqual(["F", "E", "E", "D", "D", "C", "C", "B", "B", "A", "A"]);
  });

  it("is zero for an empty list", () => {
    expect(uomg([])).toBe(0);
  });

  it("lets the latest attempt replace the old score, or averages every attempt", () => {
    const attempts = [result("math", 6, 40, 1), result("math", 6, 80, 2), result("art", 4, 70)];
    expect(resolveRetakes(attempts, GPA_DEFAULTS).map((r) => r.score)).toEqual([80, 70]);
    expect(uomg(attempts)).toBe(76);
    expect(uomg(attempts, { ...GPA_DEFAULTS, retakePolicy: "average" })).toBe(62.5);
  });

  it("drops failed courses from the denominator when asked to", () => {
    const mixed = [result("a", 5, 80), result("b", 5, 40)];
    expect(uomg(mixed)).toBe(60);
    expect(uomg(mixed, { ...GPA_DEFAULTS, includeFailed: false })).toBe(80);
  });

  it("rounds to the configured digits", () => {
    const thirds = [result("a", 3, 70), result("b", 3, 71), result("c", 3, 72)];
    expect(uomg([result("x", 3, 71), result("y", 6, 72)])).toBe(71.67);
    expect(
      uomg([result("x", 3, 71), result("y", 6, 72)], { ...GPA_DEFAULTS, roundDigits: 0 }),
    ).toBe(72);
    expect(uomg(thirds)).toBe(71);
  });

  it("counts only passed, latest courses as earned credits", () => {
    const attempts = [result("math", 6, 40, 1), result("math", 6, 80, 2), result("art", 4, 45)];
    expect(earnedCredits(attempts)).toBe(6);
  });

  it("numbers the attempts of a subject in semester order", () => {
    const rows = withAttempts([
      { subjectId: "m", semester: { year: 2025, term: "spring" as const } },
      { subjectId: "m", semester: { year: 2024, term: "fall" as const } },
      { subjectId: "p", semester: { year: 2024, term: "fall" as const } },
    ]);
    expect(rows.map((r) => [r.subjectId, r.attempt])).toEqual([
      ["m", 1],
      ["p", 1],
      ["m", 2],
    ]);
  });
});
