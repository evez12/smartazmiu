import socket

from app.core.jobs import ArqQueue


def _closed_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


async def test_a_lost_wake_up_does_not_fail_the_request() -> None:
    """Redis outage (§13.5): the work is already persisted, so enqueue errors are logged, not raised."""
    queue = ArqQueue(f"redis://127.0.0.1:{_closed_port()}/0")
    try:
        await queue.dispatch_notifications()
        await queue.sync_audiences()
    finally:
        await queue.close()
