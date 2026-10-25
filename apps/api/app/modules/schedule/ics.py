"""iCalendar (RFC 5545) export of expanded occurrences in Asia/Baku time.

Each occurrence is its own event, so changes are exact: a moved class appears at its new time, a cancelled one
carries ``STATUS:CANCELLED`` and keeps its UID, so calendars that imported it earlier mark it as cancelled.
"""

from collections.abc import Iterable
from datetime import date, datetime, time

from app.modules.schedule.models import ClassType
from app.modules.schedule.service import Occurrence, OccurrenceStatus

CLASS_TYPE_LABELS = {
    ClassType.LECTURE: "mühazirə",
    ClassType.SEMINAR: "seminar",
    ClassType.LABORATORY: "laboratoriya",
}

# Baku has had no daylight saving time since 2016; a single STANDARD component describes it.
_VTIMEZONE = (
    "BEGIN:VTIMEZONE",
    "TZID:Asia/Baku",
    "BEGIN:STANDARD",
    "DTSTART:19700101T000000",
    "TZOFFSETFROM:+0400",
    "TZOFFSETTO:+0400",
    "TZNAME:+04",
    "END:STANDARD",
    "END:VTIMEZONE",
)


def _escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def _fold(line: str) -> list[str]:
    """Lines longer than 75 octets continue on lines starting with a space, never inside a character."""
    parts: list[str] = []
    current, size, limit = "", 0, 75
    for char in line:
        width = len(char.encode())
        if size + width > limit:
            parts.append(current)
            current, size, limit = " ", 1, 75
        current += char
        size += width
    parts.append(current)
    return parts


def _local(day: date, at: time) -> str:
    return f"{day:%Y%m%d}T{at:%H%M}00"


def _event(occurrence: Occurrence, stamp: str) -> list[str]:
    summary = f"{occurrence.subject.name_az} ({CLASS_TYPE_LABELS[occurrence.class_type]})"
    description = []
    if occurrence.teachers:
        description.append(f"Müəllim: {', '.join(occurrence.teachers)}")
    if occurrence.groups:
        description.append(f"Qruplar: {', '.join(occurrence.groups)}")
    if occurrence.status is OccurrenceStatus.CANCELLED:
        description.append("Dərs ləğv olunub.")
    elif occurrence.status is not OccurrenceStatus.SCHEDULED:
        description.append("Cədvəldə dəyişiklik var.")
    if occurrence.note:
        description.append(occurrence.note)
    lines = [
        "BEGIN:VEVENT",
        f"UID:{occurrence.entry_id}-{occurrence.original_day:%Y%m%d}@smartazmiu",
        f"DTSTAMP:{stamp}",
        f"DTSTART;TZID=Asia/Baku:{_local(occurrence.day, occurrence.starts_at)}",
        f"DTEND;TZID=Asia/Baku:{_local(occurrence.day, occurrence.ends_at)}",
        f"SUMMARY:{_escape(summary)}",
    ]
    if occurrence.room is not None:
        lines.append(
            f"LOCATION:{_escape(f'{occurrence.room.code}, {occurrence.room.building_name}')}"
        )
    lines.append(f"DESCRIPTION:{_escape(chr(10).join(description))}")
    cancelled = occurrence.status is OccurrenceStatus.CANCELLED
    lines += [f"STATUS:{'CANCELLED' if cancelled else 'CONFIRMED'}", "END:VEVENT"]
    return lines


def calendar(occurrences: Iterable[Occurrence], generated_at: datetime) -> str:
    stamp = f"{generated_at:%Y%m%dT%H%M%S}Z"
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//SmartAzMIU//Ders cedveli//AZ",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Dərs cədvəli",
        "X-WR-TIMEZONE:Asia/Baku",
        *_VTIMEZONE,
    ]
    for occurrence in occurrences:
        # The moved class is exported on its new day; its original day would only duplicate it.
        if occurrence.status is not OccurrenceStatus.MOVED_AWAY:
            lines += _event(occurrence, stamp)
    lines.append("END:VCALENDAR")
    return "".join(f"{part}\r\n" for line in lines for part in _fold(line))
