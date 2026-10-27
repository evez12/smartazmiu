import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.chat.models import ChannelType, MessageModeration, NotifyLevel, ScanStatus
from app.modules.chat.policy import Reason

# Ids are strings in JSON (§4.2): snowflakes exceed JavaScript's 53-bit integers.


Badge = Literal["teacher", "curator", "guide"]


class AuthorOut(BaseModel):
    id: str
    display_name: str
    photo_url: str | None
    badge: Badge | None = None
    """The person's role in this channel: the offering's teacher, the group's curator (§12.7) or a guide of the
    community's subject (§5.2)."""
    guide_semester: str | None = None
    """For guides: the semester they passed the subject in, e.g. "2025 Payız"; never the grade."""


class ReactionOut(BaseModel):
    emoji: str
    count: int


class MentionOut(BaseModel):
    """A channel member named in the message; anyone else stays plain text (§13.2)."""

    id: str
    display_name: str


class AttachmentOut(BaseModel):
    id: str
    filename: str
    mime: str
    size_bytes: int
    width: int | None
    height: int | None
    status: ScanStatus
    """Only the uploader ever sees anything but ``clean`` (D-068)."""
    previewable: bool


class PollOptionOut(BaseModel):
    id: str
    text: str
    votes: int


class PollOut(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)

    id: str
    multi: bool
    closes_at: datetime | None
    closed: bool
    options: list[PollOptionOut]
    voters: int
    my_votes: list[str] | None = None
    """The reader's own choices; None in broadcast events."""


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
    moderation: MessageModeration = MessageModeration.VISIBLE
    is_verified_answer: bool = False
    verified_by_name: str | None = None
    """Who confirmed the answer: the course teacher or a guide of the subject (§5.3)."""
    is_anonymous: bool = False
    """An anonymous #suallar question: ``author`` is None for everyone, shown as "Anonim" (§5.3)."""
    pinned: bool = False
    """In the channel's "Faydalı" collection."""
    saved: bool | None = None
    """Saved by the reader; None in broadcast events."""
    poll: PollOut | None = None
    reply_count: int = 0
    """Replies in the message's thread that are not deleted (top-level messages only)."""
    last_reply_at: datetime | None = None
    reactions: list[ReactionOut] = Field(default_factory=list)
    """Counts per emoji, in the order of the fixed set (D-067)."""
    my_reactions: list[str] | None = None
    """The reader's own reactions; None in broadcast events, which every member receives alike."""
    mentions: list[MentionOut] = Field(default_factory=list)
    mentions_channel: bool = False
    attachments: list[AttachmentOut] = Field(default_factory=list)
    """Clean attachments; the uploader also sees their own that are being scanned or were rejected."""


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
    attachment_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)
    """Uploads from ``POST /chat/attachments/presign``; the body may be empty when there are some."""
    is_anonymous: bool = False
    """Only for new questions in #suallar of course and community channels (§5.3)."""


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
    can_pin: bool = False
    """May add to and remove from the channel's "Faydalı" collection."""
    can_verify: bool = False
    """May mark answers as verified: the course's teacher or a guide of the community's subject (§5.3)."""
    can_see_anonymous: bool = False
    """May look up who asked an anonymous question (moderators, teachers, staff; audited)."""
    subject_id: str | None = None
    """Course and community channels: their subject, for links to materials and guides (§5.1)."""


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


class PresignIn(BaseModel):
    channel_id: uuid.UUID
    filename: str = Field(min_length=1, max_length=255)
    mime: str = Field(min_length=1, max_length=127)
    size: int = Field(ge=1)


class PresignOut(BaseModel):
    attachment_id: str
    url: str
    """PUT the file here with the same ``Content-Type`` header before the link expires."""
    object_key: str
    expires_at: datetime
    headers: dict[str, str]


class DownloadOut(BaseModel):
    url: str
    expires_at: datetime


class PinsOut(BaseModel):
    messages: list[MessageOut]


class PollIn(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    client_msg_id: uuid.UUID
    topic_id: uuid.UUID | None = None
    options: list[str] = Field(min_length=2, max_length=10)
    multi: bool = False
    closes_at: datetime | None = None


class VoteIn(BaseModel):
    option_ids: list[uuid.UUID] = Field(min_length=1, max_length=10)


class SavedItemOut(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)

    message_id: str
    channel_id: str
    channel_name: str | None
    saved_at: datetime
    message: MessageOut | None
    """None when the message was deleted or the channel is no longer readable; then nothing else is shown."""


class SavedListOut(BaseModel):
    items: list[SavedItemOut]
