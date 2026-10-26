from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from app.modules.chat.policy import Action, ChannelState, Decision, Reason, authorize

NOW = datetime(2027, 1, 15, 10, 0, tzinfo=UTC)
LATER = NOW + timedelta(hours=1)
MEMBER = ChannelState(now=NOW, is_member=True)


@pytest.mark.parametrize(
    ("state", "action", "expected"),
    [
        (ChannelState(now=NOW, is_member=False), Action.READ, Decision(False, Reason.NOT_MEMBER)),
        (ChannelState(now=NOW, is_member=False), Action.SEND, Decision(False, Reason.NOT_MEMBER)),
        (MEMBER, Action.READ, Decision(True)),
        (MEMBER, Action.SEND, Decision(True)),
        (
            replace(MEMBER, account_active=False),
            Action.SEND,
            Decision(False, Reason.ACCOUNT_INACTIVE),
        ),
        (replace(MEMBER, is_archived=True), Action.SEND, Decision(False, Reason.CHANNEL_ARCHIVED)),
        (replace(MEMBER, is_archived=True), Action.READ, Decision(True)),
        (
            replace(MEMBER, exam_until=LATER),
            Action.SEND,
            Decision(False, Reason.EXAM_MODE, until=LATER),
        ),
        (
            replace(MEMBER, exam_until=LATER),
            Action.SEND_ATTACHMENT,
            Decision(False, Reason.EXAM_MODE, until=LATER),
        ),
        (replace(MEMBER, exam_until=LATER), Action.READ, Decision(True)),
        (replace(MEMBER, is_readonly=True), Action.REACT, Decision(False, Reason.CHANNEL_READONLY)),
        (
            replace(MEMBER, member_readonly=True),
            Action.SEND,
            Decision(False, Reason.CHANNEL_READONLY),
        ),
        (
            replace(MEMBER, user_blocked_peer=True),
            Action.SEND,
            Decision(False, Reason.USER_BLOCKED),
        ),
        (replace(MEMBER, dm_unavailable=True), Action.SEND, Decision(False, Reason.DM_UNAVAILABLE)),
        (replace(MEMBER, dm_unavailable=True), Action.DELETE, Decision(True)),
        (
            replace(MEMBER, posting_muted_until=LATER),
            Action.SEND,
            Decision(False, Reason.MUTED, until=LATER),
        ),
        (
            replace(MEMBER, posting_muted_until=NOW - timedelta(seconds=1)),
            Action.SEND,
            Decision(True),
        ),
        (replace(MEMBER, posting_muted_until=LATER), Action.EDIT, Decision(True)),
        (
            replace(MEMBER, slow_mode_seconds=30, slow_mode_retry_after=12),
            Action.SEND,
            Decision(False, Reason.SLOW_MODE, retry_after=12),
        ),
        (
            replace(MEMBER, slow_mode_seconds=30, slow_mode_retry_after=12, slow_mode_exempt=True),
            Action.SEND,
            Decision(True),
        ),
        (
            replace(MEMBER, rate_limit_retry_after=4),
            Action.SEND,
            Decision(False, Reason.RATE_LIMITED, retry_after=4),
        ),
        (MEMBER, Action.MENTION_CHANNEL, Decision(False, Reason.CHANNEL_MENTION_NOT_ALLOWED)),
        (replace(MEMBER, can_mention_channel=True), Action.MENTION_CHANNEL, Decision(True)),
    ],
)
def test_each_reason(state: ChannelState, action: Action, expected: Decision) -> None:
    assert authorize(action, state) == expected


def test_the_most_fundamental_reason_wins() -> None:
    """Slow mode + exam mode + mute (§13.2): the user is told about the exam, not the slow mode."""
    everything = replace(
        MEMBER,
        exam_until=LATER,
        is_readonly=True,
        posting_muted_until=LATER,
        slow_mode_seconds=30,
        slow_mode_retry_after=10,
        rate_limit_retry_after=5,
    )
    order = [
        (everything, Reason.EXAM_MODE),
        (replace(everything, exam_until=None), Reason.CHANNEL_READONLY),
        (replace(everything, exam_until=None, is_readonly=False), Reason.MUTED),
        (
            replace(everything, exam_until=None, is_readonly=False, posting_muted_until=None),
            Reason.SLOW_MODE,
        ),
        (
            replace(
                everything,
                exam_until=None,
                is_readonly=False,
                posting_muted_until=None,
                slow_mode_retry_after=None,
            ),
            Reason.RATE_LIMITED,
        ),
    ]
    for state, reason in order:
        assert authorize(Action.SEND, state).reason is reason
    assert authorize(Action.SEND, replace(everything, is_archived=True)).reason is (
        Reason.CHANNEL_ARCHIVED
    )


def test_exam_mode_has_no_exemption_for_teachers() -> None:
    """D-057: the offering's teachers are exempt from slow mode, never from exam mode."""
    teacher = replace(MEMBER, slow_mode_exempt=True, can_mention_channel=True, exam_until=LATER)
    assert authorize(Action.SEND, teacher).reason is Reason.EXAM_MODE
