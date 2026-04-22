from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse

from api.app.services.jobs import enqueue_job_analysis, enqueue_job_render, load_job

router = APIRouter(prefix="/api/v1", tags=["jobs"])


@router.post("/jobs")
async def create_job(file: UploadFile = File(...)) -> JSONResponse:
    upload_dir = Path("outputs") / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    upload_path = upload_dir / file.filename
    upload_path.write_bytes(await file.read())
    return JSONResponse(status_code=202, content=enqueue_job_analysis(upload_path))


@router.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, object]:
    return load_job(job_id)


@router.post("/jobs/{job_id}/render")
def render_job(job_id: str) -> JSONResponse:
    job_payload = load_job(job_id)
    if job_payload["state"] not in {"analysis_completed", "rendering", "completed"}:
        raise HTTPException(status_code=409, detail="Job analysis is not ready for report rendering")
    return JSONResponse(status_code=202, content=enqueue_job_render(job_id))


@router.get("/reports/{report_file_name}")
def download_report(report_file_name: str) -> FileResponse:
    report_path = Path("outputs") / "reports" / report_file_name
    return FileResponse(report_path)
