from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Snip — URL Shortener"
    base_url: str = "http://localhost:8000"
    database_url: str = "postgresql+asyncpg://shortener:shortener@localhost:5432/shortener"
    redis_url: str = "redis://localhost:6379/0"

    code_length: int = 7
    link_cache_ttl: int = 3600
    stats_cache_ttl: int = 10
    rate_limit_per_minute: int = 20


@lru_cache
def get_settings() -> Settings:
    return Settings()
