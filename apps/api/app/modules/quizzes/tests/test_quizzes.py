"""Quizzes: offering-scoped building, timed attempts, auto-grading, open questions, stats (§6.1, §13, D-092)."""

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.time import utc_now
from app.modules.audit.models import AuditLog
from app.modules.chat.tests.conftest import MakePerson, Person
from app.modules.materials.tests.test_materials import sign_in
from app.modules.quizzes.models import AttemptStatus, QuestionType, QuizAttempt, QuizQuestion
from app.modules.quizzes.schemas import QuestionCreateIn
from app.modules.quizzes.service import QuizService, clean_answers
from tests.support import TokenFactory

API = "/api/v1"
Seed = Callable[..., Awaitable[None]]

MCQ = {
    "type": "mcq",
    "prompt": "Medianın tərifi hansıdır?",
    "points": 2,
    "options": [{"id": "a", "text": "Orta qiymət"}, {"id": "b", "text": "Ortadakı qiymət"}],
    "correct_answer": "b",
}
MULTI = {
    "type": "multi_select",
    "prompt": "Mərkəzi meyl göstəricilərini seçin.",
    "points": 3,
    "options": [
        {"id": "a", "text": "Orta"},
        {"id": "b", "text": "Dispersiya"},
        {"id": "c", "text": "Median"},
    ],
    "correct_answer": ["a", "c"],
}
SHORT = {"type": "short_answer", "prompt": "Normal paylanmanı izah edin.", "points": 5}


@pytest.mark.parametrize(
    "bad",
    [
        {**MCQ, "correct_answer": "z"},
        {**MCQ, "options": [MCQ["options"][0]]},  # type: ignore[index]
        {**MCQ, "options": [{"id": "a", "text": "x"}, {"id": "a", "text": "y"}]},
        {**MULTI, "correct_answer": "a"},
        {**MULTI, "correct_answer": []},
        {**MULTI, "correct_answer": ["a", "z"]},
        {**SHORT, "options": [{"id": "a", "text": "x"}]},
        {**SHORT, "correct_answer": 5},
        {**MCQ, "points": 0},
    ],
)
def test_a_question_that_cannot_be_answered_correctly_is_refused(bad: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        QuestionCreateIn.model_validate(bad)


def test_answers_must_fit_their_question() -> None:
    quiz = uuid.uuid4()
    mcq = QuizQuestion(
        id=uuid.uuid4(),
        quiz_id=quiz,
        position=1,
        type=QuestionType.MCQ,
        prompt="",
        points=1,
        options=MCQ["options"],
        correct_answer="b",
    )
    short = QuizQuestion(
        id=uuid.uuid4(),
        quiz_id=quiz,
        position=2,
        type=QuestionType.SHORT_ANSWER,
        prompt="",
        points=1,
        options=[],
        correct_answer=None,
    )
    assert clean_answers([mcq, short], {str(mcq.id): "a", str(short.id): "mətn"}) == {
        str(mcq.id): "a",
        str(short.id): "mətn",
    }
    assert clean_answers([mcq], {str(mcq.id): None}) == {}
    for raw in ({str(mcq.id): "z"}, {str(mcq.id): ["a"]}, {str(short.id): 5}, {"başqa": "a"}):
        with pytest.raises(AppError, match=r"quizzes\.invalid_answers"):
            clean_answers([mcq, short], raw)


@pytest.fixture
async def people(
    client: AsyncClient, tokens: TokenFactory, seed: Seed, person: MakePerson
) -> dict[str, Person]:
    await seed()
    return {
        "leyla": await sign_in(
            client, tokens, "leyla.hasanova@smartazmiu.test", ["teacher"], "Leyla", "Həsənova"
        ),
        "aysel": await sign_in(
            client, tokens, "aysel.mammadova@smartazmiu.test", ["student"], "Aysel", "Məmmədova"
        ),
        "rauf": await sign_in(
            client, tokens, "rauf.mammadov@smartazmiu.test", ["teacher"], "Rauf", "Məmmədov"
        ),
        "outsider": await person("Orxan", "Rzayev"),
    }


async def offering_of(client: AsyncClient, who: Person) -> str:
    items = (await client.get(f"{API}/coursework/offerings", headers=who.headers)).json()["items"]
    found: str = next(
        o["id"] for o in items if (o["subject_code"], o["groups"]) == ("IQT-2102", ["765a2"])
    )
    return found


async def build(
    client: AsyncClient,
    teacher: Person,
    *questions: dict[str, Any],
    publish: bool = True,
    **quiz: Any,
) -> dict[str, Any]:
    created = await client.post(
        f"{API}/quizzes",
        headers=teacher.headers,
        json={
            "course_offering_id": await offering_of(client, teacher),
            "title": "Aralıq test",
            **quiz,
        },
    )
    assert created.status_code == 201, created.text
    detail: dict[str, Any] = created.json()
    for question in questions:
        added = await client.post(
            f"{API}/quizzes/{detail['id']}/questions", headers=teacher.headers, json=question
        )
        assert added.status_code == 201, added.text
        detail = added.json()
    if publish:
        published = await client.post(
            f"{API}/quizzes/{detail['id']}/publish", headers=teacher.headers
        )
        assert published.status_code == 200, published.text
        detail = published.json()
    return detail


async def start(client: AsyncClient, who: Person, quiz_id: str) -> Any:
    return await client.post(f"{API}/quizzes/{quiz_id}/attempts", headers=who.headers)


async def test_building_is_for_the_offerings_teachers_and_the_answer_stays_secret(
    client: AsyncClient, people: dict[str, Person]
) -> None:
    leyla, aysel, rauf, outsider = (people[k] for k in ("leyla", "aysel", "rauf", "outsider"))
    offering = await offering_of(client, leyla)
    for who in (rauf, aysel, outsider):
        refused = await client.post(
            f"{API}/quizzes",
            headers=who.headers,
            json={"course_offering_id": offering, "title": "X"},
        )
        assert (refused.status_code, refused.json()["error"]["code"]) == (
            404,
            "quizzes.offering_not_found",
        )

    draft = await build(client, leyla, MCQ, MULTI, SHORT, publish=False, time_limit_seconds=600)
    assert (draft["published"], draft["question_count"], draft["can_manage"]) == (False, 3, True)
    assert [q["position"] for q in draft["questions"]] == [1, 2, 3]
    assert draft["questions"][0]["correct_answer"] == "b"
    # Unpublished quizzes do not exist for students or strangers.
    for who in (aysel, outsider, rauf):
        assert (
            await client.get(f"{API}/quizzes/{draft['id']}", headers=who.headers)
        ).status_code == 404
        assert (await client.get(f"{API}/quizzes", headers=who.headers)).json()["items"] == []
    empty = await build(client, leyla, publish=False)
    nothing = await client.post(f"{API}/quizzes/{empty['id']}/publish", headers=leyla.headers)
    assert (nothing.status_code, nothing.json()["error"]["code"]) == (409, "quizzes.no_questions")

    removed = await client.delete(
        f"{API}/quizzes/{draft['id']}/questions/{draft['questions'][2]['id']}",
        headers=leyla.headers,
    )
    assert [q["position"] for q in removed.json()["questions"]] == [1, 2]
    published = await client.post(f"{API}/quizzes/{draft['id']}/publish", headers=leyla.headers)
    assert published.json()["published"] is True
    frozen = await client.post(
        f"{API}/quizzes/{draft['id']}/questions", headers=leyla.headers, json=SHORT
    )
    assert (frozen.status_code, frozen.json()["error"]["code"]) == (
        409,
        "quizzes.already_published",
    )
    assert (
        await client.post(f"{API}/quizzes/{draft['id']}/publish", headers=leyla.headers)
    ).status_code == 409

    seen = (await client.get(f"{API}/quizzes/{draft['id']}", headers=aysel.headers)).json()
    assert (seen["questions"], seen["can_manage"], seen["can_start"]) == (None, False, True)
    assert seen["attempts_used"] == 0
    assert "correct_answer" not in (await client.get(f"{API}/quizzes", headers=aysel.headers)).text
    attempt = await start(client, aysel, draft["id"])
    assert attempt.status_code == 201, attempt.text
    assert "correct_answer" not in attempt.text
    assert [q["position"] for q in attempt.json()["questions"]] == [1, 2]
    # Strangers cannot start, read the results or the statistics.
    assert (await start(client, outsider, draft["id"])).status_code == 404
    for path in ("attempts", "stats"):
        assert (
            await client.get(f"{API}/quizzes/{draft['id']}/{path}", headers=aysel.headers)
        ).status_code == 403
        assert (
            await client.get(f"{API}/quizzes/{draft['id']}/{path}", headers=outsider.headers)
        ).status_code == 404
    assert (await start(client, leyla, draft["id"])).status_code == 403


async def test_closed_questions_are_graded_open_ones_by_the_teacher(
    client: AsyncClient, db: AsyncSession, people: dict[str, Person]
) -> None:
    leyla, aysel = people["leyla"], people["aysel"]
    quiz = await build(client, leyla, MCQ, MULTI, SHORT)
    first, second, third = quiz["questions"]

    attempt = (await start(client, aysel, quiz["id"])).json()
    resumed = (await start(client, aysel, quiz["id"])).json()
    assert resumed["id"] == attempt["id"]
    saved = await client.patch(
        f"{API}/quiz-attempts/{attempt['id']}",
        headers=aysel.headers,
        json={"answers": {first["id"]: "b", second["id"]: ["c", "a"]}},
    )
    assert saved.status_code == 200
    assert saved.json()["status"] == "in_progress"
    assert saved.json()["server_time"]
    invalid = await client.patch(
        f"{API}/quiz-attempts/{attempt['id']}",
        headers=aysel.headers,
        json={"answers": {first["id"]: "z"}},
    )
    assert (invalid.status_code, invalid.json()["error"]["code"]) == (
        422,
        "quizzes.invalid_answers",
    )

    done = await client.post(
        f"{API}/quiz-attempts/{attempt['id']}/submit",
        headers=aysel.headers,
        json={"answers": {first["id"]: "b", second["id"]: ["c", "a"], third["id"]: "Zəng əyrisi"}},
    )
    assert done.status_code == 200, done.text
    result = done.json()
    assert (result["status"], result["score"], result["max_score"], result["pending_review"]) == (
        "submitted",
        5,
        10,
        True,
    )
    assert result["questions"] is None
    closed = await client.patch(
        f"{API}/quiz-attempts/{attempt['id']}", headers=aysel.headers, json={"answers": {}}
    )
    assert (closed.status_code, closed.json()["error"]["code"]) == (409, "quizzes.attempt_closed")

    # The teacher reads the answers, scores the open one, and the student's result becomes final.
    listed = (
        await client.get(f"{API}/quizzes/{quiz['id']}/attempts", headers=leyla.headers)
    ).json()["items"]
    assert [(r["student"]["display_name"], r["pending_review"]) for r in listed] == [
        ("Aysel Məmmədova", True)
    ]
    review = (
        await client.get(f"{API}/quiz-attempts/{attempt['id']}/review", headers=leyla.headers)
    ).json()
    assert review["answers"][third["id"]] == "Zəng əyrisi"
    assert review["questions"][0]["correct_answer"] == "b"
    for scores, code in (
        ({first["id"]: 1}, "quizzes.not_an_open_question"),
        ({third["id"]: 6}, "quizzes.points_out_of_range"),
        ({third["id"]: -1}, "quizzes.points_out_of_range"),
    ):
        bad = await client.put(
            f"{API}/quiz-attempts/{attempt['id']}/open-question-scores",
            headers=leyla.headers,
            json={"scores": scores},
        )
        assert (bad.status_code, bad.json()["error"]["code"]) == (422, code)
    assert (
        await client.put(
            f"{API}/quiz-attempts/{attempt['id']}/open-question-scores",
            headers=aysel.headers,
            json={"scores": {third["id"]: 5}},
        )
    ).status_code == 403
    scored = await client.put(
        f"{API}/quiz-attempts/{attempt['id']}/open-question-scores",
        headers=leyla.headers,
        json={"scores": {third["id"]: 4}},
    )
    assert scored.status_code == 200, scored.text
    assert (scored.json()["score"], scored.json()["pending_review"]) == (9, False)
    mine = (await client.get(f"{API}/quizzes/{quiz['id']}", headers=aysel.headers)).json()
    assert (mine["attempts_used"], mine["best_percent"]) == (1, 90)
    assert mine["can_start"] is False
    assert mine["start_blocked"] == "attempt_limit_reached"
    limit = await start(client, aysel, quiz["id"])
    assert (limit.status_code, limit.json()["error"]["code"]) == (
        409,
        "quizzes.attempt_limit_reached",
    )

    # Scores are personal data: the audit entry names the attempt, not the points.
    entry = await db.scalar(select(AuditLog).where(AuditLog.action == "quiz.graded"))
    assert entry is not None
    assert entry.details == {"quiz_id": quiz["id"]}


async def test_time_is_the_servers_and_late_answers_are_not_counted(
    client: AsyncClient, db: AsyncSession, people: dict[str, Person]
) -> None:
    leyla, aysel = people["leyla"], people["aysel"]
    quiz = await build(client, leyla, MCQ, SHORT, time_limit_seconds=60, max_attempts=3)
    first, second = quiz["questions"]
    attempt = (await start(client, aysel, quiz["id"])).json()
    assert attempt["expires_at"] is not None
    await client.patch(
        f"{API}/quiz-attempts/{attempt['id']}",
        headers=aysel.headers,
        json={"answers": {first["id"]: "b"}},
    )

    # Time ran out ten seconds ago: what arrives now is not counted, what was saved before is.
    await db.execute(update(QuizAttempt).values(expires_at=utc_now() - timedelta(seconds=10)))
    await db.commit()
    late = await client.post(
        f"{API}/quiz-attempts/{attempt['id']}/submit",
        headers=aysel.headers,
        json={"answers": {first["id"]: "a", second["id"]: "Gec yazılıb"}},
    )
    assert (late.status_code, late.json()["error"]["code"]) == (409, "quizzes.time_is_up")
    final = (await client.get(f"{API}/quiz-attempts/{attempt['id']}", headers=aysel.headers)).json()
    assert (final["status"], final["score"], final["answers"]) == (
        "auto_submitted",
        2,
        {first["id"]: "b"},
    )

    # An attempt the student walked away from is closed by the job, once.
    again = (await start(client, aysel, quiz["id"])).json()
    assert again["attempt_number"] == 2
    assert again["id"] != attempt["id"]
    await db.execute(
        update(QuizAttempt)
        .where(QuizAttempt.id == uuid.UUID(again["id"]))
        .values(expires_at=utc_now() - timedelta(minutes=5))
    )
    await db.commit()
    assert await QuizService(db).finalize_expired() == 1
    assert await QuizService(db).finalize_expired() == 0
    closed = await db.get(QuizAttempt, uuid.UUID(again["id"]))
    assert closed is not None
    await db.refresh(closed)
    assert (closed.status, closed.score) == (AttemptStatus.AUTO_SUBMITTED, 0)


async def test_a_quiz_has_a_window_and_two_clicks_start_one_attempt(
    client: AsyncClient, people: dict[str, Person]
) -> None:
    leyla, aysel = people["leyla"], people["aysel"]
    soon = (utc_now() + timedelta(days=1)).isoformat()
    ended = (utc_now() - timedelta(hours=1)).isoformat()
    later = await build(client, leyla, MCQ, available_from=soon)
    assert (
        await client.get(f"{API}/quizzes/{later['id']}", headers=aysel.headers)
    ).status_code == 404
    over = await build(client, leyla, MCQ, deadline=ended)
    seen = (await client.get(f"{API}/quizzes/{over['id']}", headers=aysel.headers)).json()
    assert (seen["can_start"], seen["start_blocked"]) == (False, "closed")
    expired = await start(client, aysel, over["id"])
    assert (expired.status_code, expired.json()["error"]["code"]) == (409, "quizzes.expired")

    quiz = await build(client, leyla, MCQ, max_attempts=3)
    responses = await asyncio.gather(*(start(client, aysel, quiz["id"]) for _ in range(4)))
    assert {r.status_code for r in responses} <= {200, 201}
    assert len({r.json()["id"] for r in responses}) == 1
    assert (await client.get(f"{API}/quizzes/{quiz['id']}", headers=aysel.headers)).json()[
        "attempts_used"
    ] == 1


async def test_statistics_count_attempts_and_rate_each_closed_question(
    client: AsyncClient, people: dict[str, Person]
) -> None:
    leyla, aysel = people["leyla"], people["aysel"]
    quiz = await build(client, leyla, MCQ, SHORT, max_attempts=2)
    first, second = quiz["questions"]
    for answer, text in (("b", "Doğru"), ("a", "Səhv")):
        attempt = (await start(client, aysel, quiz["id"])).json()
        await client.post(
            f"{API}/quiz-attempts/{attempt['id']}/submit",
            headers=aysel.headers,
            json={"answers": {first["id"]: answer, second["id"]: text}},
        )
    stats = (await client.get(f"{API}/quizzes/{quiz['id']}/stats", headers=leyla.headers)).json()
    assert (stats["submitted_attempts"], stats["students"], stats["pending_review"]) == (2, 1, 2)
    assert stats["average_percent"] == 14  # 2 of 7 points, then 0 of 7
    assert {b["label"]: b["count"] for b in stats["distribution"]} == {
        "0–50": 2,
        "51–70": 0,
        "71–90": 0,
        "91–100": 0,
    }
    assert [(q["position"], q["correct_percent"]) for q in stats["questions"]] == [
        (1, 50),
        (2, None),
    ]
    listed = (await client.get(f"{API}/quizzes", headers=leyla.headers)).json()["items"][0]
    assert (listed["students_attempted"], listed["attempts_used"]) == (1, None)
