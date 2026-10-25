from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.delivery import Dispatcher
from app.workers import main


async def test_worker_starts_dispatches_and_stops(db: AsyncSession) -> None:
    ctx: dict[str, Any] = {}
    await main.startup(ctx)
    try:
        assert isinstance(ctx["dispatcher"], Dispatcher)
        assert await main.dispatch_notifications(ctx) == 0
        assert await main.sync_audiences(ctx) == 0
    finally:
        await main.shutdown(ctx)
    assert main.dispatch_notifications in main.WorkerSettings.functions
    assert main.sync_audiences in main.WorkerSettings.functions
    assert set(main.RELEVANCE) == {"announcement", "event", "schedule_change"}
    assert main.WorkerSettings.keep_result == 0
