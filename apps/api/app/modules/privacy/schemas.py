from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.privacy.models import ConsentPurpose


class ConsentRecordOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    purpose: ConsentPurpose
    granted: bool
    policy_version: str | None
    recorded_at: datetime


class MyConsentsOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    notice_version: str
    """Current version of the privacy notice."""
    notice_acknowledged_at: datetime | None
    """When the user acknowledged the current version; null until they do."""
    history: list[ConsentRecordOut]
    """Newest first."""


class NoticeAcknowledgement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = Field(max_length=20)
