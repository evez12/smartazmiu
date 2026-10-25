from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from structlog.testing import capture_logs

from app.modules.chat.partitions import existing_partitions, warn_if_running_out
from app.workers import main


async def test_the_worker_keeps_partitions_and_purges_client_ids(db: AsyncSession) -> None:
    ctx: dict[str, Any] = {}
    await main.startup(ctx)
    try:
        assert await main.ensure_message_partitions(ctx) == 0
        assert await main.purge_message_client_ids(ctx) == 0
    finally:
        await main.shutdown(ctx)
    names = {job.name for job in main.WorkerSettings.cron_jobs}
    assert {"cron:ensure_message_partitions", "cron:purge_message_client_ids"} <= names


async def test_a_warning_is_logged_when_future_partitions_run_out(db: AsyncSession) -> None:
    with capture_logs() as logs:
        await warn_if_running_out(db)
    assert logs == []
    # Far in the future no partition exists yet: the daily job must have stopped running.
    with capture_logs() as logs:
        await warn_if_running_out(db, today=date(2040, 1, 1))
    assert logs[0]["event"] == "message_partitions_running_out"
    assert logs[0]["future_months"] == 0
    assert not {name for name in await existing_partitions(db) if name >= "messages_y2040"}
