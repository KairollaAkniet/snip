from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, desc, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import cache
from app.config import get_settings
from app.database import SessionLocal
from app.models import Click, Link
from app.schemas import CountItem, LinkCreate, LinkStats
from app.utils import generate_code, parse_user_agent, referrer_domain

MAX_CODE_ATTEMPTS = 5
STATS_DAYS = 30
TOP_N = 8


class AliasTakenError(Exception):
    pass


@dataclass
class ResolvedLink:
    id: int
    url: str
    expired: bool


def as_utc(dt: datetime) -> datetime:
    # SQLite drops tzinfo; values are always written in UTC so re-attach it.
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def is_expired(expires_at: datetime | None) -> bool:
    return expires_at is not None and as_utc(expires_at) <= datetime.now(UTC)


async def create_link(db: AsyncSession, data: LinkCreate) -> Link:
    expires_at = (
        datetime.now(UTC) + timedelta(days=data.expires_in_days) if data.expires_in_days else None
    )

    if data.custom_alias:
        candidates = [data.custom_alias]
    else:
        length = get_settings().code_length
        candidates = [generate_code(length) for _ in range(MAX_CODE_ATTEMPTS)]

    for code in candidates:
        link = Link(code=code, original_url=str(data.url), expires_at=expires_at, clicks_count=0)
        db.add(link)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            continue
        await db.refresh(link)
        return link

    if data.custom_alias:
        raise AliasTakenError(data.custom_alias)
    raise RuntimeError("Could not generate a unique code")


async def get_link(db: AsyncSession, code: str) -> Link | None:
    return await db.scalar(select(Link).where(Link.code == code))


async def list_links(db: AsyncSession, limit: int = 20) -> list[Link]:
    result = await db.scalars(select(Link).order_by(desc(Link.created_at), desc(Link.id)).limit(limit))
    return list(result)


async def delete_link(db: AsyncSession, link: Link) -> None:
    await db.execute(delete(Click).where(Click.link_id == link.id))
    await db.delete(link)
    await db.commit()
    await cache.delete(cache.link_key(link.code), cache.stats_key(link.code))


async def resolve(db: AsyncSession, code: str) -> ResolvedLink | None:
    """Cache-aside lookup used by the redirect hot path."""
    cached = await cache.get_json(cache.link_key(code))
    if cached:
        expires_at = datetime.fromisoformat(cached["expires_at"]) if cached["expires_at"] else None
        return ResolvedLink(id=cached["id"], url=cached["url"], expired=is_expired(expires_at))

    link = await get_link(db, code)
    if link is None:
        return None

    ttl = get_settings().link_cache_ttl
    if link.expires_at is not None:
        seconds_left = int((as_utc(link.expires_at) - datetime.now(UTC)).total_seconds())
        ttl = min(ttl, max(seconds_left, 1))

    await cache.set_json(
        cache.link_key(code),
        {
            "id": link.id,
            "url": link.original_url,
            "expires_at": as_utc(link.expires_at).isoformat() if link.expires_at else None,
        },
        ttl,
    )
    return ResolvedLink(id=link.id, url=link.original_url, expired=is_expired(link.expires_at))


async def record_click(link_id: int, code: str, user_agent: str, referrer: str | None) -> None:
    """Runs as a background task after the redirect is sent, so it opens its own session."""
    device, browser, os_name = parse_user_agent(user_agent)
    async with SessionLocal() as db:
        db.add(
            Click(
                link_id=link_id,
                referrer=referrer_domain(referrer),
                device=device,
                browser=browser,
                os=os_name,
            )
        )
        await db.execute(
            update(Link).where(Link.id == link_id).values(clicks_count=Link.clicks_count + 1)
        )
        await db.commit()
    await cache.delete(cache.stats_key(code))


async def _top(db: AsyncSession, link_id: int, column) -> list[CountItem]:
    rows = await db.execute(
        select(column, func.count().label("n"))
        .where(Click.link_id == link_id)
        .group_by(column)
        .order_by(desc("n"))
        .limit(TOP_N)
    )
    return [CountItem(label=label, count=n) for label, n in rows]


async def get_stats(db: AsyncSession, link: Link) -> LinkStats:
    cached = await cache.get_json(cache.stats_key(link.code))
    if cached:
        return LinkStats.model_validate(cached)

    today = datetime.now(UTC).date()
    first_day = today - timedelta(days=STATS_DAYS - 1)
    since = datetime.combine(first_day, datetime.min.time(), tzinfo=UTC)

    day = func.date(Click.created_at)
    rows = await db.execute(
        select(day, func.count())
        .where(Click.link_id == link.id, Click.created_at >= since)
        .group_by(day)
    )
    per_day = {str(d): n for d, n in rows}
    clicks_by_day = [
        CountItem(label=(first_day + timedelta(days=i)).isoformat(),
                  count=per_day.get((first_day + timedelta(days=i)).isoformat(), 0))
        for i in range(STATS_DAYS)
    ]

    total = await db.scalar(select(func.count()).select_from(Click).where(Click.link_id == link.id))

    stats = LinkStats(
        code=link.code,
        total_clicks=total or 0,
        clicks_by_day=clicks_by_day,
        devices=await _top(db, link.id, Click.device),
        browsers=await _top(db, link.id, Click.browser),
        os=await _top(db, link.id, Click.os),
        referrers=await _top(db, link.id, Click.referrer),
    )
    await cache.set_json(cache.stats_key(link.code), stats.model_dump(), get_settings().stats_cache_ttl)
    return stats
