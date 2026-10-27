"""Prometheus metrics (§7). Labels carry transports, error codes and job kinds only: never a user, channel or file.

The API runs several uvicorn workers, so process metrics use the client's multiprocess mode when
``PROMETHEUS_MULTIPROC_DIR`` is set (compose mounts a fresh tmpfs there). Queue and scan figures live in Redis and
Postgres; they are read when Prometheus scrapes, so the worker process needs no exporter of its own.
"""

import os
import time
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass

import structlog
from fastapi import APIRouter, Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    generate_latest,
    multiprocess,
)
from prometheus_client.core import GaugeMetricFamily, Metric
from prometheus_client.registry import REGISTRY, Collector
from pydantic import ValidationError
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.modules.chat.models import MessageAttachment, ScanStatus
from app.modules.materials.models import MaterialVersion

logger = structlog.get_logger(__name__)

WS_CONNECTIONS = Gauge(
    "smartazmiu_ws_connections", "Open chat WebSocket connections", multiprocess_mode="livesum"
)
MESSAGES_SENT = Counter(
    "smartazmiu_chat_messages_sent", "Chat messages stored and published", ["transport"]
)
SEND_ERRORS = Counter(
    "smartazmiu_chat_send_errors",
    "Chat sends refused or failed, by error code",
    ["transport", "code"],
)

# ARQ keeps queued jobs in a sorted set scored by the time they may run, in milliseconds.
ARQ_QUEUE = "arq:queue"


@contextmanager
def counting_send(transport: str) -> Iterator[None]:
    """Counts a failed send by its catalogue code; the caller counts the success once it knows it was new."""
    try:
        yield
    except AppError as exc:
        SEND_ERRORS.labels(transport, exc.code).inc()
        raise
    except ValidationError:
        SEND_ERRORS.labels(transport, "request.validation_failed").inc()
        raise
    except Exception:
        SEND_ERRORS.labels(transport, "internal").inc()
        raise


@dataclass(frozen=True, slots=True)
class Snapshot:
    queue_depth: float | None
    queue_lag_seconds: float | None
    scans_pending: dict[str, float]
    scans_deferred: dict[str, float]
    scans_rejected: dict[tuple[str, str], float]


class SnapshotCollector(Collector):
    def __init__(self, snapshot: Snapshot) -> None:
        self.snapshot = snapshot

    def collect(self) -> Iterable[Metric]:
        s = self.snapshot
        if s.queue_depth is not None and s.queue_lag_seconds is not None:
            yield GaugeMetricFamily(
                "smartazmiu_job_queue_depth", "Jobs waiting in the ARQ queue", value=s.queue_depth
            )
            yield GaugeMetricFamily(
                "smartazmiu_job_queue_lag_seconds",
                "How long the oldest due job has waited to start",
                value=s.queue_lag_seconds,
            )
        pending = GaugeMetricFamily(
            "smartazmiu_scan_queue_depth", "Uploads waiting for the virus scan", labels=["kind"]
        )
        deferred = GaugeMetricFamily(
            "smartazmiu_scan_deferred",
            "Uploads whose scan was postponed (scanner or storage unavailable)",
            labels=["kind"],
        )
        for kind, value in s.scans_pending.items():
            pending.add_metric([kind], value)
        for kind, value in s.scans_deferred.items():
            deferred.add_metric([kind], value)
        yield pending
        yield deferred
        # Rejected rows are never deleted (the object is purged, the row kept), so this only grows: a counter.
        rejected = GaugeMetricFamily(
            "smartazmiu_scan_rejected",
            "Uploads rejected by the type check (failed) or ClamAV (infected), since the start",
            labels=["kind", "status"],
        )
        for (kind, status), value in s.scans_rejected.items():
            rejected.add_metric([kind, status], value)
        yield rejected


async def queue_figures(redis: Redis) -> tuple[float | None, float | None]:
    try:
        depth = await redis.zcard(ARQ_QUEUE)
        now_ms = time.time() * 1000
        due = await redis.zrangebyscore(ARQ_QUEUE, "-inf", now_ms, start=0, num=1, withscores=True)
    except (RedisError, OSError) as exc:
        logger.warning("metrics_queue_unavailable", error=type(exc).__name__)
        return None, None
    lag = (now_ms - due[0][1]) / 1000 if due else 0.0
    return float(depth), max(lag, 0.0)


async def scan_figures(
    session: AsyncSession,
) -> tuple[dict[str, float], dict[str, float], dict[tuple[str, str], float]]:
    pending: dict[str, float] = {}
    deferred: dict[str, float] = {}
    rejected: dict[tuple[str, str], float] = {}
    sources = (
        ("attachment", MessageAttachment, MessageAttachment.message_id),
        ("material", MaterialVersion, MaterialVersion.material_id),
    )
    for kind, model, owner in sources:
        waiting = (model.scan_status == ScanStatus.PENDING) & owner.is_not(None)
        row = (
            await session.execute(
                select(
                    func.count().filter(waiting),
                    func.count().filter(waiting & (model.scan_attempts > 0)),
                )
            )
        ).one()
        pending[kind], deferred[kind] = float(row[0]), float(row[1])
        counts = dict(
            (
                await session.execute(
                    select(model.scan_status, func.count())
                    .where(model.scan_status.in_([ScanStatus.FAILED, ScanStatus.INFECTED]))
                    .group_by(model.scan_status)
                )
            ).all()
        )
        for status in (ScanStatus.FAILED, ScanStatus.INFECTED):
            rejected[(kind, status.value)] = float(counts.get(status, 0))
    return pending, deferred, rejected


def process_registry() -> CollectorRegistry:
    if not os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        return REGISTRY
    registry = CollectorRegistry()
    multiprocess.MultiProcessCollector(registry)  # type: ignore[no-untyped-call]
    return registry


def mark_process_dead() -> None:
    """Drops this worker's live gauges, so a restarted worker does not count closed sockets twice."""
    if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        multiprocess.mark_process_dead(os.getpid())  # type: ignore[no-untyped-call]


router = APIRouter(include_in_schema=False)


@router.get("/metrics")
async def metrics(request: Request) -> Response:
    """Internal: nginx routes nothing here and the web proxy forwards only ``/api/v1``."""
    state = request.app.state
    depth, lag = await queue_figures(state.durable_redis)
    pending: dict[str, float] = {}
    deferred: dict[str, float] = {}
    rejected: dict[tuple[str, str], float] = {}
    try:
        async with state.database.sessionmaker() as session:
            pending, deferred, rejected = await scan_figures(session)
    except (SQLAlchemyError, OSError) as exc:
        logger.warning("metrics_database_unavailable", error=type(exc).__name__)
    snapshot = CollectorRegistry()
    snapshot.register(SnapshotCollector(Snapshot(depth, lag, pending, deferred, rejected)))
    body = generate_latest(process_registry()) + generate_latest(snapshot)
    return Response(body, media_type=CONTENT_TYPE_LATEST)
