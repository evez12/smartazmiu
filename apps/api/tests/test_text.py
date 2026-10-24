import pytest

from app.core.text import lower_az, normalize_az, search_key


@pytest.mark.parametrize(
    ("text", "exact", "folded"),
    [
        ("İSTİFADƏÇİ", "istifadəçi", "istifadeci"),
        ("ISTIFADECI", "ıstıfadecı", "istifadeci"),
        ("ıspanaq", "ıspanaq", "ispanaq"),
        ("İqtisadi riyaziyyat", "iqtisadi riyaziyyat", "iqtisadi riyaziyyat"),
        ("Iqtisadi riyaziyyat", "ıqtisadi riyaziyyat", "iqtisadi riyaziyyat"),
        (
            "Mikroİqtisadiyyat ŞƏHLA Ağayeva",
            "mikroiqtisadiyyat şəhla ağayeva",
            "mikroiqtisadiyyat sehla agayeva",
        ),
        (
            "Расписание группы 765A2 and IT",
            "расписание группы 765a2 and ıt",
            "расписание группы 765a2 and it",
        ),
    ],
)
def test_normalize_az(text: str, exact: str, folded: str) -> None:
    result = normalize_az(text)
    assert (result.exact, result.folded) == (exact, folded)


def test_diacritic_and_case_variants_share_the_folded_form() -> None:
    assert normalize_az("İSTİFADƏÇİ").folded == normalize_az("ISTIFADECI").folded
    assert normalize_az("Mikroiqtisadiyyat").folded == normalize_az("MİKROİQTİSADİYYAT").folded


def test_invisible_characters_and_whitespace_are_removed() -> None:
    assert (
        normalize_az("  Mikro\u200biqtisadiyyat\u00ad \t\n fənni\ufeff ").exact
        == "mikroiqtisadiyyat fənni"
    )


def test_nfkc_composes_a_decomposed_dotted_capital_i() -> None:
    assert normalize_az("I\u0307lkin").exact == "ilkin"
    assert normalize_az("ﬁzika").exact == "fizika"


def test_lower_az_differs_from_the_default_mapping() -> None:
    assert lower_az("IŞIQ İŞI") == "ışıq işı"


def test_search_key_joins_present_parts() -> None:
    assert search_key("Aysel", None, "Məmmədova", "", "2025076512") == "aysel memmedova 2025076512"
