"""项目运行配置，统一从环境变量和 .env 文件读取。"""

from functools import lru_cache
from urllib.parse import urlsplit, urlunsplit

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """后端运行时配置模型。"""

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
    """缓存配置对象，避免每次请求重复解析环境变量。"""
    return Settings()


def resolve_openai_base_url(base_url: str | None) -> str | None:
    """规范化 OpenAI 兼容端点，确保路径至少落在 `/v1`。"""
    if not base_url:
        return base_url

    parsed = urlsplit(base_url)
    normalized_path = parsed.path.rstrip("/")
    if normalized_path in ("", "/"):
        normalized_path = "/v1"

    return urlunsplit(parsed._replace(path=normalized_path))
