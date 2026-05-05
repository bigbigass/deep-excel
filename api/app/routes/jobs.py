"""作业相关 HTTP 路由，负责上传、查询和触发报表渲染。

这个文件尽量保持“薄路由”：
- 路由层只做 HTTP 相关工作，比如接收文件、返回状态码、抛出 HTTPException。
- 具体业务处理都下沉到 `api.app.services.jobs`。

这样后端主流程可以被测试直接调用，而不必总是绕一圈 HTTP。
"""

from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse

from api.app.services.jobs import enqueue_job_analysis, enqueue_job_render, load_job

router = APIRouter(prefix="/api/v1", tags=["jobs"])


@router.post("/jobs")
async def create_job(file: UploadFile = File(...)) -> JSONResponse:
    """接收原始数据文件并异步启动分析任务。

    路由层先把上传流落成磁盘文件，再把文件路径交给 job 服务，
    后台线程后续都围绕这个稳定路径工作。
    """
    upload_dir = Path("outputs") / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    upload_path = upload_dir / file.filename
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
    """下载已生成的报表文件。

    这里没有再包一层业务逻辑，直接把 outputs/reports 下的目标文件返回给客户端。
    """
    report_path = Path("outputs") / "reports" / report_file_name
    return FileResponse(report_path)
