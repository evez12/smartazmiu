import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.chat.models import ScanStatus
from app.modules.materials.models import MaterialReportReason, MaterialReportStatus, MaterialType


class PersonOut(BaseModel):
    id: str
    display_name: str


class SemesterOut(BaseModel):
    id: str
    label: str
    can_upload: bool


class VersionOut(BaseModel):
    id: str
    version: int
    filename: str
    mime: str
    size_bytes: int
    note: str
    status: ScanStatus
    previewable: bool
    uploaded_by: PersonOut | None
    created_at: datetime


class MaterialOut(BaseModel):
    id: str
    subject_id: str
    semester: SemesterOut
    type: MaterialType
    title: str
    description: str
    created_by: PersonOut | None
    created_at: datetime
    current: VersionOut | None
    """The newest clean version; null while the first upload is still being checked."""
    version_count: int
    """How many clean versions exist."""
    scanning: bool
    """A newer upload is still being checked (shown to people who can edit only)."""
    hidden: bool
    can_edit: bool


class MaterialDetailOut(MaterialOut):
    subject_name: str
    versions: list[VersionOut]
    """Newest first. Others see clean versions only; uploaders and editors also see checks and rejections."""


class MaterialSubjectOut(BaseModel):
    id: str
    code: str
    name: str
    materials: int


class MaterialSubjectListOut(BaseModel):
    items: list[MaterialSubjectOut]


class SubjectCatalogOut(BaseModel):
    subject_id: str
    subject_code: str
    subject_name: str
    semesters: list[SemesterOut]
    can_upload: bool
    can_manage: bool
    materials: list[MaterialOut]


class MaterialPresignIn(BaseModel):
    subject_id: uuid.UUID
    semester_id: uuid.UUID
    filename: str = Field(min_length=1, max_length=255)
    mime: str = Field(min_length=1, max_length=127)
    size: int = Field(ge=1)


class MaterialPresignOut(BaseModel):
    upload_id: str
    url: str
    """PUT the file here with the given headers before the link expires."""
    object_key: str
    expires_at: datetime
    headers: dict[str, str]


class MaterialCreateIn(BaseModel):
    upload_id: uuid.UUID
    type: MaterialType
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    copyright_confirmed: bool


class VersionCreateIn(BaseModel):
    upload_id: uuid.UUID
    note: str = Field(default="", max_length=300)
    copyright_confirmed: bool


class MaterialDownloadOut(BaseModel):
    url: str
    expires_at: datetime


class MaterialReportIn(BaseModel):
    reason: MaterialReportReason
    note: str = Field(default="", max_length=500)


class MaterialReportCreatedOut(BaseModel):
    id: str
    status: MaterialReportStatus
    duplicate: bool


class MaterialReportOut(BaseModel):
    id: str
    material_id: str
    material_title: str
    subject_id: str
    subject_name: str
    material_hidden: bool
    reason: MaterialReportReason
    note: str
    status: MaterialReportStatus
    reporter: PersonOut | None
    handled_by: PersonOut | None
    handled_at: datetime | None
    created_at: datetime


class MaterialReportPageOut(BaseModel):
    items: list[MaterialReportOut]
    total: int


class MaterialReportStatusIn(BaseModel):
    status: MaterialReportStatus


class VisibilityIn(BaseModel):
    hidden: bool
