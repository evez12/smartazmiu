import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.deps import SessionDep
from app.core.errors import COMMON_ERROR_RESPONSES
from app.core.rbac import CurrentUserDep
from app.modules.community.schemas import (
    AnswerCreate,
    AnswerOut,
    CommentCreate,
    CommentOut,
    CommunityReportIn,
    PostCreate,
    PostOut,
    PostPage,
    PromotionIn,
    QuestionCreate,
    QuestionDetailOut,
    QuestionOut,
    QuestionPage,
)
from app.modules.community.service import CommunityService

router = APIRouter(tags=["community"], responses=COMMON_ERROR_RESPONSES)


def dep(session: SessionDep) -> CommunityService:
    return CommunityService(session)


ServiceDep = Annotated[CommunityService, Depends(dep)]


@router.get("/feed/posts", response_model=PostPage)
async def list_posts(
    _: CurrentUserDep,
    service: ServiceDep,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 25,
) -> PostPage:
    items, next_cursor = await service.posts(cursor, limit)
    return PostPage(items=items, next_cursor=next_cursor)


@router.post("/feed/posts", response_model=PostOut, status_code=201)
async def create_post(user: CurrentUserDep, service: ServiceDep, body: PostCreate) -> PostOut:
    return await service.create_post(user, body)


@router.post("/feed/posts/{post_id}/comments", response_model=CommentOut, status_code=201)
async def comment(
    user: CurrentUserDep, service: ServiceDep, post_id: uuid.UUID, body: CommentCreate
) -> CommentOut:
    return await service.comment(user, post_id, body)


@router.put("/feed/posts/{post_id}/helpful", status_code=204)
async def helpful(user: CurrentUserDep, service: ServiceDep, post_id: uuid.UUID) -> None:
    await service.react(user, post_id, True)


@router.delete("/feed/posts/{post_id}/helpful", status_code=204)
async def unhelpful(user: CurrentUserDep, service: ServiceDep, post_id: uuid.UUID) -> None:
    await service.react(user, post_id, False)


@router.post("/community/{target_type}/{target_id}/reports", status_code=204)
async def report(
    user: CurrentUserDep,
    service: ServiceDep,
    target_type: str,
    target_id: uuid.UUID,
    body: CommunityReportIn,
) -> None:
    await service.report(user, target_type, target_id, body)


@router.get("/forum/questions", response_model=QuestionPage)
async def list_questions(
    _: CurrentUserDep,
    service: ServiceDep,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 25,
) -> QuestionPage:
    items, next_cursor = await service.questions(cursor, limit)
    return QuestionPage(items=items, next_cursor=next_cursor)


@router.get("/community/tags/{tag_id}/posts", response_model=list[PostOut])
async def tag_posts(
    _: CurrentUserDep,
    service: ServiceDep,
    tag_id: uuid.UUID,
    limit: Annotated[int, Query(ge=1, le=50)] = 25,
) -> list[PostOut]:
    return await service.tag_posts(tag_id, limit)


@router.get("/community/tags/{tag_id}/questions", response_model=list[QuestionOut])
async def tag_questions(
    _: CurrentUserDep,
    service: ServiceDep,
    tag_id: uuid.UUID,
    limit: Annotated[int, Query(ge=1, le=50)] = 25,
) -> list[QuestionOut]:
    return await service.tag_questions(tag_id, limit)


@router.get("/forum/tags/{tag_slug}", response_model=QuestionPage)
async def tag_questions_by_slug(
    _: CurrentUserDep,
    service: ServiceDep,
    tag_slug: str,
    limit: Annotated[int, Query(ge=1, le=50)] = 25,
) -> QuestionPage:
    return QuestionPage(items=await service.questions_for_tag_slug(tag_slug, limit))


@router.post("/forum/questions", response_model=QuestionOut, status_code=201)
async def create_question(
    user: CurrentUserDep, service: ServiceDep, body: QuestionCreate
) -> QuestionOut:
    return await service.create_question(user, body)


@router.get("/forum/questions/{question_id}", response_model=QuestionDetailOut)
async def question_detail(
    _: CurrentUserDep, service: ServiceDep, question_id: uuid.UUID
) -> QuestionDetailOut:
    return await service.question_detail(question_id)


@router.post("/forum/questions/{question_id}/answers", response_model=AnswerOut, status_code=201)
async def answer(
    user: CurrentUserDep, service: ServiceDep, question_id: uuid.UUID, body: AnswerCreate
) -> AnswerOut:
    return await service.answer(user, question_id, body)


@router.post("/forum/questions/{question_id}/accept/{answer_id}", status_code=204)
async def accept(
    user: CurrentUserDep, service: ServiceDep, question_id: uuid.UUID, answer_id: uuid.UUID
) -> None:
    await service.accept(user, question_id, answer_id)


@router.put("/forum/answers/{answer_id}/vote", status_code=204)
async def vote(
    user: CurrentUserDep,
    service: ServiceDep,
    answer_id: uuid.UUID,
    value: Annotated[int, Query(ge=-1, le=1)],
) -> None:
    await service.vote(user, answer_id, value)


@router.post("/forum/answers/{answer_id}/verify", status_code=204)
async def verify(user: CurrentUserDep, service: ServiceDep, answer_id: uuid.UUID) -> None:
    await service.verify_answer(user, answer_id)


@router.post(
    "/chat/channels/{channel_id}/messages/{message_id}/promote",
    response_model=QuestionOut,
    status_code=201,
)
async def promote(
    user: CurrentUserDep,
    service: ServiceDep,
    channel_id: uuid.UUID,
    message_id: int,
    body: PromotionIn,
) -> QuestionOut:
    return await service.promote_thread(user, channel_id, message_id, body.title, body.tag_ids)
