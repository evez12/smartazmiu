"""The Python reference of the ÜOMG spec (docs/uomg-gpa-spec.md, section 6) against the cases shared with the web app.

The reference is executed from the document itself, so the text the product owner reads cannot drift from what is
tested. The same JSON drives `apps/web/src/features/gpa/uomg.test.ts` (D-106).
"""

import json
import re
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[3]
CASES = json.loads((ROOT / "infra/fixtures/uomg-rounding.json").read_text(encoding="utf-8"))[
    "cases"
]


@pytest.fixture(scope="module")
def reference() -> dict[str, Any]:
    spec = (ROOT / "docs/uomg-gpa-spec.md").read_text(encoding="utf-8")
    block = re.search(r"```python\n(.*?)```", spec, re.DOTALL)
    assert block is not None
    namespace: dict[str, Any] = {}
    exec(compile(block.group(1), "uomg-gpa-spec.md", "exec"), namespace)  # noqa: S102
    return namespace


def run(reference: dict[str, Any], courses: list[list[int]], digits: int) -> float:
    results = [
        reference["CourseResult"](f"c{index}", credits, score)
        for index, (credits, score) in enumerate(courses)
    ]
    value: float = reference["uomg"](results, reference["GpaConfig"](round_digits=digits))
    return value


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_the_reference_matches_the_shared_cases(
    reference: dict[str, Any], case: dict[str, Any]
) -> None:
    assert run(reference, case["courses"], case["digits"]) == case["expected"]


def test_exact_ties_round_up_where_builtin_round_does_not(reference: dict[str, Any]) -> None:
    # 64.225 is a tie; the double nearest to it is below, so the builtin gives 64.22. 72.5 is a tie that the
    # builtin sends to the even neighbour, 72.
    assert round(2569 / 40, 2) == 64.22
    assert round(145 / 2, 0) == 72
    assert run(reference, [[1, 73], [39, 64]], 2) == 64.23
    assert run(reference, [[1, 72], [1, 73]], 0) == 73


def test_transcript_empty_list_and_fractional_scores(reference: dict[str, Any]) -> None:
    transcript = [[5, 81], [8, 74], [5, 78], [8, 75], [4, 89]]
    assert run(reference, transcript, 1) == 78.1
    assert run(reference, [], 2) == 0.0
    # A score with decimals stays exact: 71.5 and 72 over equal credits is 71.75, a tie at one digit.
    results = [reference["CourseResult"]("a", 2, 71.5), reference["CourseResult"]("b", 2, 72)]
    assert reference["uomg"](results, reference["GpaConfig"](round_digits=1)) == 71.8
