"""The pilot support channel (D-074): registry people and staff are members, staff moderate it."""

from collections.abc import Awaitable, Callable

from httpx import AsyncClient
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.chat.models import Channel, ChannelMember, ChannelType, MemberRole
from app.modules.chat.provisioning import SUPPORT_CHANNEL_NAME, ChannelProvisioner
from app.modules.users.models import Role, RoleCode, User, UserRole, UserStatus

from .conftest import MakePerson

Seed = Callable[..., Awaitable[None]]


async def support_roles(db: AsyncSession) -> dict[str, MemberRole]:
    rows = await db.execute(
        select(User.email, ChannelMember.role)
        .join(ChannelMember, ChannelMember.user_id == User.id)
        .join(Channel, Channel.id == ChannelMember.channel_id)
        .where(Channel.type == ChannelType.SUPPORT)
        .execution_options(populate_existing=True)
    )
    return {email: role for email, role in rows if email}


async def test_registry_people_and_staff_share_one_support_channel(
    client: AsyncClient,
    db: AsyncSession,
    seed: Seed,
    person: MakePerson,
    staff_headers: dict[str, str],
) -> None:
    await seed()
    stranger = await person("Səbinə", "Rzayeva")  # signed in, but not in the registry
    await ChannelProvisioner(db).run()

    channels = list(await db.scalars(select(Channel).where(Channel.type == ChannelType.SUPPORT)))
    assert [channel.name for channel in channels] == [SUPPORT_CHANNEL_NAME]
    roles = await support_roles(db)
    assert roles["aysel.mammadova@smartazmiu.test"] is MemberRole.MEMBER
    assert roles["leyla.hasanova@smartazmiu.test"] is MemberRole.MEMBER
    # The staff account behind the import fixture moderates it.
    assert roles["elvin.quliyev@smartazmiu.test"] is MemberRole.MODERATOR
    stranger_email = await db.scalar(select(User.email).where(User.id == stranger.id))
    assert stranger_email not in roles

    # Losing the staff role makes a moderator a member (Leyla stays: she is in the registry).
    leyla = await db.scalar(select(User.id).where(User.email == "leyla.hasanova@smartazmiu.test"))
    staff_role = await db.scalar(select(Role.id).where(Role.code == RoleCode.STAFF.value))
    assert leyla is not None
    assert staff_role is not None
    db.add(UserRole(user_id=leyla, role_id=staff_role))
    await db.commit()
    await ChannelProvisioner(db).run()
    assert (await support_roles(db))["leyla.hasanova@smartazmiu.test"] is MemberRole.MODERATOR
    await db.execute(delete(UserRole).where(UserRole.user_id == leyla))
    await db.execute(
        update(User)
        .where(User.email == "aysel.mammadova@smartazmiu.test")
        .values(status=UserStatus.INACTIVE)
    )
    await db.commit()
    result = await ChannelProvisioner(db).run()
    roles = await support_roles(db)
    assert roles["leyla.hasanova@smartazmiu.test"] is MemberRole.MEMBER
    # Inactive accounts leave it like every provisioned channel (§13.1).
    assert "aysel.mammadova@smartazmiu.test" not in roles
    assert result.channels_created == 0

    # Members can ask there; the channel behaves like any other (ADR 0004).
    message = await client.post(
        f"/api/v1/chat/channels/{channels[0].id}/messages",
        headers=staff_headers,
        json={
            "body": "Salam, suallarınızı burada yazın.",
            "client_msg_id": "0b6c8a4e-7d5e-4c1d-9f3a-2e8b1c6d4f70",
        },
    )
    assert message.status_code == 201, message.text
