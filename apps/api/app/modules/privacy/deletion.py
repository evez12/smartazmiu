"""The database part of account deletion (ADR 0005, D-135).

``REFERENCES`` says what happens to every column that points at ``users``. A test compares it with the schema, so a
table added later without a decision fails the build instead of leaving a deleted person's data behind. The
functions here are idempotent: a purge that ran halfway is run again from the top.
"""

import hashlib
import hmac
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, cast

from sqlalchemy import CursorResult, ForeignKeyConstraint, MetaData, delete, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.modules.privacy.models import AccountDeletion
from app.modules.users.models import ContactVisibility, DmPolicy, User, UserStatus

PLACEHOLDER_NAME = "Silinmiş istifadəçi"
MIN_PEPPER_LENGTH = 16


class Handling(StrEnum):
    PERSONAL = "personal"
    """The row belongs to the person alone (settings, memberships, votes, cabinet mirror): deleted."""
    ANONYMIZED = "anonymized"
    """Others read the row: it stays and the reference is set to NULL, shown as the placeholder."""
    AUDIT = "audit"
    """Replaced by a keyed hash of the id (``AuditLog.actor_hash``, target and details)."""
    RETAINED = "retained"
    """Points at the tombstone, which holds no personal data, so the row keeps working (a DM, the ledger)."""


PERSONAL_COLUMNS = (
    "user_roles.user_id",
    "consent_records.user_id",
    "notifications.user_id",
    "push_subscriptions.user_id",
    "notification_preferences.user_id",
    "notification_quiet_hours.user_id",
    "announcement_recipients.user_id",
    "event_recipients.user_id",
    "event_registrations.user_id",
    "channel_members.user_id",
    "channel_reads.user_id",
    "message_reactions.user_id",
    "message_mentions.user_id",
    "user_blocks.blocked_id",
    "user_blocks.blocker_id",
    "mentor_profiles.user_id",
    "mentor_requests.requester_id",
    "tip_upvotes.user_id",
    "poll_votes.user_id",
    "saved_messages.user_id",
    "channel_bans.user_id",
    "global_chat_bans.user_id",
    "helpful_reactions.user_id",
    "forum_votes.user_id",
    "course_offering_teachers.teacher_id",
    "enrollments.user_id",
    "cabinet_students.user_id",
    "cabinet_grades.user_id",
    "cabinet_semesters.user_id",
    "cabinet_appeals.user_id",
    "cabinet_conflicts.user_id",
)
ANONYMIZED_COLUMNS = (
    # Content others read (D-091, D-093); the author reference is nullable since migration 0039.
    "feed_posts.author_id",
    "feed_comments.author_id",
    "forum_questions.author_id",
    "forum_answers.author_id",
    "forum_answers.verified_by",
    "course_tips.author_id",
    "course_tips.reviewed_by",
    "assignment_submissions.student_id",
    "assignment_files.student_id",
    "quiz_attempts.student_id",
    # Chat, files, reports and everything a person did as a staff member or moderator.
    "messages.author_id",
    "messages.verified_by",
    "message_attachments.uploader_id",
    "pinned_messages.pinned_by",
    "thread_locks.locked_by",
    "reports.reporter_id",
    "reports.handled_by",
    "material_reports.reporter_id",
    "material_reports.handled_by",
    "materials.created_by",
    "material_versions.uploader_id",
    "feedback.user_id",
    "feedback.handled_by",
    "moderation_actions.moderator_id",
    "moderation_actions.target_user_id",
    "channel_bans.banned_by",
    "global_chat_bans.banned_by",
    "channels.created_by",
    "mentor_requests.mentor_id",
    "mentor_profiles.teacher_taken_with_id",
    "announcements.created_by",
    "events.created_by",
    "event_registrations.checked_in_by",
    "assignments.created_by",
    "assignment_grades.graded_by",
    "quizzes.created_by",
    "attendance_sessions.opened_by",
    "attendance_records.marked_by",
    "attendance_records.student_id",
    "past_papers.reviewed_by",
    "past_papers.uploader_id",
    "subject_exam_modes.updated_by",
    "schedule_entries.teacher_id",
    "schedule_changes.teacher_id",
    "academic_groups.curator_id",
    "academic_imports.applied_by",
    "academic_imports.created_by",
    "cabinet_sync_runs.triggered_by",
)
AUDIT_COLUMNS = ("audit_logs.actor_id",)
RETAINED_COLUMNS = (
    "channels.user_low_id",
    "channels.user_high_id",
    "account_deletions.user_id",
    "account_deletions.requested_by",
)

REFERENCES: dict[str, Handling] = {
    **dict.fromkeys(PERSONAL_COLUMNS, Handling.PERSONAL),
    **dict.fromkeys(ANONYMIZED_COLUMNS, Handling.ANONYMIZED),
    **dict.fromkeys(AUDIT_COLUMNS, Handling.AUDIT),
    **dict.fromkeys(RETAINED_COLUMNS, Handling.RETAINED),
}


def references_to_users(metadata: MetaData) -> set[str]:
    """Every ``table.column`` of the schema that is a foreign key to ``users``."""
    found: set[str] = set()
    for table in metadata.tables.values():
        for constraint in table.constraints:
            if (
                isinstance(constraint, ForeignKeyConstraint)
                and constraint.referred_table.name == "users"
            ):
                found.update(f"{table.name}.{column.name}" for column in constraint.columns)
    return found


class DeletionNotConfiguredError(RuntimeError):
    """The pepper is missing: a hash without it could be reversed by trying every id."""


def subject_hash(user_id: uuid.UUID, pepper: str) -> str:
    """Keyed hash that names a deleted person in audit entries and the ledger (ADR 0005, decision 8)."""
    if len(pepper) < MIN_PEPPER_LENGTH:
        raise DeletionNotConfiguredError("DELETION_PEPPER is not set")
    return hmac.new(pepper.encode(), f"account:{user_id}".encode(), hashlib.sha256).hexdigest()


@dataclass(frozen=True, slots=True)
class PurgeCounts:
    deleted: int
    anonymized: int


async def purge_database(
    session: AsyncSession,
    deletion: AccountDeletion,
    settings: Settings,
    *,
    now: datetime | None = None,
) -> PurgeCounts | None:
    """Reduce one account to a tombstone inside the caller's transaction.

    Returns ``None`` when the database part is already done, so a retry after a failure in a later step (objects,
    identity provider) is a no-op here.
    """
    if deletion.database_purged_at is not None or deletion.user_id is None:
        return None
    digest = subject_hash(deletion.user_id, settings.deletion_pepper)
    user = await session.get(User, deletion.user_id, with_for_update=True)
    if user is None:
        raise LookupError("deletion ledger names a missing user")

    deleted = anonymized = 0
    for reference, handling in REFERENCES.items():
        table_name, column_name = reference.split(".")
        table = User.metadata.tables[table_name]
        column = table.c[column_name]
        if handling is Handling.PERSONAL:
            result = await session.execute(delete(table).where(column == user.id))
            deleted += cast("CursorResult[Any]", result).rowcount
        elif handling is Handling.ANONYMIZED:
            result = await session.execute(
                update(table).where(column == user.id).values({column_name: None})
            )
            anonymized += cast("CursorResult[Any]", result).rowcount

    await _hash_audit_references(session, user.id, digest)
    _make_tombstone(user)
    deletion.database_purged_at = now or datetime.now(UTC)
    await session.flush()
    return PurgeCounts(deleted=deleted, anonymized=anonymized)


async def _hash_audit_references(session: AsyncSession, user_id: uuid.UUID, digest: str) -> None:
    params = {"id": str(user_id), "hash": digest}
    await session.execute(
        text(
            "UPDATE audit_logs SET actor_hash = :hash, actor_id = NULL"
            " WHERE actor_id = CAST(:id AS uuid)"
        ),
        params,
    )
    await session.execute(
        text(
            "UPDATE audit_logs SET target_type = 'deleted_user', target_id = :hash"
            " WHERE target_type = 'user' AND target_id = :id"
        ),
        params,
    )
    # Entries about other things can still name the person in their details (a role change, an import row).
    await session.execute(
        text(
            "UPDATE audit_logs SET details = CAST(replace(CAST(details AS text), :id, :hash) AS jsonb)"
            " WHERE CAST(details AS text) LIKE '%' || :id || '%'"
        ),
        params,
    )


def _make_tombstone(user: User) -> None:
    """Keep the id (so references and the ledger stay valid) and nothing that identifies the person."""
    user.status = UserStatus.DELETED
    user.display_name = PLACEHOLDER_NAME
    user.given_name = ""
    user.family_name = ""
    user.search_key = ""
    user.bio = ""
    user.email = None
    user.university_id = None
    user.idp_subject = None
    user.person_type = None
    user.academic_group_id = None
    user.photo_key = None
    user.locale = None
    user.dm_policy = DmPolicy.NOBODY
    user.contact_visibility = ContactVisibility.HIDDEN
    user.onboarded_at = None
    user.roles_synced_at = None
    user.purge_at = None
