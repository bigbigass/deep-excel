from __future__ import annotations

from time import perf_counter
from typing import Any

from pydantic import BaseModel

from api.app.agent.factory import build_agent_model
from api.app.config import get_settings, resolve_openai_base_url


class UpstreamCheckResult(BaseModel):
    configured: bool
    reachable: bool
    model: str
    base_url: str | None
    latency_ms: int | None
    response_preview: str | None
    error: str | None


def _extract_response_preview(content: Any) -> str | None:
    if isinstance(content, str):
        return content.strip() or None
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                text = block.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
        if parts:
            return " ".join(parts)[:200]
    return None


def run_upstream_connectivity_check() -> UpstreamCheckResult:
    settings = get_settings()
    resolved_base_url = resolve_openai_base_url(settings.openai_base_url)
    if not settings.openai_api_key:
        return UpstreamCheckResult(
            configured=False,
            reachable=False,
            model=settings.model_name,
            base_url=resolved_base_url,
            latency_ms=None,
            response_preview=None,
            error="Missing DEEPEXCEL_OPENAI_API_KEY",
        )

    model = build_agent_model(timeout=15, max_retries=0)
    start = perf_counter()
    try:
        response = model.invoke([("user", "Reply with PONG only.")])
        latency_ms = int((perf_counter() - start) * 1000)
        return UpstreamCheckResult(
            configured=True,
            reachable=True,
            model=settings.model_name,
            base_url=resolved_base_url,
            latency_ms=latency_ms,
            response_preview=_extract_response_preview(response.content),
            error=None,
        )
    except Exception as exc:
        latency_ms = int((perf_counter() - start) * 1000)
        return UpstreamCheckResult(
            configured=True,
            reachable=False,
            model=settings.model_name,
            base_url=resolved_base_url,
            latency_ms=latency_ms,
            response_preview=None,
            error=str(exc),
        )
