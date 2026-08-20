"""质量调查 AI 共用模型工厂。"""

from __future__ import annotations

from langchain_openai import ChatOpenAI

from api.app.config import get_settings, resolve_openai_base_url


def build_investigation_model(**kwargs: object) -> ChatOpenAI:
    """使用项目的 OpenAI 兼容配置创建调查模型。

    模型只负责结构化计划和证据综合；所有统计数字仍由确定性工具生成。
    """
    settings = get_settings()
    if not settings.openai_api_key:
        raise ValueError("DEEPEXCEL_OPENAI_API_KEY is required for AI investigation")

    return ChatOpenAI(
        model=settings.model_name,
        api_key=settings.openai_api_key,
        base_url=resolve_openai_base_url(settings.openai_base_url),
        **kwargs,
    )
