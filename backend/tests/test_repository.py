import pytest

from app.db.repository import ShortCodeExistsError, UrlRepository


async def test_create_auto_generates_code_and_persists(session):
    repo = UrlRepository(session)
    url = await repo.create("https://example.com")
    assert url.short_code is not None
    assert len(url.short_code) == 7
    assert url.long_url == "https://example.com"
    assert url.is_custom is False

    fetched = await repo.get_by_code(url.short_code)
    assert fetched is not None
    assert fetched.id == url.id
    assert fetched.long_url == "https://example.com"


async def test_create_with_custom_code_marks_is_custom(session):
    repo = UrlRepository(session)
    url = await repo.create("https://example.com", custom_code="docs")
    assert url.short_code == "docs"
    assert url.is_custom is True


async def test_duplicate_custom_code_raises(session):
    repo = UrlRepository(session)
    await repo.create("https://a.example", custom_code="docs")
    with pytest.raises(ShortCodeExistsError):
        await repo.create("https://b.example", custom_code="docs")


async def test_get_unknown_returns_none(session):
    repo = UrlRepository(session)
    assert await repo.get_by_code("nope") is None


async def test_code_exists_predicate(session):
    repo = UrlRepository(session)
    url = await repo.create("https://example.com")
    assert await repo.code_exists(url.short_code) is True
    assert await repo.code_exists("nope") is False