import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.chat.policy import Reason

# Ids are strings in JSON (§4.2): snowflakes exceed JavaScript's 53-bit integers.


class AuthorOut(BaseModel):
    id: str
    display_name: str
    photo_url: str | None


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
