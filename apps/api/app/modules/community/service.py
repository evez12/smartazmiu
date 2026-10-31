"""Feed and Q&A forum (§6, Sprint 12, D-090): university-wide spaces for every signed-in account."""

import base64
import re
import uuid
from collections import defaultdict
from datetime import datetime
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import ColumnElement, Select, and_, delete, exists, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.ratelimit import RateLimit, enforce_rate_limit
from app.core.time import utc_now
from app.modules.audit.models import AuditAction
from app.modules.audit.service import record_audit
from app.modules.chat.blocked_terms import BlockedTermService
from app.modules.chat.lookup import find_message
from app.modules.chat.mentions import USER_MENTION
from app.modules.chat.models import ChannelMember, MessageModeration
from app.modules.chat.schemas import AuthorOut
from app.modules.community.models import (
    CommunityTag,
    FeedComment,
    FeedPost,
    FeedPostTag,
    ForumAnswer,
    ForumQuestion,
    ForumQuestionTag,
    ForumVote,
    HelpfulReaction,
)
from app.modules.community.schemas import (
    AnswerCreate,
    AnswerOut,
    CommentCreate,
    CommentOut,
    CommentPage,
    ContentKind,
    PostCreate,
    PostOut,
    PostPage,
    QuestionCreate,
    QuestionDetailOut,
    QuestionPage,
    QuestionSummaryOut,
    TagOut,
)
from app.modules.users.models import PersonType, User
from app.modules.users.profile import photo_url
from app.modules.users.service import CurrentUser

POST_LIMIT = RateLimit("community_post", limit=10, window_seconds=3600)
QUESTION_LIMIT = RateLimit("community_question", limit=10, window_seconds=3600)
COMMENT_LIMIT = RateLimit("community_comment", limit=60, window_seconds=3600)
ANSWER_LIMIT = RateLimit("community_answer", limit=30, window_seconds=3600)
REACTION_LIMIT = RateLimit("community_reaction", limit=60, window_seconds=60)

MODERATE = "admin.reports.handle"
"""Report handlers (staff, admin) see hidden content and hide or restore it (D-070, D-090)."""
VERIFIERS = frozenset({"teacher", "staff"})
EXCERPT = 300
SPACES = re.compile(r" {2,}")
PAGE = 20

CONTENT: dict[str, Any] = {
    "post": FeedPost,
    "comment": FeedComment,
    "question": ForumQuestion,
    "answer": ForumAnswer,
}


def _cursor(value: datetime, item_id: uuid.UUID) -> str:
    return base64.urlsafe_b64encode(f"{value.isoformat()}|{item_id}".encode()).decode()


def _decode(value: str | None) -> tuple[datetime, uuid.UUID] | None:
    if not value:
        return None
    try:
        raw = base64.urlsafe_b64decode(value.encode()).decode().split("|")
        return datetime.fromisoformat(raw[0]), uuid.UUID(raw[1])
    except (ValueError, IndexError, UnicodeError) as exc:
        raise AppError("community.invalid_cursor", 422) from exc


def _author(user: User | None) -> AuthorOut | None:
    if user is None:
        return None
    badge = "teacher" if user.person_type is PersonType.TEACHER else None
    return AuthorOut(
        id=str(user.id), display_name=user.display_name, photo_url=photo_url(user), badge=badge
    )


def visible(model: Any, viewer: CurrentUser) -> ColumnElement[bool]:
    """Deleted content is gone for everyone; hidden content stays visible to its author and to report
    handlers, so nobody else can read it while it waits for review (§5.5)."""
    alive: ColumnElement[bool] = model.deleted_at.is_(None)
    if viewer.has_permission(MODERATE):
        return alive
    return and_(alive, or_(model.hidden_at.is_(None), model.author_id == viewer.id))


def _public(model: Any) -> ColumnElement[bool]:
    """What counts towards the numbers everyone sees."""
    return and_(model.deleted_at.is_(None), model.hidden_at.is_(None))


class CommunityService:
    def __init__(self, session: AsyncSession, cache: Redis) -> None:
        self.session = session
        self.cache = cache

    # --- shared -----------------------------------------------------------------------------

    async def tags(self) -> list[TagOut]:
        rows = await self.session.scalars(select(CommunityTag).order_by(CommunityTag.name))
        return [TagOut(id=str(tag.id), slug=tag.slug, name=tag.name) for tag in rows]

    async def _tags_of(
        self, link: Any, parent: Any, ids: list[uuid.UUID]
    ) -> dict[Any, list[TagOut]]:
        found: dict[Any, list[TagOut]] = defaultdict(list)
        if not ids:
            return found
        rows = await self.session.execute(
            select(parent, CommunityTag)
            .join(CommunityTag, CommunityTag.id == link.tag_id)
            .where(parent.in_(ids))
            .order_by(CommunityTag.name)
        )
        for parent_id, tag in rows:
            found[parent_id].append(TagOut(id=str(tag.id), slug=tag.slug, name=tag.name))
        return found

    async def _check_tags(self, tag_ids: list[uuid.UUID]) -> list[uuid.UUID]:
        unique = list(dict.fromkeys(tag_ids))
        if unique:
            known = await self.session.scalar(
                select(func.count()).select_from(CommunityTag).where(CommunityTag.id.in_(unique))
            )
            if known != len(unique):
                raise AppError("community.tag_not_found", 422)
        return unique

    async def _check_text(self, *parts: str) -> None:
        """The admin's blocked terms (§5.5, D-086) apply here too. There is no review queue for the feed or the
        forum, so a held term also refuses publication (D-090)."""
        if await BlockedTermService(self.session).check("\n".join(parts)) is not None:
            raise AppError("community.content_rejected", 422)

    async def _replay(self, model: Any, user: CurrentUser, key: str | None) -> Any:
        if not key:
            return None
        return await self.session.scalar(
            select(model).where(model.author_id == user.id, model.idempotency_key == key)
        )

    async def _people(self, ids: set[uuid.UUID | None]) -> dict[uuid.UUID, User]:
        wanted = {person for person in ids if person is not None}
        if not wanted:
            return {}
        return {
            person.id: person
            for person in await self.session.scalars(select(User).where(User.id.in_(wanted)))
        }

    async def delete_own(self, user: CurrentUser, kind: ContentKind, item_id: uuid.UUID) -> None:
        model = CONTENT[kind]
        result = await self.session.execute(
            update(model)
            .where(model.id == item_id, model.author_id == user.id, model.deleted_at.is_(None))
            .values(deleted_at=utc_now())
        )
        if not result.rowcount:  # type: ignore[attr-defined]
            raise AppError("community.not_found", 404)
        if kind == "answer":
            # A removed answer cannot stay the accepted one.
            await self.session.execute(
                update(ForumQuestion)
                .where(ForumQuestion.accepted_answer_id == item_id)
                .values(accepted_answer_id=None)
            )
        await self.session.commit()

    async def set_hidden(
        self, actor: CurrentUser, kind: ContentKind, item_id: uuid.UUID, hidden: bool
    ) -> None:
        model = CONTENT[kind]
        item = await self.session.scalar(
            select(model).where(model.id == item_id, model.deleted_at.is_(None)).with_for_update()
        )
        if item is None:
            raise AppError("community.not_found", 404)
        if (item.hidden_at is not None) is hidden:
            return
        item.hidden_at = utc_now() if hidden else None
        record_audit(
            self.session,
            AuditAction.COMMUNITY_HIDDEN if hidden else AuditAction.COMMUNITY_SHOWN,
            actor_id=actor.id,
            target_type=kind,
            target_id=item_id,
        )
        await self.session.commit()

    # --- feed -------------------------------------------------------------------------------

    def _posts(self, viewer: CurrentUser) -> Select[Any]:
        helpful = (
            select(func.count())
            .where(HelpfulReaction.post_id == FeedPost.id)
            .correlate(FeedPost)
            .scalar_subquery()
        )
        comments = (
            select(func.count())
            .where(FeedComment.post_id == FeedPost.id, _public(FeedComment))
            .correlate(FeedPost)
            .scalar_subquery()
        )
        mine = exists().where(
            HelpfulReaction.post_id == FeedPost.id, HelpfulReaction.user_id == viewer.id
        )
        return (
            select(FeedPost, User, helpful, comments, mine)
            .outerjoin(User, User.id == FeedPost.author_id)
            .where(visible(FeedPost, viewer))
        )

    async def _post_out(self, viewer: CurrentUser, rows: list[Any]) -> list[PostOut]:
        tags = await self._tags_of(FeedPostTag, FeedPostTag.post_id, [row[0].id for row in rows])
        return [
            PostOut(
                id=str(post.id),
                author=_author(author),
                body=post.body,
                tags=tags[post.id],
                helpful_count=helpful,
                comment_count=comments,
                my_helpful=mine,
                mine=post.author_id == viewer.id,
                hidden=post.hidden_at is not None,
                created_at=post.created_at,
            )
            for post, author, helpful, comments, mine in rows
        ]

    async def posts(
        self, viewer: CurrentUser, cursor: str | None, tag: str | None, limit: int = PAGE
    ) -> PostPage:
        query = self._posts(viewer)
        if tag:
            query = query.where(
                exists().where(
                    FeedPostTag.post_id == FeedPost.id,
                    FeedPostTag.tag_id == CommunityTag.id,
                    CommunityTag.slug == tag,
                )
            )
        marker = _decode(cursor)
        if marker:
            created, item_id = marker
            query = query.where(
                or_(
                    FeedPost.created_at < created,
                    and_(FeedPost.created_at == created, FeedPost.id < item_id),
                )
            )
        rows = list(
            await self.session.execute(
                query.order_by(FeedPost.created_at.desc(), FeedPost.id.desc()).limit(limit + 1)
            )
        )
        more = len(rows) > limit
        rows = rows[:limit]
        last = rows[-1][0] if rows else None
        return PostPage(
            items=await self._post_out(viewer, rows),
            next_cursor=_cursor(last.created_at, last.id) if more and last else None,
        )

    async def _post(self, viewer: CurrentUser, post_id: uuid.UUID) -> PostOut:
        rows = list(await self.session.execute(self._posts(viewer).where(FeedPost.id == post_id)))
        if not rows:
            raise AppError("community.post_not_found", 404)
        return (await self._post_out(viewer, rows))[0]

    async def create_post(self, user: CurrentUser, body: PostCreate, key: str | None) -> PostOut:
        replay = await self._replay(FeedPost, user, key)
        if replay is not None:
            return await self._post(user, replay.id)
        tag_ids = await self._check_tags(body.tag_ids)
        await self._check_text(body.body)
        await enforce_rate_limit(self.cache, POST_LIMIT, str(user.id))
        post = FeedPost(author_id=user.id, body=body.body.strip(), idempotency_key=key)
        self.session.add(post)
        await self.session.flush()
        self.session.add_all([FeedPostTag(post_id=post.id, tag_id=tag) for tag in tag_ids])
        await self.session.commit()
        return await self._post(user, post.id)

    async def _readable_post(self, viewer: CurrentUser, post_id: uuid.UUID) -> FeedPost:
        post = await self.session.scalar(
            select(FeedPost).where(FeedPost.id == post_id, visible(FeedPost, viewer))
        )
        if post is None:
            raise AppError("community.post_not_found", 404)
        return post

    async def comments(
        self, viewer: CurrentUser, post_id: uuid.UUID, after: str | None, limit: int = 50
    ) -> CommentPage:
        await self._readable_post(viewer, post_id)
        query = (
            select(FeedComment, User)
            .outerjoin(User, User.id == FeedComment.author_id)
            .where(FeedComment.post_id == post_id, visible(FeedComment, viewer))
        )
        marker = _decode(after)
        if marker:
            created, item_id = marker
            query = query.where(
                or_(
                    FeedComment.created_at > created,
                    and_(FeedComment.created_at == created, FeedComment.id > item_id),
                )
            )
        rows = list(
            await self.session.execute(
                query.order_by(FeedComment.created_at, FeedComment.id).limit(limit + 1)
            )
        )
        more = len(rows) > limit
        rows = rows[:limit]
        last = rows[-1][0] if rows else None
        return CommentPage(
            items=[self._comment_out(viewer, comment, author) for comment, author in rows],
            next_cursor=_cursor(last.created_at, last.id) if more and last else None,
        )

    def _comment_out(
        self, viewer: CurrentUser, comment: FeedComment, author: User | None
    ) -> CommentOut:
        return CommentOut(
            id=str(comment.id),
            post_id=str(comment.post_id),
            author=_author(author),
            body=comment.body,
            mine=comment.author_id == viewer.id,
            hidden=comment.hidden_at is not None,
            created_at=comment.created_at,
        )

    async def comment(
        self, user: CurrentUser, post_id: uuid.UUID, body: CommentCreate, key: str | None
    ) -> CommentOut:
        replay = await self._replay(FeedComment, user, key)
        if replay is None:
            await self._readable_post(user, post_id)
            await self._check_text(body.body)
            await enforce_rate_limit(self.cache, COMMENT_LIMIT, str(user.id))
            replay = FeedComment(
                post_id=post_id, author_id=user.id, body=body.body.strip(), idempotency_key=key
            )
            self.session.add(replay)
            await self.session.commit()
        return self._comment_out(user, replay, await self.session.get(User, user.id))

    async def set_helpful(self, user: CurrentUser, post_id: uuid.UUID, active: bool) -> None:
        post = await self._readable_post(user, post_id)
        if post.author_id == user.id:
            raise AppError("community.own_content", 422)
        await enforce_rate_limit(self.cache, REACTION_LIMIT, str(user.id))
        if active:
            await self.session.execute(
                insert(HelpfulReaction)
                .values(post_id=post_id, user_id=user.id)
                .on_conflict_do_nothing()
            )
        else:
            await self.session.execute(
                delete(HelpfulReaction).where(
                    HelpfulReaction.post_id == post_id, HelpfulReaction.user_id == user.id
                )
            )
        await self.session.commit()

    # --- forum ------------------------------------------------------------------------------

    def _questions(self, viewer: CurrentUser) -> Select[Any]:
        answers = (
            select(func.count())
            .where(ForumAnswer.question_id == ForumQuestion.id, _public(ForumAnswer))
            .correlate(ForumQuestion)
            .scalar_subquery()
        )
        verified = exists().where(
            ForumAnswer.question_id == ForumQuestion.id,
            ForumAnswer.teacher_verified.is_(True),
            _public(ForumAnswer),
        )
        return (
            select(ForumQuestion, User, answers, verified)
            .outerjoin(User, User.id == ForumQuestion.author_id)
            .where(visible(ForumQuestion, viewer))
        )

    async def questions(
        self, viewer: CurrentUser, cursor: str | None, tag: str | None, limit: int = PAGE
    ) -> QuestionPage:
        query = self._questions(viewer)
        if tag:
            query = query.where(
                exists().where(
                    ForumQuestionTag.question_id == ForumQuestion.id,
                    ForumQuestionTag.tag_id == CommunityTag.id,
                    CommunityTag.slug == tag,
                )
            )
        marker = _decode(cursor)
        if marker:
            created, item_id = marker
            query = query.where(
                or_(
                    ForumQuestion.created_at < created,
                    and_(ForumQuestion.created_at == created, ForumQuestion.id < item_id),
                )
            )
        rows = list(
            await self.session.execute(
                query.order_by(ForumQuestion.created_at.desc(), ForumQuestion.id.desc()).limit(
                    limit + 1
                )
            )
        )
        more = len(rows) > limit
        rows = rows[:limit]
        tags = await self._tags_of(
            ForumQuestionTag, ForumQuestionTag.question_id, [row[0].id for row in rows]
        )
        last = rows[-1][0] if rows else None
        return QuestionPage(
            items=[
                QuestionSummaryOut(
                    id=str(question.id),
                    author=_author(author),
                    title=question.title,
                    excerpt=question.body[:EXCERPT],
                    tags=tags[question.id],
                    answer_count=answer_count,
                    accepted=question.accepted_answer_id is not None,
                    teacher_verified=verified,
                    mine=question.author_id == viewer.id,
                    hidden=question.hidden_at is not None,
                    created_at=question.created_at,
                )
                for question, author, answer_count, verified in rows
            ],
            next_cursor=_cursor(last.created_at, last.id) if more and last else None,
        )

    async def _readable_question(
        self, viewer: CurrentUser, question_id: uuid.UUID
    ) -> ForumQuestion:
        question = await self.session.scalar(
            select(ForumQuestion).where(
                ForumQuestion.id == question_id, visible(ForumQuestion, viewer)
            )
        )
        if question is None:
            raise AppError("community.question_not_found", 404)
        return question

    async def question(self, viewer: CurrentUser, question_id: uuid.UUID) -> QuestionDetailOut:
        question = await self._readable_question(viewer, question_id)
        score = (
            select(func.coalesce(func.sum(ForumVote.value), 0))
            .where(ForumVote.answer_id == ForumAnswer.id)
            .correlate(ForumAnswer)
            .scalar_subquery()
        )
        my_vote = (
            select(ForumVote.value)
            .where(ForumVote.answer_id == ForumAnswer.id, ForumVote.user_id == viewer.id)
            .correlate(ForumAnswer)
            .scalar_subquery()
        )
        answers = list(
            await self.session.execute(
                select(ForumAnswer, score, my_vote)
                .where(ForumAnswer.question_id == question.id, visible(ForumAnswer, viewer))
                .order_by(ForumAnswer.created_at, ForumAnswer.id)
            )
        )
        people = await self._people(
            {question.author_id}
            | {answer.author_id for answer, _, _ in answers}
            | {answer.verified_by for answer, _, _ in answers}
        )
        tags = await self._tags_of(ForumQuestionTag, ForumQuestionTag.question_id, [question.id])
        accepted = question.accepted_answer_id
        return QuestionDetailOut(
            id=str(question.id),
            author=_author(people.get(question.author_id)),
            title=question.title,
            body=question.body,
            tags=tags[question.id],
            accepted_answer_id=str(accepted) if accepted else None,
            teacher_verified=any(
                answer.teacher_verified and answer.hidden_at is None for answer, _, _ in answers
            ),
            mine=question.author_id == viewer.id,
            hidden=question.hidden_at is not None,
            created_at=question.created_at,
            can_verify=bool(viewer.roles & VERIFIERS),
            answers=[
                AnswerOut(
                    id=str(answer.id),
                    author=_author(people.get(answer.author_id)),
                    body=answer.body,
                    score=int(answer_score),
                    my_vote=vote or 0,
                    accepted=answer.id == accepted,
                    verified_by=_author(people.get(answer.verified_by))
                    if answer.teacher_verified and answer.verified_by
                    else None,
                    mine=answer.author_id == viewer.id,
                    hidden=answer.hidden_at is not None,
                    created_at=answer.created_at,
                )
                for answer, answer_score, vote in answers
            ],
        )

    async def create_question(
        self, user: CurrentUser, body: QuestionCreate, key: str | None
    ) -> QuestionDetailOut:
        replay = await self._replay(ForumQuestion, user, key)
        if replay is not None:
            return await self.question(user, replay.id)
        tag_ids = await self._check_tags(body.tag_ids)
        await self._check_text(body.title, body.body)
        await enforce_rate_limit(self.cache, QUESTION_LIMIT, str(user.id))
        question = await self._add_question(user, body.title, body.body, tag_ids, key)
        await self.session.commit()
        return await self.question(user, question.id)

    async def _add_question(
        self, user: CurrentUser, title: str, body: str, tag_ids: list[uuid.UUID], key: str | None
    ) -> ForumQuestion:
        question = ForumQuestion(
            author_id=user.id, title=title.strip(), body=body.strip(), idempotency_key=key
        )
        self.session.add(question)
        await self.session.flush()
        self.session.add_all(
            [ForumQuestionTag(question_id=question.id, tag_id=tag) for tag in tag_ids]
        )
        return question

    async def answer(
        self, user: CurrentUser, question_id: uuid.UUID, body: AnswerCreate, key: str | None
    ) -> QuestionDetailOut:
        if await self._replay(ForumAnswer, user, key) is None:
            await self._readable_question(user, question_id)
            await self._check_text(body.body)
            await enforce_rate_limit(self.cache, ANSWER_LIMIT, str(user.id))
            self.session.add(
                ForumAnswer(
                    question_id=question_id,
                    author_id=user.id,
                    body=body.body.strip(),
                    idempotency_key=key,
                )
            )
            await self.session.commit()
        return await self.question(user, question_id)

    async def _readable_answer(self, viewer: CurrentUser, answer_id: uuid.UUID) -> ForumAnswer:
        answer = await self.session.scalar(
            select(ForumAnswer)
            .join(ForumQuestion, ForumQuestion.id == ForumAnswer.question_id)
            .where(
                ForumAnswer.id == answer_id,
                visible(ForumAnswer, viewer),
                visible(ForumQuestion, viewer),
            )
        )
        if answer is None:
            raise AppError("community.answer_not_found", 404)
        return answer

    async def accept(
        self, user: CurrentUser, question_id: uuid.UUID, answer_id: uuid.UUID | None
    ) -> None:
        question = await self._readable_question(user, question_id)
        if question.author_id != user.id:
            raise AppError("community.not_question_author", 403)
        if answer_id is not None:
            answer = await self._readable_answer(user, answer_id)
            if answer.question_id != question.id:
                raise AppError("community.answer_not_found", 404)
        question.accepted_answer_id = answer_id
        await self.session.commit()

    async def vote(self, user: CurrentUser, answer_id: uuid.UUID, value: int) -> None:
        answer = await self._readable_answer(user, answer_id)
        if answer.author_id == user.id:
            raise AppError("community.own_content", 422)
        await enforce_rate_limit(self.cache, REACTION_LIMIT, str(user.id))
        if value == 0:
            await self.session.execute(
                delete(ForumVote).where(
                    ForumVote.answer_id == answer_id, ForumVote.user_id == user.id
                )
            )
        else:
            await self.session.execute(
                insert(ForumVote)
                .values(answer_id=answer_id, user_id=user.id, value=value)
                .on_conflict_do_update(
                    index_elements=["answer_id", "user_id"], set_={"value": value}
                )
            )
        await self.session.commit()

    async def set_verified(self, user: CurrentUser, answer_id: uuid.UUID, verified: bool) -> None:
        answer = await self._readable_answer(user, answer_id)
        if not user.roles & VERIFIERS:
            raise AppError("community.not_verifier", 403)
        if answer.teacher_verified is verified:
            return
        answer.teacher_verified = verified
        answer.verified_by = user.id if verified else None
        await self.session.commit()

    async def promote(
        self,
        user: CurrentUser,
        channel_id: uuid.UUID,
        message_id: int,
        title: str,
        tag_ids: list[uuid.UUID],
    ) -> QuestionDetailOut:
        """Only the author of a visible, signed thread root may republish it, so nobody else's words, an anonymous
        question or held content reach the university-wide forum (§5.4, D-084, D-086, D-090)."""
        message = await find_message(self.session, message_id)
        member = await self.session.scalar(
            select(ChannelMember.user_id).where(
                ChannelMember.channel_id == channel_id, ChannelMember.user_id == user.id
            )
        )
        if (
            message is None
            or member is None
            or message.channel_id != channel_id
            or message.deleted_at is not None
        ):
            raise AppError("community.thread_not_found", 404)
        if (
            message.author_id != user.id
            or message.is_anonymous
            or message.parent_id is not None
            or message.moderation is not MessageModeration.VISIBLE
        ):
            raise AppError("community.promotion_not_allowed", 403)
        # Mention tokens name channel members by id; the forum is not the channel, so they are dropped.
        body = SPACES.sub(" ", USER_MENTION.sub("", message.body)).strip()
        if not body:
            raise AppError("community.promotion_not_allowed", 403)
        tags = await self._check_tags(tag_ids)
        await self._check_text(title, body)
        await enforce_rate_limit(self.cache, QUESTION_LIMIT, str(user.id))
        question = await self._add_question(user, title, body, tags, None)
        await self.session.commit()
        return await self.question(user, question.id)
