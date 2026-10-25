"""Every import kind the wizard offers. Campus and timetable specs live in their own modules."""

from app.modules.academics.importers import (
    EnrollmentsImport,
    FacultiesImport,
    GroupsImport,
    ImportSpec,
    OfferingsImport,
    SemestersImport,
    SpecialtiesImport,
    StudentsImport,
    SubjectsImport,
    TeachersImport,
)
from app.modules.academics.models import ImportKind
from app.modules.campus.imports import BuildingsImport, FloorsImport, RoomsImport
from app.modules.schedule.imports import ScheduleChangesImport, ScheduleImport, WeekParityImport

SPECS: dict[ImportKind, ImportSpec] = {
    spec.kind: spec
    for spec in (
        FacultiesImport(),
        SpecialtiesImport(),
        SubjectsImport(),
        SemestersImport(),
        TeachersImport(),
        GroupsImport(),
        StudentsImport(),
        OfferingsImport(),
        EnrollmentsImport(),
        BuildingsImport(),
        FloorsImport(),
        RoomsImport(),
        WeekParityImport(),
        ScheduleImport(),
        ScheduleChangesImport(),
    )
}
