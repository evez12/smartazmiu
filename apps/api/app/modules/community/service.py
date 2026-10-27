import base64
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.modules.chat.models import ChannelMember, Message
from app.modules.community.models import (
    CommunityReport,
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
    CommunityReportIn,
    PostCreate,
    PostOut,
    QuestionCreate,
    QuestionDetailOut,
    QuestionOut,
)
from app.modules.users.service import CurrentUser


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


class CommunityService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _tag_names(
        self, link_model: type[Any], parent_column: Any, parent_id: uuid.UUID
    ) -> list[str]:
        rows = await self.session.scalars(
            select(CommunityTag.name)
            .join(link_model, link_model.tag_id == CommunityTag.id)
            .where(parent_column == parent_id)
            .order_by(CommunityTag.name)
        )
        return list(rows.all())

    async def posts(self, cursor: str | None, limit: int) -> tuple[list[PostOut], str | None]:
        marker = _decode(cursor)
        query = (
            select(FeedPost)
            .where(FeedPost.deleted_at.is_(None))
            .order_by(FeedPost.created_at.desc(), FeedPost.id.desc())
            .limit(limit + 1)
        )
        if marker:
            created, item_id = marker
            query = query.where(
                (FeedPost.created_at < created)
                | ((FeedPost.created_at == created) & (FeedPost.id < item_id))
            )
        rows = list((await self.session.scalars(query)).all())
        more = len(rows) > limit
        rows = rows[:limit]
        result = []
        for post in rows:
            helpful = await self.session.scalar(
                select(func.count())
                .select_from(HelpfulReaction)
                .where(HelpfulReaction.post_id == post.id)
            )
            comments = await self.session.scalar(
                select(func.count())
                .select_from(FeedComment)
                .where(FeedComment.post_id == post.id, FeedComment.deleted_at.is_(None))
            )
            result.append(
                PostOut.model_validate(post, from_attributes=True).model_copy(
                    update={
                        "helpful_count": helpful or 0,
                        "comment_count": comments or 0,
                        "tags": await self._tag_names(FeedPostTag, FeedPostTag.post_id, post.id),
                    }
                )
            )
        return result, (_cursor(rows[-1].created_at, rows[-1].id) if more and rows else None)

    async def create_post(self, user: CurrentUser, body: PostCreate) -> PostOut:
        post = FeedPost(author_id=user.id, body=body.body.strip())
        self.session.add(post)
        await self.session.flush()
        self.session.add_all([FeedPostTag(post_id=post.id, tag_id=tag) for tag in body.tag_ids])
        await self.session.commit()
        return PostOut.model_validate(post, from_attributes=True).model_copy(
            update={"tags": await self._tag_names(FeedPostTag, FeedPostTag.post_id, post.id)}
        )

    async def comment(
        self, user: CurrentUser, post_id: uuid.UUID, body: CommentCreate
    ) -> CommentOut:
        post = await self.session.scalar(
            select(FeedPost).where(FeedPost.id == post_id, FeedPost.deleted_at.is_(None))
        )
        if post is None:
            raise AppError("community.post_not_found", 404)
        comment = FeedComment(post_id=post_id, author_id=user.id, body=body.body.strip())
        self.session.add(comment)
        await self.session.commit()
        return CommentOut.model_validate(comment, from_attributes=True)

    async def react(self, user: CurrentUser, post_id: uuid.UUID, active: bool) -> None:
        if not await self.session.scalar(
            select(FeedPost.id).where(FeedPost.id == post_id, FeedPost.deleted_at.is_(None))
        ):
            raise AppError("community.post_not_found", 404)
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

    async def report(
        self, user: CurrentUser, target_type: str, target_id: uuid.UUID, body: CommunityReportIn
    ) -> None:
        if target_type not in {"post", "comment", "question", "answer"}:
            raise AppError("community.invalid_target", 422)
        report = CommunityReport(
            reporter_id=user.id,
            target_type=target_type,
            target_id=target_id,
            reason=body.reason,
            details=body.details,
        )
        self.session.add(report)
        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            # Repeated reports are intentionally idempotent.

    async def question_detail(self, question_id: uuid.UUID) -> QuestionDetailOut:
        question = await self.session.scalar(
            select(ForumQuestion).where(
                ForumQuestion.id == question_id, ForumQuestion.deleted_at.is_(None)
            )
        )
        if question is None:
            raise AppError("community.question_not_found", 404)
        answers = list(
            (
                await self.session.scalars(
                    select(ForumAnswer)
                    .where(
                        ForumAnswer.question_id == question_id,
                        ForumAnswer.deleted_at.is_(None),
                    )
                    .order_by(ForumAnswer.created_at.asc(), ForumAnswer.id.asc())
                )
            ).all()
        )
        answer_ids = [answer.id for answer in answers]
        scores: dict[uuid.UUID, int] = {}
        if answer_ids:
            score_rows = await self.session.execute(
                select(ForumVote.answer_id, func.coalesce(func.sum(ForumVote.value), 0))
                .where(ForumVote.answer_id.in_(answer_ids))
                .group_by(ForumVote.answer_id)
            )
            scores = {answer_id: int(score) for answer_id, score in score_rows}
        return QuestionDetailOut(
            **(await self._question_out(question)).model_dump(),
            answers=[
                AnswerOut.model_validate(answer, from_attributes=True).model_copy(
                    update={"score": scores.get(answer.id, 0)}
                )
                for answer in answers
            ],
        )

    async def _question_out(self, question: ForumQuestion) -> QuestionOut:
        verified = bool(
            await self.session.scalar(
                select(ForumAnswer.id).where(
                    ForumAnswer.question_id == question.id,
                    ForumAnswer.teacher_verified.is_(True),
                    ForumAnswer.deleted_at.is_(None),
                )
            )
        )
        return QuestionOut.model_validate(question, from_attributes=True).model_copy(
            update={
                "tags": await self._tag_names(
                    ForumQuestionTag, ForumQuestionTag.question_id, question.id
                ),
                "teacher_verified": verified,
            }
        )

    async def questions(
        self, cursor: str | None, limit: int
    ) -> tuple[list[QuestionOut], str | None]:
        marker = _decode(cursor)
        query = (
            select(ForumQuestion)
            .where(ForumQuestion.deleted_at.is_(None))
            .order_by(ForumQuestion.created_at.desc(), ForumQuestion.id.desc())
            .limit(limit + 1)
        )
        if marker:
            created, item_id = marker
            query = query.where(
                (ForumQuestion.created_at < created)
                | ((ForumQuestion.created_at == created) & (ForumQuestion.id < item_id))
            )
        rows = list((await self.session.scalars(query)).all())
        more = len(rows) > limit
        rows = rows[:limit]
        return [
            (
                QuestionOut.model_validate(row, from_attributes=True).model_copy(
                    update={
                        "tags": await self._tag_names(
                            ForumQuestionTag, ForumQuestionTag.question_id, row.id
                        )
                    }
                )
            )
            for row in rows
        ], (_cursor(rows[-1].created_at, rows[-1].id) if more and rows else None)

    async def tag_questions(self, tag_id: uuid.UUID, limit: int) -> list[QuestionOut]:
        rows = await self.session.scalars(
            select(ForumQuestion)
            .join(ForumQuestionTag, ForumQuestionTag.question_id == ForumQuestion.id)
            .where(ForumQuestionTag.tag_id == tag_id, ForumQuestion.deleted_at.is_(None))
            .order_by(ForumQuestion.created_at.desc())
            .limit(limit)
        )
        return [
            QuestionOut.model_validate(row, from_attributes=True).model_copy(
                update={
                    "tags": await self._tag_names(
                        ForumQuestionTag, ForumQuestionTag.question_id, row.id
                    )
                }
            )
            for row in rows
        ]

    async def questions_for_tag_slug(self, slug: str, limit: int) -> list[QuestionOut]:
        tag = await self.session.scalar(select(CommunityTag).where(CommunityTag.slug == slug))
        if tag is None:
            return []
        return await self.tag_questions(tag.id, limit)

    async def tag_posts(self, tag_id: uuid.UUID, limit: int) -> list[PostOut]:
        rows = await self.session.scalars(
            select(FeedPost)
            .join(FeedPostTag, FeedPostTag.post_id == FeedPost.id)
            .where(FeedPostTag.tag_id == tag_id, FeedPost.deleted_at.is_(None))
            .order_by(FeedPost.created_at.desc())
            .limit(limit)
        )
        return [
            PostOut.model_validate(row, from_attributes=True).model_copy(
                update={"tags": await self._tag_names(FeedPostTag, FeedPostTag.post_id, row.id)}
            )
            for row in rows
        ]

    async def create_question(self, user: CurrentUser, body: QuestionCreate) -> QuestionOut:
        question = ForumQuestion(
            author_id=user.id, title=body.title.strip(), body=body.body.strip()
        )
        self.session.add(question)
        await self.session.flush()
        self.session.add_all(
            [ForumQuestionTag(question_id=question.id, tag_id=tag) for tag in body.tag_ids]
        )
        await self.session.commit()
        return QuestionOut.model_validate(question, from_attributes=True).model_copy(
            update={
                "tags": await self._tag_names(
                    ForumQuestionTag, ForumQuestionTag.question_id, question.id
                )
            }
        )

    async def answer(
        self, user: CurrentUser, question_id: uuid.UUID, body: AnswerCreate
    ) -> AnswerOut:
        if not await self.session.scalar(
            select(ForumQuestion.id).where(
                ForumQuestion.id == question_id, ForumQuestion.deleted_at.is_(None)
            )
        ):
            raise AppError("community.question_not_found", 404)
        answer = ForumAnswer(question_id=question_id, author_id=user.id, body=body.body.strip())
        self.session.add(answer)
        await self.session.commit()
        return AnswerOut.model_validate(answer, from_attributes=True).model_copy(
            update={"score": 0}
        )

    async def accept(self, user: CurrentUser, question_id: uuid.UUID, answer_id: uuid.UUID) -> None:
        question = await self.session.scalar(
            select(ForumQuestion).where(
                ForumQuestion.id == question_id, ForumQuestion.deleted_at.is_(None)
            )
        )
        answer = await self.session.scalar(
            select(ForumAnswer).where(
                ForumAnswer.id == answer_id,
                ForumAnswer.question_id == question_id,
                ForumAnswer.deleted_at.is_(None),
            )
        )
        if question is None or answer is None:
            raise AppError("community.answer_not_found", 404)
        if question.author_id != user.id:
            raise AppError("auth.forbidden", 403)
        question.accepted_answer_id = answer.id
        await self.session.commit()

    async def vote(self, user: CurrentUser, answer_id: uuid.UUID, value: int) -> None:
        if value not in {-1, 1}:
            raise AppError("community.invalid_vote", 422)
        if not await self.session.scalar(
            select(ForumAnswer.id).where(
                ForumAnswer.id == answer_id, ForumAnswer.deleted_at.is_(None)
            )
        ):
            raise AppError("community.answer_not_found", 404)
        await self.session.execute(
            insert(ForumVote)
            .values(answer_id=answer_id, user_id=user.id, value=value)
            .on_conflict_do_update(index_elements=["answer_id", "user_id"], set_={"value": value})
        )
        await self.session.commit()

    async def verify_answer(self, user: CurrentUser, answer_id: uuid.UUID) -> None:
        if "teacher" not in user.roles and not user.has_permission("forum.verify"):
            raise AppError("auth.forbidden", 403)
        answer = await self.session.get(ForumAnswer, answer_id)
        if answer is None or answer.deleted_at is not None:
            raise AppError("community.answer_not_found", 404)
        answer.teacher_verified, answer.verified_by = True, user.id
        await self.session.commit()

    async def promote_thread(
        self,
        user: CurrentUser,
        channel_id: uuid.UUID,
        message_id: int,
        title: str,
        tag_ids: list[uuid.UUID],
    ) -> QuestionOut:
        member = await self.session.scalar(
            select(ChannelMember).where(
                ChannelMember.channel_id == channel_id, ChannelMember.user_id == user.id
            )
        )
        message = await self.session.scalar(
            select(Message).where(
                Message.channel_id == channel_id,
                Message.id == message_id,
                Message.deleted_at.is_(None),
            )
        )
        if member is None or message is None:
            raise AppError("community.thread_not_found", 404)
        question = ForumQuestion(author_id=user.id, title=title.strip(), body=message.body)
        self.session.add(question)
        await self.session.flush()
        self.session.add_all(
            [ForumQuestionTag(question_id=question.id, tag_id=tag) for tag in tag_ids]
        )
        await self.session.commit()
        return await self._question_out(question)
