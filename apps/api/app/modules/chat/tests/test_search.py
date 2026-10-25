from sqlalchemy import func, literal, select
from sqlalchemy.dialects.postgresql import REGCONFIG
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.chat.search import body_vector, search_document


def test_the_document_holds_the_exact_and_the_folded_form() -> None:
    assert search_document("İSTİFADƏÇİ  qaydaları") == "istifadəçi qaydaları istifadeci qaydalari"
    # Typed without Azerbaijani letters, the folded form still meets the folded form of İSTİFADƏÇİ.
    assert search_document("ISTIFADECI") == "ıstıfadecı istifadeci"
    assert search_document("ıspanaq") == "ıspanaq ispanaq"
    assert search_document("Mikro\u200biqtisadiyyat exam экзамен") == (
        "mikroiqtisadiyyat exam экзамен"
    )


async def test_queries_with_and_without_azerbaijani_letters_match(db: AsyncSession) -> None:
    vector = body_vector("İqtisadi riyaziyyat imtahanı")
    for word in ("iqtisadi", "imtahanı", "imtahani"):
        query = func.to_tsquery(literal("simple", REGCONFIG), word)
        assert await db.scalar(select(vector.op("@@")(query))), word
    missing = func.to_tsquery(literal("simple", REGCONFIG), "statistika")
    assert not await db.scalar(select(vector.op("@@")(missing)))
