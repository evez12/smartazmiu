"""The exam timetable through the import wizard: preview, warnings, apply, idempotence (D-097)."""

import uuid
from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.academics.models import ImportKind
from app.modules.academics.tests.conftest import Upload
from app.modules.chat.bus import ChatBus
from app.modules.chat.provisioning import ChannelProvisioner
from app.modules.exams.models import ExamSlot

HEADER = "subject_code,year,term,offering_code,group_codes,date,starts_at,ends_at,room_code\n"
Seed = Callable[..., Awaitable[None]]


@pytest.fixture
async def ready(seed: Seed, db: AsyncSession) -> None:
    await seed(ImportKind.ROOMS)
    await ChannelProvisioner(db).run()


async def slot_count(db: AsyncSession) -> int:
    return await db.scalar(select(func.count()).select_from(ExamSlot)) or 0


def counts(record: dict[str, Any]) -> dict[str, int]:
    return {name: record["summary"][name] for name in ("created", "updated", "unchanged")}


def codes(items: list[dict[str, Any]]) -> list[tuple[int, str]]:
    return [(item["row"], item["code"]) for item in items]


async def test_a_clean_file_has_no_warnings_and_applies_once(
    upload: Upload, db: AsyncSession, ready: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    told: list[list[uuid.UUID]] = []

    async def record(self: ChatBus, channel_ids: list[uuid.UUID]) -> None:
        told.append(list(channel_ids))

    monkeypatch.setattr(ChatBus, "channels_changed", record)
    content = (
        HEADER
        + "IQT-2102,2026,Payız,765a2,,2027-01-14,10:00,11:30,2-204\n"
        + "XDL-2103,2026,Payız,765a2,,2027-01-18,10:00,11:30,1-206\n"
    )
    preview = await upload(ImportKind.EXAM_SLOTS, content)
    assert (preview["status"], preview["error_count"]) == ("ready", 0)
    assert preview["warnings"] == []
    assert await slot_count(db) == 0
    applied = await upload(ImportKind.EXAM_SLOTS, content, apply=True)
    assert applied["summary"]["created"] == 2
    assert await slot_count(db) == 2
    # Offering channels hear about it only once the import is committed.
    assert not told or told[-1]

    again = await upload(ImportKind.EXAM_SLOTS, content, apply=True)
    assert counts(again) == {"created": 0, "updated": 0, "unchanged": 2}
    assert await slot_count(db) == 2

    moved = content.replace("11:30,2-204", "12:00,2-204")
    changed = await upload(ImportKind.EXAM_SLOTS, moved, apply=True)
    assert counts(changed) == {"created": 0, "updated": 1, "unchanged": 1}
    row = await db.scalar(select(ExamSlot).where(ExamSlot.room_code == "2-204"))
    assert row is not None
    assert row.room_id is not None
    assert told


async def test_collisions_are_warnings_that_do_not_block_the_import(
    upload: Upload, db: AsyncSession, ready: None
) -> None:
    content = (
        HEADER
        # Two offerings of group 765a2 at the same time, and two rooms the same.
        + "IQT-2102,2026,Payız,765a2,,2027-01-14,10:00,11:30,2-204\n"
        + "IQT-2101,2026,Payız,765a2,,2027-01-14,10:30,12:00,1-301\n"
        # Another group, but the same room as the first row.
        + "IQT-2101,2026,Payız,765a1,,2027-01-14,11:00,12:30,2-204\n"
    )
    preview = await upload(ImportKind.EXAM_SLOTS, content)
    assert preview["status"] == "ready"
    assert preview["error_count"] == 0
    found = codes(preview["warnings"])
    assert (2, "overlaps_group") in found
    assert (3, "overlaps_group") in found
    assert (4, "overlaps_room") in found
    applied = await upload(ImportKind.EXAM_SLOTS, content, apply=True)
    assert applied["summary"]["created"] == 3
    assert codes(applied["warnings"]) == found

    # A later file is warned about what is already stored.
    later = await upload(
        ImportKind.EXAM_SLOTS,
        HEADER + "XDL-2103,2026,Payız,765a2,,2027-01-14,11:00,12:00,1-206\n",
    )
    assert codes(later["warnings"]) == [(2, "overlaps_group")]


async def test_a_bad_row_blocks_the_whole_file(
    upload: Upload, db: AsyncSession, ready: None
) -> None:
    bad = await upload(
        ImportKind.EXAM_SLOTS,
        HEADER
        + "IQT-2102,2026,Payız,765a2,,2027-01-14,11:30,10:00,2-204\n"
        + "IQT-2102,2026,Payız,765a2,,2027-01-15,10:00,11:30,Z-999\n"
        + "NOPE-1,2026,Payız,765a2,,2027-01-15,10:00,11:30,2-204\n"
        + "IQT-2102,2026,Payız,765a2,,2027-01-15,00:00,23:59,2-204\n",
    )
    assert bad["status"] == "invalid"
    assert sorted(codes(bad["errors"])) == [
        (2, "times_out_of_order"),
        (3, "unknown_reference"),
        (4, "unknown_reference"),
        (5, "window_too_long"),
    ]
    assert await slot_count(db) == 0


async def test_the_template_has_the_expected_header(
    client: AsyncClient, staff_headers: dict[str, str]
) -> None:
    response = await client.get("/api/v1/admin/imports/templates/exam_slots", headers=staff_headers)
    assert response.status_code == 200
    assert response.content.decode("utf-8-sig").strip() == HEADER.strip()
