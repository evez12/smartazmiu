import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query
from fastapi import Path as FastPath

from app.core.deps import RedisDep, SessionDep
from app.core.errors import COMMON_ERROR_RESPONSES
from app.core.rbac import CurrentUserDep, require_permission
from app.modules.chat.lookup import MAX_MESSAGE_ID
from app.modules.community.schemas import (
    AcceptIn,
    AnswerCreate,
    CommentCreate,
    CommentOut,
    CommentPage,
    ContentKind,
    PostCreate,
    PostOut,
    PostPage,
    PromotionIn,
    QuestionCreate,
    QuestionDetailOut,
    QuestionPage,
    TagListOut,
    VisibilityIn,
)
from app.modules.community.service import MODERATE, CommunityService
from app.modules.users.service import CurrentUser

router = APIRouter(tags=["community"], responses=COMMON_ERROR_RESPONSES)
Moderator = Annotated[CurrentUser, Depends(require_permission(MODERATE))]
IdempotencyKey = Annotated[
    str | None,
    Header(
        alias="Idempotency-Key", max_length=100, description="Repeating it returns the first result"
    ),
]
Cursor = Annotated[str | None, Query(max_length=200)]
TagSlug = Annotated[str | None, Query(max_length=80)]


def get_community(session: SessionDep, cache: RedisDep) -> CommunityService:
    return CommunityService(session, cache)


CommunityDep = Annotated[CommunityService, Depends(get_community)]


@router.get("/community/tags", response_model=TagListOut, operation_id="listCommunityTags")
async def list_tags(user: CurrentUserDep, community: CommunityDep) -> TagListOut:
    return TagListOut(items=await community.tags())


@router.get("/feed/posts", response_model=PostPage, operation_id="listFeedPosts")
async def list_posts(
    user: CurrentUserDep, community: CommunityDep, cursor: Cursor = None, tag: TagSlug = None
) -> PostPage:
    return await community.posts(user, cursor, tag)


@router.post("/feed/posts", response_model=PostOut, status_code=201, operation_id="createFeedPost")
async def create_post(
    user: CurrentUserDep,
    community: CommunityDep,
    body: PostCreate,
    idempotency_key: IdempotencyKey = None,
) -> PostOut:
    return await community.create_post(user, body, idempotency_key)


@router.delete("/feed/posts/{post_id}", status_code=204, operation_id="deleteFeedPost")
async def delete_post(user: CurrentUserDep, community: CommunityDep, post_id: uuid.UUID) -> None:
    await community.delete_own(user, "post", post_id)


@router.get(
    "/feed/posts/{post_id}/comments", response_model=CommentPage, operation_id="listFeedComments"
)
async def list_comments(
    user: CurrentUserDep, community: CommunityDep, post_id: uuid.UUID, after: Cursor = None
) -> CommentPage:
    return await community.comments(user, post_id, after)


@router.post(
    "/feed/posts/{post_id}/comments",
    response_model=CommentOut,
    status_code=201,
    operation_id="createFeedComment",
)
async def create_comment(
    user: CurrentUserDep,
    community: CommunityDep,
    post_id: uuid.UUID,
    body: CommentCreate,
    idempotency_key: IdempotencyKey = None,
) -> CommentOut:
    return await community.comment(user, post_id, body, idempotency_key)


@router.delete("/feed/comments/{comment_id}", status_code=204, operation_id="deleteFeedComment")
async def delete_comment(
    user: CurrentUserDep, community: CommunityDep, comment_id: uuid.UUID
) -> None:
    await community.delete_own(user, "comment", comment_id)


@router.put("/feed/posts/{post_id}/helpful", status_code=204, operation_id="markPostHelpful")
async def mark_helpful(user: CurrentUserDep, community: CommunityDep, post_id: uuid.UUID) -> None:
    await community.set_helpful(user, post_id, True)


@router.delete("/feed/posts/{post_id}/helpful", status_code=204, operation_id="unmarkPostHelpful")
async def unmark_helpful(user: CurrentUserDep, community: CommunityDep, post_id: uuid.UUID) -> None:
    await community.set_helpful(user, post_id, False)


@router.get("/forum/questions", response_model=QuestionPage, operation_id="listForumQuestions")
async def list_questions(
    user: CurrentUserDep, community: CommunityDep, cursor: Cursor = None, tag: TagSlug = None
) -> QuestionPage:
    return await community.questions(user, cursor, tag)


@router.post(
    "/forum/questions",
    response_model=QuestionDetailOut,
    status_code=201,
    operation_id="createForumQuestion",
)
async def create_question(
    user: CurrentUserDep,
    community: CommunityDep,
    body: QuestionCreate,
    idempotency_key: IdempotencyKey = None,
) -> QuestionDetailOut:
    return await community.create_question(user, body, idempotency_key)


@router.get(
    "/forum/questions/{question_id}",
    response_model=QuestionDetailOut,
    operation_id="getForumQuestion",
)
async def get_question(
    user: CurrentUserDep, community: CommunityDep, question_id: uuid.UUID
) -> QuestionDetailOut:
    return await community.question(user, question_id)


@router.delete(
    "/forum/questions/{question_id}", status_code=204, operation_id="deleteForumQuestion"
)
async def delete_question(
    user: CurrentUserDep, community: CommunityDep, question_id: uuid.UUID
) -> None:
    await community.delete_own(user, "question", question_id)


@router.post(
    "/forum/questions/{question_id}/answers",
    response_model=QuestionDetailOut,
    status_code=201,
    operation_id="createForumAnswer",
)
async def create_answer(
    user: CurrentUserDep,
    community: CommunityDep,
    question_id: uuid.UUID,
    body: AnswerCreate,
    idempotency_key: IdempotencyKey = None,
) -> QuestionDetailOut:
    return await community.answer(user, question_id, body, idempotency_key)


@router.delete("/forum/answers/{answer_id}", status_code=204, operation_id="deleteForumAnswer")
async def delete_answer(
    user: CurrentUserDep, community: CommunityDep, answer_id: uuid.UUID
) -> None:
    await community.delete_own(user, "answer", answer_id)


@router.put(
    "/forum/questions/{question_id}/accepted-answer",
    status_code=204,
    operation_id="setAcceptedAnswer",
)
async def set_accepted(
    user: CurrentUserDep, community: CommunityDep, question_id: uuid.UUID, body: AcceptIn
) -> None:
    await community.accept(user, question_id, body.answer_id)


@router.put("/forum/answers/{answer_id}/vote", status_code=204, operation_id="voteForumAnswer")
async def vote(
    user: CurrentUserDep,
    community: CommunityDep,
    answer_id: uuid.UUID,
    value: Annotated[int, Query(ge=-1, le=1)],
) -> None:
    await community.vote(user, answer_id, value)


@router.put(
    "/forum/answers/{answer_id}/verification", status_code=204, operation_id="verifyForumAnswer"
)
async def verify(user: CurrentUserDep, community: CommunityDep, answer_id: uuid.UUID) -> None:
    await community.set_verified(user, answer_id, True)


@router.delete(
    "/forum/answers/{answer_id}/verification",
    status_code=204,
    operation_id="unverifyForumAnswer",
)
async def unverify(user: CurrentUserDep, community: CommunityDep, answer_id: uuid.UUID) -> None:
    await community.set_verified(user, answer_id, False)


@router.put(
    "/community/{kind}/{item_id}/visibility",
    status_code=204,
    operation_id="setCommunityVisibility",
)
async def set_visibility(
    actor: Moderator,
    community: CommunityDep,
    kind: ContentKind,
    item_id: uuid.UUID,
    body: VisibilityIn,
) -> None:
    await community.set_hidden(actor, kind, item_id, body.hidden)


@router.post(
    "/chat/channels/{channel_id}/messages/{message_id}/promote",
    response_model=QuestionDetailOut,
    status_code=201,
    operation_id="promoteMessageToForum",
)
async def promote(
    user: CurrentUserDep,
    community: CommunityDep,
    channel_id: uuid.UUID,
    message_id: Annotated[int, FastPath(gt=0, le=MAX_MESSAGE_ID)],
    body: PromotionIn,
) -> QuestionDetailOut:
    return await community.promote(user, channel_id, message_id, body.title, body.tag_ids)
