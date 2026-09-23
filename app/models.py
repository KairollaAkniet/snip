from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class Link(Base):
    __tablename__ = "links"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    original_url: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    clicks_count: Mapped[int] = mapped_column(Integer, default=0)

    clicks: Mapped[list["Click"]] = relationship(
        back_populates="link", cascade="all, delete-orphan", passive_deletes=True
    )


class Click(Base):
    __tablename__ = "clicks"

    id: Mapped[int] = mapped_column(primary_key=True)
    link_id: Mapped[int] = mapped_column(ForeignKey("links.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    referrer: Mapped[str] = mapped_column(String(255))
    device: Mapped[str] = mapped_column(String(32))
    browser: Mapped[str] = mapped_column(String(64))
    os: Mapped[str] = mapped_column(String(64))

    link: Mapped[Link] = relationship(back_populates="clicks")
