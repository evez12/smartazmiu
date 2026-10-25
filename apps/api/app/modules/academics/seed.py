"""Loads the sample academic data through the regular import pipeline (``make seed``).

Each ``<kind>.csv`` in the given directory is validated and applied in dependency order, exactly as the
admin wizard would do it; re-running it changes nothing.
"""

import asyncio
import sys
from pathlib import Path

from app.core.config import get_settings
from app.core.db import Database
from app.core.logging import configure_logging
from app.modules.academics.import_service import ImportService
from app.modules.academics.models import ImportKind, ImportStatus


async def seed(directory: Path) -> int:
    database = Database(str(get_settings().database_url))
    try:
        async with database.sessionmaker() as session:
            service = ImportService(session)
            for kind in ImportKind:
                path = directory / f"{kind.value}.csv"
                if not path.exists():
                    continue
                record = await service.create(kind, path.name, path.read_bytes(), None, None)
                if record.status is ImportStatus.READY:
                    record = await service.apply(record.id, None)
                if record.status is not ImportStatus.APPLIED:
                    print(f"{kind.value}: {record.status.value}", *record.errors[:20], sep="\n  ")
                    return 1
                counts = ", ".join(f"{name} {count}" for name, count in record.summary.items())
                print(f"{kind.value}: {counts}")
    finally:
        await database.dispose()
    return 0


if __name__ == "__main__":
    configure_logging("WARNING")
    sys.exit(asyncio.run(seed(Path(sys.argv[1]))))
