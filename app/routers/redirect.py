from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app import services
from app.database import get_db

router = APIRouter(tags=["redirect"])

ERROR_PAGE = """<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>
<link rel="stylesheet" href="/static/style.css"></head>
<body><main class="error-page">
<div class="error-code">{status}</div><h1>{title}</h1><p>{text}</p>
<a class="btn btn-primary" href="/">На главную</a></main></body></html>"""


def error_page(status_code: int, title: str, text: str) -> HTMLResponse:
    return HTMLResponse(ERROR_PAGE.format(status=status_code, title=title, text=text), status_code=status_code)


@router.get("/{code}", include_in_schema=False)
async def follow(code: str, request: Request, background: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    link = await services.resolve(db, code)
    if link is None:
        return error_page(404, "Ссылка не найдена", "Похоже, такой короткой ссылки не существует.")
    if link.expired:
        return error_page(410, "Срок действия истёк", "Эта ссылка больше не активна.")

    background.add_task(
        services.record_click,
        link.id,
        code,
        request.headers.get("user-agent", ""),
        request.headers.get("referer"),
    )
    # 302 (not 301) so browsers don't cache the redirect and every click reaches analytics.
    return RedirectResponse(link.url, status_code=status.HTTP_302_FOUND)
