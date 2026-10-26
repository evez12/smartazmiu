"""Creates and removes the throwaway accounts and channels of the chat load test (D-073).

    uv --directory apps/api run python ../../infra/load/prepare.py up --users 500 --channels 20
    uv --directory apps/api run python ../../infra/load/prepare.py down

Accounts are Keycloak users ``load-NNNN`` mirrored as application users with a ``load-…@smartazmiu.test``
address; channels are private groups named ``Yük testi NN``. ``down`` removes exactly these (and the messages in
those channels), so the seed data and real accounts are never touched. Only for local and staging stacks.
"""

import argparse
import asyncio
import json
import os
import secrets
from pathlib import Path

import httpx
from app.core.config import get_settings
from app.modules.chat.models import Channel, ChannelMember, ChannelType, MemberRole
from app.modules.users.models import User
from sqlalchemy import delete, insert, select, text
from sqlalchemy.ext.asyncio import create_async_engine

STATE = Path(__file__).with_name(".state.json")
PREFIX = "load-"
CHANNEL_PREFIX = "Yük testi "
KEYCLOAK = os.environ.get("KEYCLOAK_URL", "http://127.0.0.1:8080")
REALM = os.environ.get("KEYCLOAK_REALM", "smartazmiu")


async def admin(client: httpx.AsyncClient) -> None:
    response = await client.post(
        f"{KEYCLOAK}/realms/master/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": os.environ.get("KEYCLOAK_ADMIN_USER", "admin"),
            "password": os.environ["KEYCLOAK_ADMIN_PASSWORD"],
        },
    )
    response.raise_for_status()
    client.headers["Authorization"] = f"Bearer {response.json()['access_token']}"


async def up(users: int, channels: int) -> None:
    password = secrets.token_urlsafe(18)
    names = [f"{PREFIX}{n:04d}" for n in range(1, users + 1)]
    async with httpx.AsyncClient(
        base_url=f"{KEYCLOAK}/admin/realms/{REALM}", timeout=30
    ) as kc:
        await admin(kc)
        for name in names:
            response = await kc.post(
                "/users",
                json={
                    "username": name,
                    "email": f"{name}@smartazmiu.test",
                    "emailVerified": True,
                    "enabled": True,
                    "firstName": "Yük",
                    "lastName": f"Testi {name[-4:]}",
                    "credentials": [
                        {"type": "password", "value": password, "temporary": False}
                    ],
                },
            )
            if response.status_code == 409:
                # Left over from an interrupted run: give it this run's password.
                found = await kc.get(
                    "/users", params={"username": name, "exact": "true"}
                )
                reset = await kc.put(
                    f"/users/{found.json()[0]['id']}/reset-password",
                    json={"type": "password", "value": password, "temporary": False},
                )
                reset.raise_for_status()
            else:
                response.raise_for_status()
    engine = create_async_engine(str(get_settings().database_url))
    async with engine.begin() as connection:
        # Registry-style rows (no identity provider subject yet): the first sign-in links them by e-mail.
        await connection.execute(
            insert(User),
            [
                {
                    "email": f"{name}@smartazmiu.test",
                    "given_name": "Yük",
                    "family_name": f"Testi {name[-4:]}",
                    "display_name": f"Yük Testi {name[-4:]}",
                }
                for name in names
            ],
        )
        ids = list(
            await connection.scalars(
                select(User.id)
                .where(User.email.like(f"{PREFIX}%@smartazmiu.test"))
                .order_by(User.email)
            )
        )
        channel_ids = []
        for number in range(channels):
            channel_id = await connection.scalar(
                insert(Channel)
                .values(
                    type=ChannelType.PRIVATE_GROUP,
                    name=f"{CHANNEL_PREFIX}{number + 1:02d}",
                )
                .returning(Channel.id)
            )
            channel_ids.append(str(channel_id))
            members = ids[number::channels]
            await connection.execute(
                insert(ChannelMember),
                [
                    {"channel_id": channel_id, "user_id": m, "role": MemberRole.MEMBER}
                    for m in members
                ],
            )
    await engine.dispose()
    # The k6 script reads this; user n is in channel n % channels.
    STATE.write_text(
        json.dumps({"password": password, "users": names, "channels": channel_ids})
    )
    print(f"{users} accounts in {channels} channels; state in {STATE}")


async def down() -> None:
    engine = create_async_engine(str(get_settings().database_url))
    async with engine.begin() as connection:
        channels = select(Channel.id).where(
            Channel.type == ChannelType.PRIVATE_GROUP,
            Channel.name.like(f"{CHANNEL_PREFIX}%"),
        )
        # Rows that point at messages without a foreign key (ADR 0002); messages cascade from the channel.
        for table in ("message_client_ids", "message_reactions", "message_mentions"):
            await connection.execute(
                text(
                    f"DELETE FROM {table} WHERE message_id IN "
                    "(SELECT id FROM messages WHERE channel_id IN (SELECT id FROM channels "
                    "WHERE type = 'private_group' AND name LIKE :prefix))"
                ),
                {"prefix": f"{CHANNEL_PREFIX}%"},
            )
        await connection.execute(delete(Channel).where(Channel.id.in_(channels)))
        await connection.execute(
            delete(User).where(User.email.like(f"{PREFIX}%@smartazmiu.test"))
        )
    await engine.dispose()
    async with httpx.AsyncClient(
        base_url=f"{KEYCLOAK}/admin/realms/{REALM}", timeout=30
    ) as kc:
        await admin(kc)
        while True:
            found = (
                await kc.get("/users", params={"search": PREFIX, "max": 200})
            ).json()
            found = [u for u in found if u["username"].startswith(PREFIX)]
            if not found:
                break
            for user in found:
                await kc.delete(f"/users/{user['id']}")
    STATE.unlink(missing_ok=True)
    print("load test accounts and channels removed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("up")
    create.add_argument("--users", type=int, default=500)
    create.add_argument("--channels", type=int, default=20)
    commands.add_parser("down")
    args = parser.parse_args()
    asyncio.run(up(args.users, args.channels) if args.command == "up" else down())


if __name__ == "__main__":
    main()
