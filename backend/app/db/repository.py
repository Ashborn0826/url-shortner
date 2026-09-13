from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Click, Url
from app.shortcode import generate_code


class ShortCodeExistsError(Exception):
    """Raised when a custom short code collides with an existing row."""


def _is_short_code_unique_violation(error: IntegrityError) -> bool:
    """Inspect an IntegrityError to determine whether it is a UNIQUE
    violation on urls.short_code (as opposed to some other integrity failure
    like NOT NULL or FK).

    SQLite error message: "UNIQUE constraint failed: urls.short_code"
    Postgres: pgcode '23505' (unique_violation); constraint name in
              orig.diag.constraint_name contains "short_code".
    """
    orig = error.orig
    msg = str(orig).lower()
    if "unique" in msg and "short_code" in msg:
        return True
    diag = getattr(orig, "diag", None)
    if diag is not None:
        constraint = getattr(diag, "constraint_name", "") or ""
        if "short_code" in constraint:
            return True
    return False


class UrlRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, long_url: str, custom_code: str | None = None) -> Url:
        if custom_code is not None:
            code, is_custom = custom_code, True
        else:
            code, is_custom = generate_code(), False

        url = Url(short_code=code, long_url=long_url, is_custom=is_custom)
        self.session.add(url)
        try:
            await self.session.commit()
        except IntegrityError as e:
            await self.session.rollback()
            if _is_short_code_unique_violation(e):
                raise ShortCodeExistsError(code) from None
            raise
        await self.session.refresh(url)
        return url

    async def get_by_code(self, short_code: str) -> Url | None:
        result = await self.session.execute(
            select(Url).where(Url.short_code == short_code)
        )
        return result.scalar_one_or_none()

    async def code_exists(self, short_code: str) -> bool:
        result = await self.session.execute(
            select(Url.id).where(Url.short_code == short_code)
        )
        return result.scalar_one_or_none() is not None


class ClickRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        url_id: int,
        clicked_at: datetime,
        referrer: str | None,
        user_agent: str | None,
        browser: str | None,
        os: str | None,
        device: str | None,
    ) -> Click:
        click = Click(
            url_id=url_id,
            clicked_at=clicked_at,
            referrer=referrer,
            user_agent=user_agent,
            browser=browser,
            os=os,
            device=device,
        )
        self.session.add(click)
        await self.session.commit()
        await self.session.refresh(click)
        return click

    async def count_by_url(self, url_id: int) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(Click).where(Click.url_id == url_id)
        )
        return result.scalar() or 0

    async def clicks_by_day(self, url_id: int, days: int = 30) -> list[dict]:
        """Return [{day: 'YYYY-MM-DD', count: N}, ...] for the last `days`."""
        since = datetime.now(timezone.utc) - timedelta(days=days)
        result = await self.session.execute(
            select(
                func.date(Click.clicked_at).label("day"),
                func.count().label("count"),
            )
            .where(Click.url_id == url_id, Click.clicked_at >= since)
            .group_by("day")
            .order_by("day")
        )
        return [{"day": str(row.day), "count": row.count} for row in result]

    async def top_referrers(self, url_id: int, limit: int = 5) -> list[dict]:
        """Top referrers by click count. NULL referrer buckets into '(direct)'."""
        result = await self.session.execute(
            select(
                func.coalesce(Click.referrer, "(direct)").label("referrer"),
                func.count().label("count"),
            )
            .where(Click.url_id == url_id)
            .group_by("referrer")
            .order_by(func.count().desc())
            .limit(limit)
        )
        return [{"referrer": row.referrer, "count": row.count} for row in result]

    async def top_browsers(self, url_id: int, limit: int = 5) -> list[dict]:
        """Top browsers by click count. Skips clicks with NULL browser."""
        result = await self.session.execute(
            select(
                Click.browser.label("browser"),
                func.count().label("count"),
            )
            .where(Click.url_id == url_id, Click.browser.isnot(None))
            .group_by(Click.browser)
            .order_by(func.count().desc())
            .limit(limit)
        )
        return [{"browser": row.browser, "count": row.count} for row in result]