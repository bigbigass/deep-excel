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
    settings = get_settings()
    return {"status": "ok", "app": settings.app_name}


app.include_router(jobs_router)
app.include_router(health_router)
Path("outputs").mkdir(parents=True, exist_ok=True)
app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")
