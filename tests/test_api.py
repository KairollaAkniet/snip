from datetime import UTC, datetime, timedelta

from sqlalchemy import update

from app.database import SessionLocal
from app.models import Link

CHROME_WIN = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
)
SAFARI_IPHONE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)


async def create(client, **payload):
    payload.setdefault("url", "https://example.com/some/very/long/path?x=1")
    return await client.post("/api/links", json=payload)


async def test_create_link(client):
    res = await create(client)
    assert res.status_code == 201
    body = res.json()
    assert len(body["code"]) == 7
    assert body["short_url"] == f"http://test/{body['code']}"
    assert body["clicks_count"] == 0
    assert body["expires_at"] is None


async def test_create_with_alias_and_conflict(client):
    assert (await create(client, custom_alias="my-link")).status_code == 201
    res = await create(client, custom_alias="my-link")
    assert res.status_code == 409


async def test_invalid_input(client):
    assert (await create(client, url="not a url")).status_code == 422
    assert (await create(client, custom_alias="a b")).status_code == 422
    assert (await create(client, custom_alias="docs")).status_code == 422
    assert (await create(client, expires_in_days=0)).status_code == 422


async def test_redirect_records_click_and_caches(client, redis):
    code = (await create(client, custom_alias="promo")).json()["code"]

    res = await client.get(f"/{code}", headers={"user-agent": CHROME_WIN, "referer": "https://www.google.com/search"})
    assert res.status_code == 302
    assert res.headers["location"] == "https://example.com/some/very/long/path?x=1"
    assert await redis.exists("link:promo")

    await client.get(f"/{code}", headers={"user-agent": SAFARI_IPHONE})

    link = (await client.get(f"/api/links/{code}")).json()
    assert link["clicks_count"] == 2

    stats = (await client.get(f"/api/links/{code}/stats")).json()
    assert stats["total_clicks"] == 2
    assert len(stats["clicks_by_day"]) == 30
    assert stats["clicks_by_day"][-1]["count"] == 2
    assert {d["label"] for d in stats["devices"]} == {"Desktop", "Mobile"}
    assert {b["label"] for b in stats["browsers"]} == {"Chrome", "Safari"}
    assert {r["label"] for r in stats["referrers"]} == {"google.com", "Direct"}


async def test_unknown_code_404(client):
    assert (await client.get("/nope123")).status_code == 404
    assert (await client.get("/api/links/nope123")).status_code == 404


async def test_expired_link_410(client):
    code = (await create(client, custom_alias="old", expires_in_days=1)).json()["code"]
    async with SessionLocal() as db:
        await db.execute(
            update(Link).where(Link.code == code).values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
        )
        await db.commit()
    assert (await client.get(f"/{code}")).status_code == 410


async def test_qr_code(client):
    code = (await create(client)).json()["code"]
    res = await client.get(f"/api/links/{code}/qr")
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/svg+xml"
    assert b"<svg" in res.content


async def test_list_and_delete(client, redis):
    first = (await create(client, custom_alias="first")).json()["code"]
    await create(client, custom_alias="second")
    await client.get(f"/{first}")

    codes = [link["code"] for link in (await client.get("/api/links")).json()]
    assert set(codes) == {"first", "second"}

    assert (await client.delete(f"/api/links/{first}")).status_code == 204
    assert not await redis.exists("link:first")
    assert (await client.get(f"/{first}")).status_code == 404


async def test_rate_limit(client):
    for _ in range(5):
        assert (await create(client)).status_code == 201
    assert (await create(client)).status_code == 429


async def test_works_without_redis(client, redis):
    from redis.asyncio import Redis

    from app import cache

    cache.set_redis(Redis.from_url("redis://127.0.0.1:1/0", socket_connect_timeout=0.2))
    code = (await create(client, custom_alias="noredis")).json()["code"]
    assert (await client.get(f"/{code}")).status_code == 302


async def test_index_and_health(client):
    assert (await client.get("/")).status_code == 200
    health = (await client.get("/health")).json()
    assert health == {"database": True, "redis": True}
