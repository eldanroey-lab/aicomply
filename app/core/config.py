from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    APP_NAME: str = "AiComply"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"

    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost/aicomply"

    def __init__(self, **data):
        super().__init__(**data)
        # Render (and other platforms) provide postgresql:// — upgrade to asyncpg driver
        if self.DATABASE_URL.startswith("postgresql://") or self.DATABASE_URL.startswith("postgres://"):
            object.__setattr__(
                self,
                "DATABASE_URL",
                self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
                               .replace("postgres://", "postgresql+asyncpg://", 1),
            )

    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/callback"

    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    MAX_UPLOAD_SIZE_MB: int = 10
    ALLOWED_EXTENSIONS: list[str] = ["pdf", "docx", "txt", "xlsx", "csv"]

    ANTHROPIC_API_KEY: Optional[str] = None

    ALERT_EMAIL_FROM: Optional[str] = None
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
