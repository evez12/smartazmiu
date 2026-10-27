"""Admin-managed, rule-based moderation of message text (§5.5)."""

import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.text import normalize_az
from app.core.time import utc_now
from app.modules.audit.models import AuditAction
from app.modules.audit.service import record_audit
from app.modules.chat.models import BlockedTerm, BlockedTermAction
from app.modules.users.service import CurrentUser

LANGUAGES = frozenset({"az", "en", "ru"})


def validate_pattern(pattern: str, is_regex: bool) -> str:
    normalized = normalize_az(pattern).exact
    if not normalized or len(normalized) > 128:
        raise AppError("chat.blocked_term_invalid", 422)
    if is_regex:
        # Restrict regexes to the simple character/word operators needed for a blocklist.
        # Groups and backreferences invite catastrophic backtracking on user-written bodies.
        if "(" in normalized or ")" in normalized or re.search(r"\\[1-9]", normalized):
            raise AppError("chat.blocked_term_invalid", 422)
        try:
            compiled = re.compile(normalized)
        except re.error as exc:
            raise AppError("chat.blocked_term_invalid", 422) from exc
        if compiled.search("") is not None:
            raise AppError("chat.blocked_term_invalid", 422)
    return normalized


def matches(term: BlockedTerm, body: str) -> bool:
    text = normalize_az(body)
    pattern = normalize_az(term.pattern)
    if term.is_regex:
        return any(
            re.search(candidate, value) is not None
            for candidate, value in ((pattern.exact, text.exact), (pattern.folded, text.folded))
        )
    return pattern.exact in text.exact or pattern.folded in text.folded


class BlockedTermService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self) -> list[BlockedTerm]:
        return list(
            await self.session.scalars(
                select(BlockedTerm)
                .where(BlockedTerm.disabled_at.is_(None))
                .order_by(BlockedTerm.id)
            )
        )

    async def add(
        self, actor: CurrentUser, pattern: str, is_regex: bool, action: BlockedTermAction, lang: str
    ) -> BlockedTerm:
        if lang not in LANGUAGES:
            raise AppError("chat.blocked_term_invalid", 422)
        term = BlockedTerm(
            pattern=validate_pattern(pattern, is_regex),
            is_regex=is_regex,
            action=action,
            lang=lang,
        )
        self.session.add(term)
        await self.session.flush()
        record_audit(
            self.session,
            AuditAction.BLOCKED_TERM_ADDED,
            actor_id=actor.id,
            target_type="blocked_term",
            target_id=term.id,
            details={"action": action.value, "lang": lang},
        )
        await self.session.commit()
        return term

    async def remove(self, actor: CurrentUser, term_id: uuid.UUID) -> None:
        term = await self.session.get(BlockedTerm, term_id)
        if term is None or term.disabled_at is not None:
            raise AppError("chat.blocked_term_not_found", 404)
        term.disabled_at = utc_now()
        record_audit(
            self.session,
            AuditAction.BLOCKED_TERM_REMOVED,
            actor_id=actor.id,
            target_type="blocked_term",
            target_id=term_id,
        )
        await self.session.commit()

    async def check(self, body: str) -> BlockedTermAction | None:
        terms = await self.list()
        actions = {term.action for term in terms if matches(term, body)}
        if BlockedTermAction.REJECT in actions:
            return BlockedTermAction.REJECT
        return BlockedTermAction.HOLD if actions else None
