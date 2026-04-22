from fastapi import APIRouter

from api.app.services import upstream_check as upstream_check_service

router = APIRouter(prefix="/api/v1/health", tags=["health"])


@router.post("/upstream-check")
def upstream_check() -> dict[str, object]:
    return upstream_check_service.run_upstream_connectivity_check().model_dump()
