import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from app.utils import RESERVED_CODES

ALIAS_RE = re.compile(r"^[A-Za-z0-9_-]{3,32}$")


class LinkCreate(BaseModel):
    url: HttpUrl
    custom_alias: str | None = Field(default=None, description="3-32 символа: буквы, цифры, _ и -")
    expires_in_days: int | None = Field(default=None, ge=1, le=365)

    @field_validator("custom_alias")
    @classmethod
    def validate_alias(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        if not ALIAS_RE.match(value):
            raise ValueError("Алиас: 3-32 символа, только буквы, цифры, _ и -")
        if value.lower() in RESERVED_CODES:
            raise ValueError("Этот алиас зарезервирован")
        return value


class LinkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    original_url: str
    short_url: str
    created_at: datetime
    expires_at: datetime | None
    clicks_count: int


class CountItem(BaseModel):
    label: str
    count: int


class LinkStats(BaseModel):
    code: str
    total_clicks: int
    clicks_by_day: list[CountItem]
    devices: list[CountItem]
    browsers: list[CountItem]
    os: list[CountItem]
    referrers: list[CountItem]
