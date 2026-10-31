from datetime import UTC, datetime, timedelta

from app.core.ids import uuid7
from app.modules.quizzes.models import QuestionType, QuizQuestion
from app.modules.quizzes.service import attempt_expiry, auto_grade


def test_auto_grade_scores_closed_questions_but_not_short_answers() -> None:
    quiz_id = uuid7()
    mcq = QuizQuestion(
        id=uuid7(),
        quiz_id=quiz_id,
        position=1,
        type=QuestionType.MCQ,
        prompt="",
        points=2,
        correct_answer="a",
    )
    short = QuizQuestion(
        id=uuid7(),
        quiz_id=quiz_id,
        position=2,
        type=QuestionType.SHORT_ANSWER,
        prompt="",
        points=3,
        correct_answer="a",
    )
    assert auto_grade([mcq, short], {str(mcq.id): "a", str(short.id): "a"}) == (2, 5)


def test_attempt_expiry_uses_earliest_server_deadline() -> None:
    started = datetime(2026, 5, 1, tzinfo=UTC)
    assert attempt_expiry(started, 3600, started + timedelta(minutes=30)) == started + timedelta(
        minutes=30
    )


def test_open_questions_score_nothing_until_a_teacher_does() -> None:
    quiz_id = uuid7()
    multi = QuizQuestion(
        id=uuid7(),
        quiz_id=quiz_id,
        position=1,
        type=QuestionType.MULTI_SELECT,
        prompt="",
        points=3,
        options=[{"id": "a", "text": ""}, {"id": "b", "text": ""}, {"id": "c", "text": ""}],
        correct_answer=["a", "c"],
    )
    # All or nothing, whatever the order of the picked options.
    assert auto_grade([multi], {str(multi.id): ["c", "a"]}) == (3, 3)
    assert auto_grade([multi], {str(multi.id): ["a"]}) == (0, 3)
    assert auto_grade([multi], {}) == (0, 3)
