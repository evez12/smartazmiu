"""Scoped chat moderation actions (§5.5)."""

import uuid
from datetime import timedelta

from sqlalchemy import delete, exists, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.time import utc_now
from app.modules.audit.models import AuditAction
from app.modules.audit.service import record_audit
from app.modules.chat.bus import ChatBus, channel_topic, user_topic
from app.modules.chat.lookup import find_message
from app.modules.chat.models import (
    Channel,
    ChannelBan,
    ChannelMember,
    GlobalChatBan,
    MemberRole,
    Message,
    MessageModeration,
    ModerationAction,
    ModerationActionKind,
    ThreadLock,
)
from app.modules.chat.payloads import message_payload
from app.modules.chat.search import body_vector
from app.modules.users.models import Role, RoleCode, UserRole
from app.modules.users.service import CurrentUser

MUTE_SECONDS = frozenset({3600, 86400, 604800})
SLOW_MODE_SECONDS = frozenset({0, 10, 30, 60})


class ModerationService:
    def __init__(self, session: AsyncSession, bus: ChatBus) -> None:
        self.session = session
        self.bus = bus

    async def act(
        self,
        actor: CurrentUser,
        action: ModerationActionKind,
        *,
        channel_id: uuid.UUID | None,
        message_id: int | None,
        target_user_id: uuid.UUID | None,
        duration_seconds: int | None,
        reason: str,
    ) -> ModerationAction:
        is_admin = RoleCode.ADMIN.value in actor.roles
        if action is ModerationActionKind.GLOBAL_BAN:
            if not is_admin or target_user_id is None:
                raise AppError("moderation.forbidden", 403)
        else:
            if channel_id is None or not await self._can_moderate(actor, channel_id):
                raise AppError("moderation.channel_not_found", 404)
        message = await find_message(self.session, message_id, lock=True) if message_id else None
        if message_id is not None and (message is None or message.channel_id != channel_id):
            raise AppError("moderation.message_not_found", 404)
        if message is not None:
            target_user_id = message.author_id
        if target_user_id is not None:
            await self._protect_target(actor, target_user_id, message)
        clean_reason = reason.strip()
        if not clean_reason:
            raise AppError("moderation.reason_required", 422)

        if action is ModerationActionKind.DELETE_MESSAGE:
            if message is None or message.deleted_at is not None:
                raise AppError("moderation.message_not_found", 404)
            await self.session.execute(
                update(Message)
                .where(Message.id == message.id, Message.created_at == message.created_at)
                .values(deleted_at=utc_now(), body_tsv=None, is_verified_answer=False)
            )
        elif action is ModerationActionKind.RESTORE_MESSAGE:
            if message is None or message.deleted_at is not None:
                raise AppError("moderation.message_not_found", 404)
            message.moderation = MessageModeration.VISIBLE
            message.body_tsv = body_vector(message.body)
        elif action is ModerationActionKind.MUTE:
            if duration_seconds not in MUTE_SECONDS or target_user_id is None:
                raise AppError("moderation.invalid_duration", 422)
            await self.session.execute(
                update(ChannelMember)
                .where(
                    ChannelMember.channel_id == channel_id,
                    ChannelMember.user_id == target_user_id,
                )
                .values(posting_muted_until=utc_now() + timedelta(seconds=duration_seconds))
            )
        elif action is ModerationActionKind.KICK:
            if target_user_id is None:
                raise AppError("moderation.target_required", 422)
            await self.session.execute(
                delete(ChannelMember).where(
                    ChannelMember.channel_id == channel_id,
                    ChannelMember.user_id == target_user_id,
                )
            )
        elif action is ModerationActionKind.BAN:
            if target_user_id is None or channel_id is None:
                raise AppError("moderation.target_required", 422)
            await self.session.execute(
                insert(ChannelBan)
                .values(channel_id=channel_id, user_id=target_user_id, banned_by=actor.id)
                .on_conflict_do_nothing()
            )
            await self.session.execute(
                delete(ChannelMember).where(
                    ChannelMember.channel_id == channel_id,
                    ChannelMember.user_id == target_user_id,
                )
            )
        elif action is ModerationActionKind.GLOBAL_BAN:
            assert target_user_id is not None
            await self.session.execute(
                insert(GlobalChatBan)
                .values(user_id=target_user_id, banned_by=actor.id)
                .on_conflict_do_nothing()
            )
        elif action is ModerationActionKind.LOCK_THREAD:
            if message is None or message.parent_id is not None:
                raise AppError("moderation.thread_not_found", 422)
            await self.session.execute(
                insert(ThreadLock)
                .values(message_id=message.id, channel_id=message.channel_id, locked_by=actor.id)
                .on_conflict_do_nothing()
            )
        elif action is ModerationActionKind.SLOW_MODE:
            if duration_seconds not in SLOW_MODE_SECONDS or channel_id is None:
                raise AppError("moderation.invalid_duration", 422)
            await self.session.execute(
                update(Channel)
                .where(Channel.id == channel_id)
                .values(slow_mode_seconds=duration_seconds)
            )

        entry = ModerationAction(
            moderator_id=actor.id,
            action=action,
            target_user_id=target_user_id,
            channel_id=channel_id,
            message_id=message_id,
            duration_seconds=duration_seconds,
            reason=clean_reason,
        )
        self.session.add(entry)
        await self.session.flush()
        record_audit(
            self.session,
            AuditAction.MODERATION_ACTION,
            actor_id=actor.id,
            target_type="moderation_action",
            target_id=entry.id,
            details={
                "action": action.value,
                "channel_id": str(channel_id) if channel_id else None,
                "message_id": str(message_id) if message_id else None,
                "target_user_id": str(target_user_id) if target_user_id else None,
                "duration_seconds": duration_seconds,
            },
        )
        await self.session.commit()
        await self._publish(action, channel_id, message, target_user_id)
        return entry

    async def _can_moderate(self, actor: CurrentUser, channel_id: uuid.UUID) -> bool:
        if actor.roles & {RoleCode.ADMIN.value, RoleCode.STAFF.value}:
            return await self.session.get(Channel, channel_id) is not None
        return bool(
            await self.session.scalar(
                select(
                    exists().where(
                        ChannelMember.channel_id == channel_id,
                        ChannelMember.user_id == actor.id,
                        ChannelMember.role.in_([MemberRole.OWNER, MemberRole.MODERATOR]),
                    )
                )
            )
        )

    async def _protect_target(
        self, actor: CurrentUser, target_id: uuid.UUID, message: Message | None
    ) -> None:
        if target_id == actor.id and RoleCode.ADMIN.value not in actor.roles:
            raise AppError("moderation.protected_target", 403)
        if RoleCode.MODERATOR.value not in actor.roles or RoleCode.ADMIN.value in actor.roles:
            return
        roles = set(
            await self.session.scalars(
                select(Role.code)
                .join(UserRole, UserRole.role_id == Role.id)
                .where(UserRole.user_id == target_id)
            )
        )
        if roles & {RoleCode.ADMIN.value, RoleCode.TEACHER.value}:
            raise AppError("moderation.protected_target", 403)
        if message is not None and message.author_id == actor.id:
            raise AppError("moderation.protected_target", 403)

    async def _publish(
        self,
        action: ModerationActionKind,
        channel_id: uuid.UUID | None,
        message: Message | None,
        target_user_id: uuid.UUID | None,
    ) -> None:
        if message is not None and action in {
            ModerationActionKind.DELETE_MESSAGE,
            ModerationActionKind.RESTORE_MESSAGE,
        }:
            payload = await message_payload(self.session, message.id, None)
            if payload is not None:
                await self.bus.publish(
                    channel_topic(message.channel_id),
                    "message.updated",
                    payload.model_dump(mode="json"),
                )
        if channel_id is not None and action is ModerationActionKind.SLOW_MODE:
            await self.bus.publish(
                channel_topic(channel_id), "channel.updated", {"channel_id": str(channel_id)}
            )
        if target_user_id is not None and action in {
            ModerationActionKind.KICK,
            ModerationActionKind.BAN,
            ModerationActionKind.GLOBAL_BAN,
        }:
            channel_ids = (
                [channel_id]
                if channel_id is not None
                else list(
                    await self.session.scalars(
                        select(ChannelMember.channel_id).where(
                            ChannelMember.user_id == target_user_id
                        )
                    )
                )
            )
            for revoked_channel_id in channel_ids:
                await self.bus.publish(
                    user_topic(target_user_id),
                    "membership.revoked",
                    {"channel_id": str(revoked_channel_id)},
                )
