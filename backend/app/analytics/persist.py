"""Persist a click event to Postgres.

Called by the worker (`process_one`) after dequeuing an event from the
Redis click queue. Looks up the URL by `short_code` (the worker doesn't
trust the FK in the event payload — short_code is the source of truth),
parses the User-Agent into structured fields, and inserts a row.
"""
from datetime import datetime
from typing import Any

from app.analytics.ua import parse_user_agent
from app.db.models import Click
from app.db.repository import UrlRepository


async def persist_click(event: dict[str, Any]) -> int:
    """Persist a click event. Returns the click id, or 0 if the URL was
    not found (deleted between redirect and processing — drop the event).
    """
    # Late import so tests can monkey-patch `app.db.session.AsyncSessionLocal`.
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        url = await UrlRepository(session).get_by_code(event["short_code"])
        if url is None:
            # URL was deleted between the redirect and the worker pick-up.
            # Drop the click rather than failing — the URL is gone.
            return 0

        ua = parse_user_agent(event.get("user_agent"))
        click = Click(
            url_id=url.id,
            clicked_at=datetime.fromisoformat(event["ts"]),
            referrer=event.get("referrer") or None,
            user_agent=event.get("user_agent"),
            browser=ua.browser,
            os=ua.os,
            device=ua.device,
        )
        session.add(click)
        await session.commit()
        await session.refresh(click)
        return click.id