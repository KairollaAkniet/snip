from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import cache
from app.config import get_settings
from app.database import engine, get_db, init_db
from app.routers import links, redirect

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    yield
    await cache.get_redis().aclose()
    await engine.dispose()


app = FastAPI(title=get_settings().app_name, version="1.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(links.router)


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health", tags=["system"])
async def health(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    redis_ok = await cache.ping()
    body = {"database": db_ok, "redis": redis_ok}
    return JSONResponse(body, status_code=200 if db_ok else 503)


# Catch-all "/{code}" must be registered last so it doesn't shadow other routes.
app.include_router(redirect.router)
