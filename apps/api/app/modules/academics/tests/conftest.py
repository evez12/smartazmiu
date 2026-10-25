import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient

from app.modules.academics.models import ImportKind
from tests.support import TokenFactory

SEED_DIR = Path(__file__).resolve().parents[6] / "infra" / "seed" / "academics"

Upload = Callable[..., Awaitable[dict[str, Any]]]


@pytest.fixture
def staff_headers(tokens: TokenFactory) -> dict[str, str]:
    token = tokens.issue(
        str(uuid.uuid4()),
        ["staff"],
        given_name="Elvin",
        family_name="Quliyev",
        email="elvin.quliyev@smartazmiu.test",
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def upload(client: AsyncClient, staff_headers: dict[str, str]) -> Upload:
    """Uploads a file as staff and returns the preview; ``apply=True`` also applies it."""

    async def run(
        kind: ImportKind | str,
        content: bytes | str,
        *,
        file_name: str | None = None,
        encoding: str | None = None,
        apply: bool = False,
        expected_status: int = 201,
    ) -> dict[str, Any]:
        kind_value = kind.value if isinstance(kind, ImportKind) else kind
        data = content.encode() if isinstance(content, str) else content
        form = {"kind": kind_value, **({"encoding": encoding} if encoding else {})}
        response = await client.post(
            "/api/v1/admin/imports",
            headers=staff_headers,
            data=form,
            files={"file": (file_name or f"{kind_value}.csv", data, "text/csv")},
        )
        assert response.status_code == expected_status, response.text
        body: dict[str, Any] = response.json()
        if apply:
            assert body["status"] == "ready", body["errors"]
            applied = await client.post(
                f"/api/v1/admin/imports/{body['id']}/apply", headers=staff_headers
            )
            assert applied.status_code == 200, applied.text
            body = applied.json()
            assert body["status"] == "applied", body["errors"]
        return body

    return run


@pytest.fixture
def seed(upload: Upload) -> Callable[..., Awaitable[None]]:
    """Applies the sample data files of ``infra/seed/academics`` up to and including ``until``."""

    async def run(until: ImportKind = ImportKind.ENROLLMENTS) -> None:
        for kind in ImportKind:
            await upload(kind, (SEED_DIR / f"{kind.value}.csv").read_bytes(), apply=True)
            if kind is until:
                return

    return run
