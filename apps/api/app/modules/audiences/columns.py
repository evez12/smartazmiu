"""Audience columns shared by announcements and events: one typed foreign key per target kind."""

import uuid
from enum import StrEnum

from sqlalchemy import CheckConstraint, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.modules.audiences.service import Audience, AudienceType

TARGET_COLUMNS = {
    AudienceType.FACULTY: "faculty_id",
    AudienceType.SPECIALTY: "specialty_id",
    AudienceType.GROUP: "academic_group_id",
    AudienceType.COURSE_OFFERING: "course_offering_id",
}


def _enum(enum: type[StrEnum], name: str) -> Enum:
    return Enum(enum, name=name, values_callable=lambda members: [m.value for m in members])


def audience_check() -> CheckConstraint:
    """Exactly the column of the audience type is set; the whole university has none."""
    columns = list(TARGET_COLUMNS.values())
    rules = ["(audience_type = 'university' AND num_nonnulls({}) = 0)".format(", ".join(columns))]
    for kind, column in TARGET_COLUMNS.items():
        others = ", ".join(c for c in columns if c != column)
        rules.append(
            f"(audience_type = '{kind.value}' AND {column} IS NOT NULL AND num_nonnulls({others}) = 0)"
        )
    return CheckConstraint(" OR ".join(rules), name="one_audience_target")


class AudienceColumns:
    audience_type: Mapped[AudienceType] = mapped_column(_enum(AudienceType, "audience_type"))
    faculty_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("faculties.id"))
    specialty_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("specialties.id"))
    academic_group_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("academic_groups.id"))
    course_offering_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("course_offerings.id"))

    @property
    def audience(self) -> Audience:
        column = TARGET_COLUMNS.get(self.audience_type)
        return Audience(self.audience_type, getattr(self, column) if column else None)

    def set_audience(self, audience: Audience) -> None:
        self.audience_type = audience.type
        for kind, column in TARGET_COLUMNS.items():
            setattr(self, column, audience.target_id if kind is audience.type else None)
