"""The single chat authorisation function (ADR 0004): every REST endpoint, WebSocket event and composer banner
asks it, so the reason a user sees is the one that actually applies (§13.2). Pure: no I/O."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol


class Action(StrEnum):
    READ = "read"
    SEND = "send"
    SEND_ATTACHMENT = "send_attachment"
    REACT = "react"
    EDIT = "edit"
    DELETE = "delete"
    MENTION_CHANNEL = "mention_channel"


class Reason(StrEnum):
    NOT_MEMBER = "chat.not_member"
    ACCOUNT_INACTIVE = "chat.account_inactive"
    CHANNEL_ARCHIVED = "chat.channel_archived"
    EXAM_MODE = "chat.exam_mode"
    CHANNEL_READONLY = "chat.channel_readonly"
    USER_BLOCKED = "chat.user_blocked"
    """The sender blocked the other person of this DM."""
    DM_UNAVAILABLE = "chat.dm_unavailable"
    """The other person blocked the sender or accepts no messages; deliberately one code for both (§5.4)."""
    MUTED = "chat.muted"
    SLOW_MODE = "chat.slow_mode"
    RATE_LIMITED = "chat.rate_limited"
    # chat.attachments_not_allowed (new accounts in communities) joins with those restrictions in Sprint 10.
    CHANNEL_MENTION_NOT_ALLOWED = "chat.channel_mention_not_allowed"


# Exam mode, read-only channels and DM restrictions stop new content; deleting one's own message stays possible.
CONTENT = frozenset({Action.SEND, Action.SEND_ATTACHMENT, Action.REACT, Action.EDIT})
POSTING = frozenset({Action.SEND, Action.SEND_ATTACHMENT, Action.REACT})
NEW_MESSAGES = frozenset({Action.SEND, Action.SEND_ATTACHMENT})


@dataclass(frozen=True, slots=True)
class ExamWindow:
    channel_id: uuid.UUID
    starts_at: datetime
    """Already includes the 15 minutes before the exam (§5.2)."""
    ends_at: datetime


class ExamWindowProvider(Protocol):
    """Exam windows that cover ``at`` for the given channels, computed from persisted data at read time (D-059)."""

    async def windows(self, channel_ids: list[uuid.UUID], at: datetime) -> list[ExamWindow]: ...


class NoExamWindows:
    """Sprint 5 stub: exam slots arrive in Sprint 10, so no channel is ever in exam mode yet (D-059)."""

    async def windows(self, channel_ids: list[uuid.UUID], at: datetime) -> list[ExamWindow]:
        return []


@dataclass(frozen=True, slots=True)
class ChannelState:
    """Everything the decision depends on, for one user in one channel at ``now``."""

    now: datetime
    is_member: bool
    account_active: bool = True
    is_archived: bool = False
    is_readonly: bool = False
    member_readonly: bool = False
    exam_until: datetime | None = None
    user_blocked_peer: bool = False
    dm_unavailable: bool = False
    posting_muted_until: datetime | None = None
    slow_mode_seconds: int = 0
    slow_mode_exempt: bool = False
    slow_mode_retry_after: int | None = None
    """Seconds until the user may post again under slow mode, once the loader has claimed the slot."""
    rate_limit_retry_after: int | None = None
    can_mention_channel: bool = False


@dataclass(frozen=True, slots=True)
class Decision:
    allowed: bool
    reason: Reason | None = None
    until: datetime | None = None
    retry_after: int | None = None


ALLOW = Decision(allowed=True)


def authorize(action: Action, state: ChannelState) -> Decision:
    """The first matching reason wins (precedence in ADR 0004), so the user sees the most fundamental one."""
    if not state.is_member:
        return Decision(False, Reason.NOT_MEMBER)
    if action is Action.READ:
        return ALLOW
    if not state.account_active:
        return Decision(False, Reason.ACCOUNT_INACTIVE)
    if state.is_archived:
        return Decision(False, Reason.CHANNEL_ARCHIVED)
    # Exam mode applies to everyone in the channel, teachers included (D-057).
    if state.exam_until is not None and action in CONTENT:
        return Decision(False, Reason.EXAM_MODE, until=state.exam_until)
    if (state.is_readonly or state.member_readonly) and action in CONTENT:
        return Decision(False, Reason.CHANNEL_READONLY)
    if state.user_blocked_peer and action in CONTENT:
        return Decision(False, Reason.USER_BLOCKED)
    if state.dm_unavailable and action in CONTENT:
        return Decision(False, Reason.DM_UNAVAILABLE)
    muted = state.posting_muted_until
    if muted is not None and muted > state.now and action in POSTING:
        return Decision(False, Reason.MUTED, until=muted)
    if action in NEW_MESSAGES and not state.slow_mode_exempt and state.slow_mode_retry_after:
        return Decision(False, Reason.SLOW_MODE, retry_after=state.slow_mode_retry_after)
    if action in NEW_MESSAGES and state.rate_limit_retry_after:
        return Decision(False, Reason.RATE_LIMITED, retry_after=state.rate_limit_retry_after)
    if action is Action.MENTION_CHANNEL and not state.can_mention_channel:
        return Decision(False, Reason.CHANNEL_MENTION_NOT_ALLOWED)
    return ALLOW
