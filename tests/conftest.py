import os
import tempfile
from pathlib import Path

# Must be set before the app is imported: the engine is created at import time.
TEST_DB = Path(tempfile.gettempdir()) / "url_shortener_test.db"
TEST_DB.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB.as_posix()}"
os.environ["RATE_LIMIT_PER_MINUTE"] = "5"

import fakeredis  # noqa: E402
import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app import cache  # noqa: E402
from app.database import Base, engine, init_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
async def redis():
    client = fakeredis.FakeAsyncRedis(decode_responses=True)
    cache.set_redis(client)
    yield client
    await client.aclose()
    cache.set_redis(None)


@pytest.fixture
async def client(redis):
    await init_db()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
