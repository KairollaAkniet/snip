import qrcode
import qrcode.image.svg
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import cache, services
from app.config import get_settings
from app.database import get_db
from app.models import Link
from app.schemas import LinkCreate, LinkOut, LinkStats

router = APIRouter(prefix="/api/links", tags=["links"])


def short_url(request: Request, code: str) -> str:
    return f"{str(request.base_url).rstrip('/')}/{code}"


def to_out(request: Request, link: Link) -> LinkOut:
    return LinkOut(
        code=link.code,
        original_url=link.original_url,
        short_url=short_url(request, link.code),
        created_at=services.as_utc(link.created_at),
        expires_at=services.as_utc(link.expires_at) if link.expires_at else None,
        clicks_count=link.clicks_count,
    )


async def get_link_or_404(code: str, db: AsyncSession = Depends(get_db)) -> Link:
    link = await services.get_link(db, code)
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ссылка не найдена")
    return link


@router.post("", response_model=LinkOut, status_code=status.HTTP_201_CREATED)
async def create_link(data: LinkCreate, request: Request, db: AsyncSession = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    if not await cache.allow_request(f"create:{client_ip}", get_settings().rate_limit_per_minute):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Слишком много запросов, попробуйте через минуту")
    try:
        link = await services.create_link(db, data)
    except services.AliasTakenError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Такой алиас уже занят")
    return to_out(request, link)


@router.get("", response_model=list[LinkOut])
async def list_links(request: Request, db: AsyncSession = Depends(get_db)):
    return [to_out(request, link) for link in await services.list_links(db)]


@router.get("/{code}", response_model=LinkOut)
async def get_link(request: Request, link: Link = Depends(get_link_or_404)):
    return to_out(request, link)


@router.get("/{code}/stats", response_model=LinkStats)
async def get_stats(link: Link = Depends(get_link_or_404), db: AsyncSession = Depends(get_db)):
    return await services.get_stats(db, link)


@router.get("/{code}/qr", response_class=Response)
async def get_qr(request: Request, link: Link = Depends(get_link_or_404)):
    img = qrcode.make(short_url(request, link.code), image_factory=qrcode.image.svg.SvgPathImage, border=2)
    return Response(content=img.to_string(), media_type="image/svg+xml")


@router.delete("/{code}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_link(link: Link = Depends(get_link_or_404), db: AsyncSession = Depends(get_db)):
    await services.delete_link(db, link)
