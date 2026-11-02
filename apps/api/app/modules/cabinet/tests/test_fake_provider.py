import pytest

from app.core.config import Settings
from app.modules.cabinet.fake import FakeCabinetProvider
from app.modules.cabinet.provider import (
    CabinetNotAvailableYetError,
    CabinetProvider,
    CabinetUnavailableError,
    build_provider,
)
from app.modules.cabinet.tests.contract import CabinetProviderContract


class TestFakeProviderContract(CabinetProviderContract):
    @pytest.fixture
    def provider(self) -> CabinetProvider:
        return FakeCabinetProvider()

    @pytest.fixture
    def known_id(self) -> str:
        return "25765201"

    @pytest.fixture
    def unknown_id(self) -> str:
        return "T-10457"


async def test_a_switched_off_fake_is_unavailable() -> None:
    provider = FakeCabinetProvider()
    provider.break_connection()

    with pytest.raises(CabinetUnavailableError):
        await provider.grades("25765201")

    provider.break_connection(False)
    assert (await provider.grades("25765201")).items


async def test_different_students_get_different_but_stable_results() -> None:
    provider = FakeCabinetProvider()

    first = await provider.grades("25765201")
    second = await provider.grades("25765202")

    assert [g.score for g in first.items] != [g.score for g in second.items]
    assert first == await FakeCabinetProvider().grades("25765201")


def test_the_university_system_is_not_available_yet() -> None:
    with pytest.raises(CabinetNotAvailableYetError):
        build_provider(Settings(cabinet_provider="azmiu"))


def production(url: str = "", key: str = "") -> Settings:
    return Settings(
        app_env="production",
        ticket_secret="t",
        attendance_secret="a",
        cabinet_provider="azmiu",
        cabinet_api_url=url,
        cabinet_api_key=key,
    )


def test_production_never_serves_made_up_grades() -> None:
    with pytest.raises(ValueError, match="not allowed in production"):
        Settings(
            app_env="production", ticket_secret="t", attendance_secret="a", cabinet_provider="fake"
        )


def test_production_refuses_the_real_provider_without_credentials() -> None:
    with pytest.raises(ValueError, match="CABINET_API_KEY"):
        production()
    with pytest.raises(ValueError, match="CABINET_API_KEY"):
        production(url="https://cabinet.example")
    assert production(url="https://cabinet.example", key="k").cabinet_provider == "azmiu"
