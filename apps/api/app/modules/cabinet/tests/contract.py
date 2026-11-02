"""What every ``CabinetProvider`` must satisfy; the real one joins this suite when it exists (D-126).

A provider's test module subclasses ``CabinetProviderContract`` and supplies three fixtures: ``provider``, a
``known_id`` it has a record for and an ``unknown_id`` it has none for.
"""

import pytest

from app.modules.cabinet.provider import (
    AppealStatus,
    CabinetNotFoundError,
    CabinetProvider,
)


class CabinetProviderContract:
    @pytest.fixture
    def provider(self) -> CabinetProvider:
        raise NotImplementedError

    @pytest.fixture
    def known_id(self) -> str:
        raise NotImplementedError

    @pytest.fixture
    def unknown_id(self) -> str:
        raise NotImplementedError

    async def test_every_answer_names_the_person_it_is_about(
        self, provider: CabinetProvider, known_id: str
    ) -> None:
        assert (await provider.grades(known_id)).university_id == known_id
        assert (await provider.transcript(known_id)).university_id == known_id
        assert (await provider.appeals(known_id)).university_id == known_id

    async def test_grades_are_scores_with_one_result_per_course_and_term(
        self, provider: CabinetProvider, known_id: str
    ) -> None:
        items = (await provider.grades(known_id)).items

        assert items
        assert all(0 <= grade.score <= 100 and grade.credits > 0 for grade in items)
        keys = [(g.subject_code, g.semester_year, g.semester_term) for g in items]
        assert len(keys) == len(set(keys))

    async def test_transcript_semesters_are_unique_and_credits_add_up(
        self, provider: CabinetProvider, known_id: str
    ) -> None:
        transcript = await provider.transcript(known_id)

        keys = [(s.semester_year, s.semester_term) for s in transcript.semesters]
        assert len(keys) == len(set(keys))
        for semester in transcript.semesters:
            assert 0 <= semester.credits_earned <= semester.credits_attempted
            assert semester.average is None or 0 <= semester.average <= 100
        assert transcript.credits_earned == sum(s.credits_earned for s in transcript.semesters)
        assert transcript.specialty_name

    async def test_appeals_have_unique_references_and_consistent_dates(
        self, provider: CabinetProvider, known_id: str
    ) -> None:
        items = (await provider.appeals(known_id)).items

        references = [appeal.reference for appeal in items]
        assert len(references) == len(set(references))
        for appeal in items:
            open_ = appeal.status in (AppealStatus.SUBMITTED, AppealStatus.UNDER_REVIEW)
            assert (appeal.decided_on is None) == open_
            assert appeal.decided_on is None or appeal.decided_on >= appeal.submitted_on

    async def test_the_same_question_gets_the_same_answer(
        self, provider: CabinetProvider, known_id: str
    ) -> None:
        assert await provider.grades(known_id) == await provider.grades(known_id)
        assert await provider.transcript(known_id) == await provider.transcript(known_id)
        assert await provider.appeals(known_id) == await provider.appeals(known_id)

    async def test_an_unknown_person_is_not_found_by_every_method(
        self, provider: CabinetProvider, unknown_id: str
    ) -> None:
        for ask in (provider.grades, provider.transcript, provider.appeals):
            with pytest.raises(CabinetNotFoundError):
                await ask(unknown_id)
