from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    encoding_secret: str
    app_title: str = "Litestar API"
    auto_verify_users: bool = False
    log_level: str = "INFO"
    database_url: str = "sqlite+aiosqlite:///db.sqlite3"

    @field_validator("encoding_secret")
    @classmethod
    def validate_secret_length(cls, v: str) -> str:
        if len(v) not in (16, 24, 32):
            raise ValueError(
                "encoding_secret must be exactly 16, 24, or 32 characters (AES key size)"
            )
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
