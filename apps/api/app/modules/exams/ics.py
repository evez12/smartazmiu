"""iCalendar export of a person's upcoming exams in Asia/Baku time (D-097).

Each exam keeps its UID, so a calendar that imported it earlier updates it when the time or the room changes.
"""

from collections.abc import Iterable
from datetime import datetime

from app.core.time import BAKU
from app.modules.exams.schemas import ExamSlotOut
from app.modules.schedule.ics import VTIMEZONE, escape, fold


def _local(moment: datetime) -> str:
    return f"{moment.astimezone(BAKU):%Y%m%dT%H%M%S}"


def calendar(exams: Iterable[ExamSlotOut], generated_at: datetime) -> str:
    stamp = f"{generated_at:%Y%m%dT%H%M%S}Z"
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//SmartAzMIU//Imtahanlar//AZ",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:İmtahan cədvəli",
        "X-WR-TIMEZONE:Asia/Baku",
        *VTIMEZONE,
    ]
    for exam in exams:
        lines += [
            "BEGIN:VEVENT",
            f"UID:exam-{exam.id}@smartazmiu",
            f"DTSTAMP:{stamp}",
            f"DTSTART;TZID=Asia/Baku:{_local(exam.starts_at)}",
            f"DTEND;TZID=Asia/Baku:{_local(exam.ends_at)}",
            f"SUMMARY:{escape(f'İmtahan: {exam.offering.subject_name}')}",
        ]
        if exam.room_code:
            lines.append(f"LOCATION:{escape(f'Otaq {exam.room_code}')}")
        if exam.offering.groups:
            lines.append(f"DESCRIPTION:{escape('Qruplar: ' + ', '.join(exam.offering.groups))}")
        lines += ["STATUS:CONFIRMED", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "".join(f"{part}\r\n" for line in lines for part in fold(line))
