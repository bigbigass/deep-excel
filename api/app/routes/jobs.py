"""作业相关 HTTP 路由，负责上传、查询和触发报表渲染。

这个文件尽量保持“薄路由”：
- 路由层只做 HTTP 相关工作，比如接收文件、返回状态码、抛出 HTTPException。
- 具体业务处理都下沉到 `api.app.services.jobs`。

这样后端主流程可以被测试直接调用，而不必总是绕一圈 HTTP。
"""

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from api.app.services.jobs import enqueue_job_analysis, enqueue_job_render, load_job

router = APIRouter(prefix="/api/v1", tags=["jobs"])


def _safe_upload_name(file_name: str | None) -> str:
    """只保留客户端文件名，避免上传路径逃逸到 outputs 之外。"""
    candidate = Path(file_name or "upload").name
    if not candidate or candidate in {".", ".."}:
        return "upload"
    return candidate


def _resolve_report_path(report_file_name: str) -> Path:
    """把下载参数解析为 reports 目录内真实存在的 xlsx 文件。"""
    candidate = Path(report_file_name)
    if (
        not report_file_name
        or "/" in report_file_name
        or "\\" in report_file_name
        or candidate.name != report_file_name
        or candidate.suffix.lower() != ".xlsx"
    ):
        raise HTTPException(status_code=400, detail="Invalid report file name")

    reports_dir = (Path("outputs") / "reports").resolve()
    report_path = (reports_dir / candidate.name).resolve()
    if report_path.parent != reports_dir:
        raise HTTPException(status_code=400, detail="Invalid report file name")
    if not report_path.is_file():
        raise HTTPException(status_code=404, detail="Report file not found")
    return report_path


@router.post("/jobs")
async def create_job(file: UploadFile = File(...)) -> JSONResponse:
    """接收原始数据文件并异步启动分析任务。

    每次上传写入独立目录，确保不同任务上传同名文件时不会互相覆盖。
    """
    upload_dir = Path("outputs") / "uploads" / uuid4().hex
    upload_dir.mkdir(parents=True, exist_ok=False)
    upload_path = upload_dir / _safe_upload_name(file.filename)
    upload_path.write_bytes(await file.read())
    return JSONResponse(status_code=202, content=enqueue_job_analysis(upload_path))


@router.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, object]:
    """读取当前作业状态，供前端轮询任务进度。"""
    return load_job(job_id)


@router.post("/jobs/{job_id}/render")
def render_job(job_id: str) -> JSONResponse:
    """在分析完成后启动 Excel 报表渲染。

    只有 analysis 阶段已经准备好 `report_spec` 时，渲染才有意义，
    所以这里先做一次状态门禁。
    """
    job_payload = load_job(job_id)
    if job_payload["state"] not in {"analysis_completed", "rendering", "completed"}:
        raise HTTPException(status_code=409, detail="Job analysis is not ready for report rendering")
    return JSONResponse(status_code=202, content=enqueue_job_render(job_id))


@router.get("/reports/{report_file_name}")
def download_report(report_file_name: str) -> FileResponse:
    """下载 reports 目录中已经生成且通过校验的 Excel 报表。"""
    return FileResponse(_resolve_report_path(report_file_name))
