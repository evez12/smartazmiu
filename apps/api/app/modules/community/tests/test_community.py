import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import inspect

from app.core.errors import AppError
from app.modules.community.models import FeedComment, FeedPost, ForumAnswer, ForumQuestion
from app.modules.community.schemas import PostCreate, QuestionCreate
from app.modules.community.service import _cursor, _decode


def test_cursor_round_trip() -> None:
    created = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)
    item_id = uuid.uuid4()
    assert _decode(_cursor(created, item_id)) == (created, item_id)


def test_invalid_cursor_is_rejected() -> None:
    with pytest.raises(AppError, match=r"community\.invalid_cursor"):
        _decode("not-a-cursor")


def test_content_validation_and_optimistic_versioning() -> None:
    assert PostCreate(body="A post").body == "A post"
    assert QuestionCreate(title="A question", body="Details").title == "A question"
    for model in (FeedPost, FeedComment, ForumQuestion, ForumAnswer):
        mapper = inspect(model)
        assert getattr(mapper, "version_id_col", None) is not None
        assert model.__table__.c.deleted_at is not None
