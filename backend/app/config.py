from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str | None = None
    postgres_db: str | None = None
    postgres_user: str | None = None
    postgres_password: str | None = None
    postgres_host: str = "db"
    postgres_port: int = 5432

    app_host: str = "0.0.0.0"
    app_port: int = 8000

    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_use_tls: bool = True
    mail_to: str = "inform@mb180.ru"

    project_name: str = "Чат-бот «СВОй»"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str | None) -> str | None:
        if not isinstance(value, str):
            return value

        normalized = value
        if normalized.startswith("postgresql+asyncpg://"):
            normalized = normalized.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)

        # Backward compatibility for the old starter template values.
        if normalized == "postgresql+psycopg2://bot:bot@db:5432/botdb":
            return None

        return normalized

    @model_validator(mode="after")
    def populate_database_url(self) -> "Settings":
        if self.database_url:
            return self

        if self.postgres_db and self.postgres_user and self.postgres_password:
            self.database_url = (
                f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
                f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
            )
        else:
            self.database_url = "sqlite:///./data/dev.db"

        return self


settings = Settings()
