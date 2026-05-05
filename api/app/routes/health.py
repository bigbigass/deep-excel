"""健康检查路由，包括本地服务状态和上游模型连通性。"""

from fastapi import APIRouter

from api.app.services import upstream_check as upstream_check_service

router = APIRouter(prefix="/api/v1/health", tags=["health"])


@router.post("/upstream-check")
def upstream_check() -> dict[str, object]:
    """主动探测上游模型服务是否可访问，并返回诊断信息。"""
    return upstream_check_service.run_upstream_connectivity_check().model_dump()
