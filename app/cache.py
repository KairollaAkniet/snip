"""Redis helpers. Every call fails soft: if Redis is down the app keeps working, just slower."""

import json
import logging
import time
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.config import get_settings

log = logging.getLogger(__name__)

_redis: Redis | None = None


def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(
            get_settings().redis_url, decode_responses=True, socket_connect_timeout=1, socket_timeout=1
        )
    return _redis


def set_redis(client: Redis | None) -> None:
    global _redis
    _redis = client


def link_key(code: str) -> str:
    return f"link:{code}"


def stats_key(code: str) -> str:
    return f"stats:{code}"


async def get_json(key: str) -> Any | None:
    try:
        raw = await get_redis().get(key)
    except RedisError as exc:
        log.warning("Redis GET failed: %s", exc)
        return None
    return json.loads(raw) if raw else None


async def set_json(key: str, value: Any, ttl: int) -> None:
    try:
        await get_redis().set(key, json.dumps(value, default=str), ex=ttl)
    except RedisError as exc:
        log.warning("Redis SET failed: %s", exc)


async def delete(*keys: str) -> None:
    try:
        await get_redis().delete(*keys)
    except RedisError as exc:
        log.warning("Redis DEL failed: %s", exc)


async def allow_request(identifier: str, limit: int, window: int = 60) -> bool:
    """Fixed-window rate limiter: at most `limit` requests per `window` seconds."""
    key = f"rl:{identifier}:{int(time.time() // window)}"
    try:
        redis = get_redis()
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, window)
    except RedisError as exc:
        log.warning("Rate limiter unavailable: %s", exc)
        return True
    return count <= limit


async def ping() -> bool:
    try:
        return bool(await get_redis().ping())
    except RedisError:
        return False
