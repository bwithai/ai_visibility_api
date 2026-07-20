import secrets
import warnings
from typing import Literal, Self

from pydantic import PostgresDsn, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore",
    )
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = secrets.token_urlsafe(32)
    FLASK_ENV: Literal["local", "staging", "production"] = "local"

    OPENAI_API_KEY: str
    ANTHROPIC_API_KEY: str
    DATABASE_URL: str | None = None

    POSTGRES_SERVER: str = ""
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = ""
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return str(
            PostgresDsn.build(
                scheme="postgresql+psycopg",
                username=self.POSTGRES_USER,
                password=self.POSTGRES_PASSWORD,
                host=self.POSTGRES_SERVER,
                port=self.POSTGRES_PORT,
                path=self.POSTGRES_DB,
            )
        )

    def _check_default_secret(self, var_name: str, value: str | None) -> None:
        if value == "change-me":
            message = (
                f'The value of {var_name} is "change-me", '
                "for security, please change it, at least for deployments."
            )
            if self.FLASK_ENV == "local":
                warnings.warn(message, stacklevel=1)
            else:
                raise ValueError(message)

    @model_validator(mode="after")
    def _enforce_non_default_secrets(self) -> Self:
        self._check_default_secret("SECRET_KEY", self.SECRET_KEY)
        self._check_default_secret("OPENAI_API_KEY", self.OPENAI_API_KEY)
        self._check_default_secret("ANTHROPIC_API_KEY", self.ANTHROPIC_API_KEY)

        if self.DATABASE_URL:
            self._check_default_secret("DATABASE_URL", self.DATABASE_URL)
        else:
            if not self.POSTGRES_SERVER or not self.POSTGRES_USER:
                raise ValueError(
                    "Either DATABASE_URL or POSTGRES_SERVER and POSTGRES_USER must be set"
                )
            self._check_default_secret("POSTGRES_PASSWORD", self.POSTGRES_PASSWORD)

        return self


settings = Settings()  # type: ignore
# print(settings.model_dump())