from functools import lru_cache
from urllib.parse import urlsplit, urlunsplit

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "deepexcel-api"
    app_env: str = "local"
    outputs_dir: str = "outputs"
    model_name: str = "gpt-5.4"
    openai_api_key: str | None = None
    openai_base_url: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="DEEPEXCEL_",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def resolve_openai_base_url(base_url: str | None) -> str | None:
    if not base_url:
        return base_url

    parsed = urlsplit(base_url)
    normalized_path = parsed.path.rstrip("/")
    if normalized_path in ("", "/"):
        normalized_path = "/v1"

    return urlunsplit(parsed._replace(path=normalized_path))
