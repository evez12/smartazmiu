# SmartAzMİU — ÜOMG (GPA) Calculation Spec

## Context
AzMİU has no university-specific GPA formula. Like all higher-education institutions in Azerbaijan, it follows the national credit-system rules:
- Cabinet of Ministers Decision No. 348 (24.12.2013) — "Rules for organizing education with the credit system" (applies to all universities regardless of ownership).
- Ministry of Education Order No. 1060 (11.09.2008) — Regulation on assessing students' knowledge under the credit system.

ÜOMG (Ümumi Orta Müvəffəqiyyət Göstəricisi) = the Azerbaijani GPA. It is expressed on a **100-point scale**, not a 4.0 scale.

## 1. Course score (0–100)
- Max total per course: **100 points**
  - **50** — semester activity (attendance, seminar/lab, independent work, course work, etc.)
  - **50** — final exam
- **Exam threshold:** if the exam score is **< 17**, the exam points are NOT added to the semester points.

```
final_score = semester + exam   if exam >= 17
            = semester          otherwise
```

## 2. Letter grade mapping

| Score  | Letter | Label (AZ)    |
|--------|--------|---------------|
| 91–100 | A      | əla           |
| 81–90  | B      | çox yaxşı     |
| 71–80  | C      | yaxşı         |
| 61–70  | D      | kafi          |
| 51–60  | E      | qənaətbəxş    |
| < 51   | F      | qeyri-kafi    |

A course with grade F does not earn its credits.

## 3. ÜOMG formula (credit-weighted average)

```
ÜOMG = Σ (credits_i × score_i) / Σ credits_i
```

- Computed per semester and cumulatively (all semesters).
- Uses the numeric score (0–100), not the letter.

### Verification case (from a real transcript)
| Credits | Score |
|---------|-------|
| 5       | 81    |
| 8       | 74    |
| 5       | 78    |
| 8       | 75    |
| 4       | 89    |

Total credits = 30, Σ(credits × score) = 2343 → **ÜOMG = 78.1**. The implementation must reproduce this.

## 4. UI thresholds worth highlighting
- **≥ 71** — no interest on social student loan for that semester.
- **≥ 91** — top-tier benefits (loan interest waivers, etc.).

## 5. Open questions — make these CONFIGURABLE (not hard-coded)
These are not confirmed for AzMİU specifically; expose them as settings with the defaults below:

| Setting               | Default | Meaning |
|-----------------------|---------|---------|
| `include_failed`      | `true`  | Whether F-graded courses count in the denominator |
| `retake_policy`       | `"replace"` | `"replace"` = latest attempt replaces old score; `"average"` = all attempts count |
| `round_digits`        | `2`     | Decimal places for displayed ÜOMG; a tie rounds up (half-up, **unconfirmed**: check the university's grading regulations) |
| `min_exam_score`      | `17`    | Exam threshold |
| `pass_threshold`      | `51`    | Minimum score to earn credits |

## 6. Reference implementation (Python)

```python
from dataclasses import dataclass
from fractions import Fraction
from math import floor
from typing import Literal


@dataclass(frozen=True)
class GpaConfig:
    include_failed: bool = True
    retake_policy: Literal["replace", "average"] = "replace"
    round_digits: int = 2
    min_exam_score: float = 17
    pass_threshold: float = 51


@dataclass(frozen=True)
class CourseResult:
    course_id: str
    credits: int
    score: float  # 0-100
    attempt: int = 1


LETTER_SCALE: list[tuple[int, str]] = [
    (91, "A"),
    (81, "B"),
    (71, "C"),
    (61, "D"),
    (51, "E"),
]


def round_half_up(value: Fraction, digits: int) -> float:
    """A tie rounds up. Python's round() rounds half to even on a binary float, so 64.225 would give 64.22 and
    72.5 would give 72. Scores are whole numbers or have at most two decimals."""
    scale = 10**digits
    return floor(value * scale + Fraction(1, 2)) / scale


def letter_grade(score: float) -> str:
    return next(
        (letter for threshold, letter in LETTER_SCALE if score >= threshold), "F"
    )


def final_score(semester: float, exam: float, cfg: GpaConfig = GpaConfig()) -> float:
    # Exam points are discarded if below the minimum threshold
    return semester + exam if exam >= cfg.min_exam_score else semester


def resolve_retakes(results: list[CourseResult], cfg: GpaConfig) -> list[CourseResult]:
    if cfg.retake_policy == "average":
        return results
    latest: dict[str, CourseResult] = {}
    for r in results:
        if r.course_id not in latest or r.attempt > latest[r.course_id].attempt:
            latest[r.course_id] = r
    return list(latest.values())


def uomg(results: list[CourseResult], cfg: GpaConfig = GpaConfig()) -> float:
    pool = resolve_retakes(results, cfg)
    if not cfg.include_failed:
        pool = [r for r in pool if r.score >= cfg.pass_threshold]
    total_credits = sum(r.credits for r in pool)
    if total_credits == 0:
        return 0.0
    points = sum(r.credits * Fraction(str(r.score)) for r in pool)
    return round_half_up(points / total_credits, cfg.round_digits)
```

## 7. Required tests
- Transcript case above → `78.1` (with `round_digits=1`).
- Exact ties (`x.5`, `x.x5`, `x.xx5`) round up; the cases in `apps/web/src/features/gpa/uomg-rounding.json` are shared by the
  Python reference test and the TypeScript test, so the two cannot drift (D-106).
- Exam = 16 → exam points ignored.
- Letter boundaries: 50→F, 51→E, 60→E, 61→D, 90→B, 91→A, 100→A.
- Empty course list → `0.0`.
- Retake with `"replace"` → only latest attempt counted.
- `include_failed=False` → F courses excluded from denominator.

## Sources
- NK Decision No. 348: https://mdu.edu.az/wp-content/uploads/2025/01/Ali-təhsil-muəssisələrinin-bakalavriat-və-magistratura-səviyyələrində-tədrisin-təskili-348.pdf
- Ministry of Education Order No. 1060: https://mdu.edu.az/wp-content/uploads/2025/03/Emr-1060.pdf
- Student loan ÜOMG thresholds: https://edu.gov.az/uploads/ttk/teqdimat.pdf
