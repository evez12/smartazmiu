from pydantic import BaseModel, ConfigDict, Field

from app.modules.audiences.service import AudienceType


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class AudienceIn(_Frozen):
    type: AudienceType
    target_id: str | None = None
    """Faculty, specialty, group or course offering id; omitted for the whole university."""


class AudienceOut(_Frozen):
    type: AudienceType
    target_id: str | None
    label: str | None
    """Name of the target (null for the university)."""
    detail: str | None


class AudienceOptionOut(_Frozen):
    id: str
    label: str
    detail: str


class AudienceOptionsOut(_Frozen):
    items: list[AudienceOptionOut] = Field(description="At most 50, by name")
