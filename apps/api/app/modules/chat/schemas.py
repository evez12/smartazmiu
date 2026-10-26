import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.modules.chat.models import ChannelType, NotifyLevel
from app.modules.chat.policy import Reason

# Ids are strings in JSON (§4.2): snowflakes exceed JavaScript's 53-bit integers.


Badge = Literal["teacher", "curator"]


class AuthorOut(BaseModel):
    id: str
    display_name: str
    photo_url: str | None
    badge: Badge | None = None
    """The person's role in this channel: the offering's teacher or the group's curator (§12.7)."""


class MessageOut(BaseModel):
    id: str
    channel_id: str
    topic_id: str | None
    parent_id: str | None
    author: AuthorOut | None
    """None once the author's account has been deleted ("Silinmiş istifadəçi", §13.2)."""
    body: str
    """Plain text; rendered escaped until Markdown arrives in Sprint 6."""
    client_msg_id: str
    created_at: datetime
    edited_at: datetime | None
    deleted_at: datetime | None


class PostingOut(BaseModel):
    """Whether the composer may send, and if not, why (ADR 0004); drives the banner above it (§12.7)."""

    allowed: bool
    reason: Reason | None = None
    until: datetime | None = None
    retry_after_seconds: int | None = None


class SendMessageIn(BaseModel):
    # Length is checked by the service, which answers with typed errors instead of a generic 422 (§5.9).
    body: str = Field(max_length=100_000)
    client_msg_id: uuid.UUID
    topic_id: uuid.UUID | None = None


class SendResultOut(BaseModel):
    message: MessageOut
    duplicate: bool
    """True when this client_msg_id was sent before: the original message is returned (§13.2)."""


class ReadMarkerIn(BaseModel):
    last_read_message_id: str = Field(pattern=r"^[0-9]{1,19}$")


class ReadMarkerOut(BaseModel):
    channel_id: str
    last_read_message_id: str


class TicketOut(BaseModel):
    ticket: str
    expires_at: datetime


class TopicOut(BaseModel):
    id: str
    slug: str
    name: str


class ChannelOut(BaseModel):
    id: str
    type: ChannelType
    name: str
    """For a DM, the other person's name."""
    context: str | None
    """Course channels: the offering's groups and semester, e.g. ``765a2 · 2026 Payız``."""
    peer: AuthorOut | None
    """The other person of a DM."""
    is_archived: bool
    is_readonly: bool
    notify_level: NotifyLevel
    muted_until: datetime | None
    """The member's own notification snooze; not a moderator mute."""
    unread_count: int
    """Messages by others after the read marker, counted up to 100 (shown as "99+")."""
    last_read_message_id: str | None
    posting: PostingOut


class ChannelListOut(BaseModel):
    channels: list[ChannelOut]
    blocked_user_ids: list[str]
    """People the user blocked: their messages are collapsed in shared channels (§13.2)."""


class ChannelDetailOut(ChannelOut):
    topics: list[TopicOut]


class MessagePageOut(BaseModel):
    messages: list[MessageOut]
    """Oldest first."""
    has_more: bool
    """More messages exist beyond this page in the direction it was read."""


class MembersOut(BaseModel):
    members: list[AuthorOut]


class OpenDmIn(BaseModel):
    user_id: uuid.UUID


class MembershipUpdateIn(BaseModel):
    notify_level: NotifyLevel | None = None
    muted_until: datetime | None = None
    """Snooze notifications until then; send null to end the snooze."""
