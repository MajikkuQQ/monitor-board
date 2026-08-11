from __future__ import annotations

from functools import lru_cache
from typing import Annotated, List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def _parse_user_ids(value: object) -> list[int]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [int(x) for x in value]
    if isinstance(value, int):
        return [value]
    text = str(value).strip()
    if not text:
        return []
    # Поддержка: 123,456  или  [123,456]
    if text.startswith("["):
        inner = text.strip("[]").strip()
        if not inner:
            return []
        return [int(part.strip()) for part in inner.split(",") if part.strip()]
    return [int(part.strip()) for part in text.split(",") if part.strip()]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    telegram_token: str
    telegram_api_base: str = "https://t.api.lookinsoft.ru"
    # NoDecode: иначе pydantic-settings пытается json.loads() и падает на "" или "1,2,3"
    allowed_user_ids: Annotated[List[int], NoDecode] = Field(default_factory=list)
    admin_api_key: str
    database_path: str = "./data/monitors.db"
    offline_threshold_sec: int = 180
    host: str = "0.0.0.0"
    port: int = 8787
    web_password: str = ""
    web_session_secret: str = ""

    @field_validator("allowed_user_ids", mode="before")
    @classmethod
    def parse_user_ids(cls, value: object) -> list[int]:
        return _parse_user_ids(value)

    @field_validator("telegram_api_base")
    @classmethod
    def strip_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")


@lru_cache
def get_settings() -> Settings:
    return Settings()
