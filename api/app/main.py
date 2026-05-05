"""FastAPI 应用入口，负责注册路由、中间件以及静态输出目录。"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.app.config import get_settings
from api.app.routes.health import router as health_router
from api.app.routes.jobs import router as jobs_router

app = FastAPI(title="DeepExcel API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:3000",
        "http://localhost:3000",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def healthcheck() -> dict[str, str]:
    """返回最精简的进程健康状态，便于本地联调和容器探活。"""
    settings = get_settings()
    return {"status": "ok", "app": settings.app_name}


app.include_router(jobs_router)
app.include_router(health_router)
# 输出目录由后端统一暴露，前端可以直接下载生成的报表和图表。
Path("outputs").mkdir(parents=True, exist_ok=True)
app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")
