from decimal import Decimal

import pytest

from app.core.errors import AppError
from app.modules.assignments.models import Assignment, LatePolicy
from app.modules.assignments.service import effective_points


def _assignment(policy: LatePolicy, penalty: str = "0") -> Assignment:
    return Assignment(
        max_points=Decimal("100"),
        late_policy=policy,
        late_penalty_percent=Decimal(penalty),
    )


def test_penalty_is_applied_to_late_grade() -> None:
    result = effective_points(_assignment(LatePolicy.PENALIZE, "25"), Decimal("80"), is_late=True)
    assert result == Decimal("60.00")


def test_rejected_late_grade_raises_domain_error() -> None:
    with pytest.raises(AppError) as error:
        effective_points(_assignment(LatePolicy.REJECT), Decimal("80"), is_late=True)
    assert error.value.code == "assignments.late_submission_rejected"
