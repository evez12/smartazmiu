import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

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


class ReactionOut(BaseModel):
    emoji: str
    count: int


class MentionOut(BaseModel):
    """A channel member named in the message; anyone else stays plain text (§13.2)."""

    id: str
    display_name: str


class MessageOut(BaseModel):
    # Every field is always present in responses, so the generated client needs no optional checks.
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)

    id: str
    channel_id: str
    topic_id: str | None
    parent_id: str | None
    author: AuthorOut | None
    """None once the author's account has been deleted ("Silinmiş istifadəçi", §13.2)."""
    body: str
    """The raw text the author wrote (Markdown, ``<@user-id>`` mentions); empty once deleted."""
    client_msg_id: str
    created_at: datetime
    edited_at: datetime | None
    deleted_at: datetime | None
    is_verified_answer: bool = False
    reply_count: int = 0
    """Replies in the message's thread that are not deleted (top-level messages only)."""
    last_reply_at: datetime | None = None
    reactions: list[ReactionOut] = Field(default_factory=list)
    """Counts per emoji, in the order of the fixed set (D-067)."""
    my_reactions: list[str] | None = None
    """The reader's own reactions; None in broadcast events, which every member receives alike."""
    mentions: list[MentionOut] = Field(default_factory=list)
    mentions_channel: bool = False


class PostingOut(BaseModel):
    """Whether the composer may send, and if not, why (ADR 0004); drives the banner above it (§12.7)."""

    allowed: bool
    reason: Reason | None = None
    until: datetime | None = None
    retry_after_seconds: int | None = None


MESSAGE_ID_PATTERN = r"^[0-9]{1,19}$"


class SendMessageIn(BaseModel):
    # Length is checked by the service, which answers with typed errors instead of a generic 422 (§5.9).
    body: str = Field(max_length=100_000)
    client_msg_id: uuid.UUID
    topic_id: uuid.UUID | None = None
    parent_id: str | None = Field(default=None, pattern=MESSAGE_ID_PATTERN)
    """Reply in this message's thread; a reply to a reply joins the same thread (one level, D-067)."""


Notice = Literal["chat.channel_mention_not_allowed"]


class SendResultOut(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)

    message: MessageOut
    duplicate: bool
    """True when this client_msg_id was sent before: the original message is returned (§13.2)."""
    notices: list[Notice] = Field(default_factory=list)
    """Things the author should know although the message was sent, e.g. an ignored @channel."""


class EditMessageIn(BaseModel):
    body: str = Field(max_length=100_000)


class EditResultOut(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)

    message: MessageOut
    notices: list[Notice] = Field(default_factory=list)


class ReactionIn(BaseModel):
    emoji: str = Field(max_length=32)


class ReactionResultOut(BaseModel):
    message_id: str
    emoji: str
    count: int
    reacted: bool
    """Whether the reader's reaction is now present."""


class ThreadOut(BaseModel):
    root: MessageOut
    """Shown as "silinmiş mesaj" when deleted; its replies stay (§13.2)."""
    replies: list[MessageOut]
    """Oldest first."""
    has_more: bool


class ReadMarkerIn(BaseModel):
    last_read_message_id: str = Field(pattern=MESSAGE_ID_PATTERN)


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
    """Top-level messages by others after the read marker, counted up to 100 (shown as "99+")."""
    mention_count: int
    """Unread messages by others that mention the reader or use @channel, counted up to 100."""
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
