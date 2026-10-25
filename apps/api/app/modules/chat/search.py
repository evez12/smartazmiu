"""What gets indexed for message search (§5.7.1). Search queries arrive in Sprint 10 and use the same forms."""

from sqlalchemy import ColumnElement, func, literal
from sqlalchemy.dialects.postgresql import REGCONFIG

from app.core.text import normalize_az


def search_document(body: str) -> str:
    """The exact and the ASCII-folded form, so a query typed either way finds the message."""
    normalized = normalize_az(body)
    if normalized.folded == normalized.exact:
        return normalized.exact
    return f"{normalized.exact} {normalized.folded}"


def body_vector(body: str) -> ColumnElement[str]:
    # `simple` does no stemming; normalize_az has already done the language-specific work.
    return func.to_tsvector(literal("simple", REGCONFIG), search_document(body))
