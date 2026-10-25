"""Default topics of course and community channels (§5.1)."""

from dataclasses import dataclass

from app.modules.chat.models import ChannelType


@dataclass(frozen=True, slots=True)
class TopicSpec:
    slug: str
    """Transliterated ASCII, used in URLs."""
    name: str


COURSE_TOPICS = (
    TopicSpec("umumi", "ümumi"),
    TopicSpec("suallar", "suallar"),
    TopicSpec("materiallar", "materiallar"),
    TopicSpec("imtahan-hazirligi", "imtahan-hazırlığı"),
)
COMMUNITY_TOPICS = (*COURSE_TOPICS, TopicSpec("meslehet", "məsləhət"))

# Group, faculty and direct-message channels have no topics: every message has topic_id NULL (D-060).
DEFAULT_TOPICS: dict[ChannelType, tuple[TopicSpec, ...]] = {
    ChannelType.COURSE_OFFERING: COURSE_TOPICS,
    ChannelType.SUBJECT_COMMUNITY: COMMUNITY_TOPICS,
}
