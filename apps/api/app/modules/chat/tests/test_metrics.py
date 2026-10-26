"""Prometheus metrics for chat delivery, the job queue and the scan queue (§7); no personal data in labels."""

import time
import uuid

from fastapi import FastAPI
from httpx import AsyncClient
from prometheus_client import REGISTRY
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.chat.models import MessageAttachment, ScanStatus

from .conftest import MakeChannel, MakePerson, Open
from .test_ws import body, joined


def sample(name: str, **labels: str) -> float:
    return REGISTRY.get_sample_value(name, labels) or 0.0


async def test_sends_errors_and_sockets_are_counted(
    client: AsyncClient, open_socket: Open, person: MakePerson, channel: MakeChannel
) -> None:
    aysel, ramin = await person(), await person("Ramin", "Əliyev")
    room = await channel(aysel, ramin)
    sent_rest = sample("smartazmiu_chat_messages_sent_total", transport="rest")
    sent_ws = sample("smartazmiu_chat_messages_sent_total", transport="ws")
    refused = sample(
        "smartazmiu_chat_send_errors_total", transport="ws", code="chat.channel_not_found"
    )
    sockets = sample("smartazmiu_ws_connections")

    payload = body()
    url = f"/api/v1/chat/channels/{room}/messages"
    assert (await client.post(url, headers=aysel.headers, json=payload)).status_code == 201
    # A retried client id is not a second message.
    assert (await client.post(url, headers=aysel.headers, json=payload)).status_code == 200
    assert sample("smartazmiu_chat_messages_sent_total", transport="rest") == sent_rest + 1

    socket = await open_socket(ramin)
    await joined(socket, room)
    assert sample("smartazmiu_ws_connections") == sockets + 1
    assert (await socket.reply("message.send", {"channel_id": str(room), **body()}))[
        "type"
    ] == "ack"
    stranger = await socket.reply("message.send", {"channel_id": str(uuid.uuid4()), **body()})
    assert stranger["data"]["code"] == "chat.channel_not_found"
    assert sample("smartazmiu_chat_messages_sent_total", transport="ws") == sent_ws + 1
    assert (
        sample("smartazmiu_chat_send_errors_total", transport="ws", code="chat.channel_not_found")
        == refused + 1
    )


async def test_scrape_reports_queue_and_scan_figures(
    app: FastAPI,
    client: AsyncClient,
    db: AsyncSession,
    person: MakePerson,
    channel: MakeChannel,
) -> None:
    aysel = await person()
    room = await channel(aysel)
    db.add_all(
        [
            MessageAttachment(
                channel_id=room,
                uploader_id=aysel.id,
                message_id=message_id,
                object_key=f"chat/{uuid.uuid4()}",
                filename="Seminar.pdf",
                mime="application/pdf",
                size_bytes=10,
                scan_status=status,
                scan_attempts=attempts,
            )
            for message_id, status, attempts in (
                (1, ScanStatus.PENDING, 0),
                (2, ScanStatus.PENDING, 2),
                (3, ScanStatus.INFECTED, 0),
                # Not sent yet: not waiting for a scan.
                (None, ScanStatus.PENDING, 0),
            )
        ]
    )
    await db.commit()
    queue: Redis = app.state.durable_redis
    await queue.zadd("arq:queue", {"scan_attachments": time.time() * 1000 - 30_000})
    try:
        scraped = await client.get("/metrics")
    finally:
        await queue.zrem("arq:queue", "scan_attachments")
    assert scraped.status_code == 200
    text = scraped.text
    assert 'smartazmiu_scan_queue_depth{kind="attachment"} 2.0' in text
    assert 'smartazmiu_scan_deferred{kind="attachment"} 1.0' in text
    assert 'smartazmiu_scan_rejected{kind="attachment",status="infected"} 1.0' in text
    assert 'smartazmiu_scan_queue_depth{kind="material"} 0.0' in text
    assert "smartazmiu_job_queue_depth 1.0" in text
    lag = next(
        float(line.split()[1])
        for line in text.splitlines()
        if line.startswith("smartazmiu_job_queue_lag_seconds ")
    )
    assert 29 <= lag < 60
    assert aysel.name not in text
    assert str(aysel.id) not in text

    # Without Redis A the scrape still answers; the queue figures are left out rather than reported as zero.
    app.state.durable_redis = Redis(host="127.0.0.1", port=1, socket_connect_timeout=0.2)
    try:
        degraded = await client.get("/metrics")
    finally:
        await app.state.durable_redis.aclose()
        app.state.durable_redis = queue
    assert degraded.status_code == 200
    assert "smartazmiu_job_queue_depth" not in degraded.text
    assert "smartazmiu_scan_queue_depth" in degraded.text
