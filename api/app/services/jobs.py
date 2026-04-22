from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from threading import Lock, Thread
from typing import Callable
from uuid import uuid4

from api.app.agent.factory import build_report_planner
from api.app.config import get_settings
from api.app.report_models import ReportSpec
from api.app.services.analytics import compute_analysis
from api.app.services.charts import generate_chart_bundle
from api.app.services.excel import render_report
from api.app.services.ingestion import infer_field_mapping, load_source_dataframe, normalize_measurements
from api.app.storage import load_json, save_json

TASK_DEFINITIONS = [
    ("upload", "上传文件"),
    ("parse", "解析检测数据"),
    ("analyze", "执行 SPC 分析"),
    ("charts", "生成图表"),
    ("ai", "生成 AI 结论"),
    ("render", "渲染 Excel 报表"),
]

_JOB_LOCK = Lock()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _resolve_detail_status(measurement_value: float, lsl: object, usl: object) -> str:
    if lsl is None or usl is None:
        return "PASS"
    if measurement_value < float(lsl) or measurement_value > float(usl):
        return "FAIL"
    return "PASS"


def _build_empty_tasks() -> list[dict[str, object]]:
    return [{"id": task_id, "label": label, "status": "pending", "error": None} for task_id, label in TASK_DEFINITIONS]


def _job_payload_path(job_id: str) -> Path:
    settings = get_settings()
    return Path(settings.outputs_dir) / "jobs" / f"{job_id}.json"


def _set_task_status(payload: dict[str, object], task_id: str, status: str, error: str | None = None) -> None:
    tasks = payload["tasks"]
    assert isinstance(tasks, list)
    for task in tasks:
        if task["id"] == task_id:
            task["status"] = status
            task["error"] = error
            return
    raise KeyError(f"Unknown task id: {task_id}")


def _update_job(job_id: str, mutator: Callable[[dict[str, object]], None]) -> dict[str, object]:
    with _JOB_LOCK:
        path = _job_payload_path(job_id)
        payload = load_json(path)
        mutator(payload)
        payload["updated_at"] = _utc_now()
        save_json(path, payload)
        return payload


def _create_job_record(job_id: str, upload_path: Path) -> dict[str, object]:
    payload = {
        "job_id": job_id,
        "state": "queued",
        "error": None,
        "created_at": _utc_now(),
        "updated_at": _utc_now(),
        "source_file_name": upload_path.name,
        "template_id": None,
        "chart_paths": {},
        "report_spec": None,
        "report_id": None,
        "download_path": None,
        "tasks": _build_empty_tasks(),
    }
    _set_task_status(payload, "upload", "completed")
    save_json(_job_payload_path(job_id), payload)
    return payload


def _mark_job_failed(job_id: str, task_id: str, exc: Exception) -> dict[str, object]:
    return _update_job(
        job_id,
        lambda payload: (
            _set_task_status(payload, task_id, "failed", str(exc)),
            payload.update({"state": "failed", "error": str(exc)})
        ),
    )


def _build_job_payload(job_id: str, upload_path: Path) -> dict[str, object]:
    settings = get_settings()
    raw = load_source_dataframe(upload_path)
    mapping = infer_field_mapping(raw)
    normalized = normalize_measurements(raw, mapping)
    analysis = compute_analysis(normalized)
    chart_dir = Path(settings.outputs_dir) / "charts" / job_id
    chart_paths = generate_chart_bundle(normalized, analysis, chart_dir)
    planner = build_report_planner()
    report_spec = planner.plan(job_id=job_id, analysis=analysis)
    report_spec.dataset_summary["sample_count"] = len(normalized)
    report_spec.detail_rows = (
        normalized[["sample_id", "measurement_value", "lsl", "usl"]]
        .assign(
            status=lambda frame: [
                _resolve_detail_status(
                    measurement_value=float(row.measurement_value),
                    lsl=row.lsl,
                    usl=row.usl,
                )
                for row in frame.itertuples(index=False)
            ]
        )
        .drop(columns=["lsl", "usl"])
        .to_dict(orient="records")
    )

    return {
        "job_id": job_id,
        "template_id": report_spec.template_decision.template_id,
        "chart_paths": chart_paths,
        "report_spec": report_spec.model_dump(),
    }


def analyze_uploaded_file(upload_path: Path) -> dict[str, object]:
    job_id = f"JOB-{uuid4().hex[:8]}"
    job_payload = _build_job_payload(job_id, upload_path)
    payload = {
        "job_id": job_id,
        "state": "analysis_completed",
        "error": None,
        "created_at": _utc_now(),
        "updated_at": _utc_now(),
        "source_file_name": upload_path.name,
        "template_id": job_payload["template_id"],
        "chart_paths": job_payload["chart_paths"],
        "report_spec": job_payload["report_spec"],
        "report_id": None,
        "download_path": None,
        "tasks": _build_empty_tasks(),
    }
    for task_id in ["upload", "parse", "analyze", "charts", "ai"]:
        _set_task_status(payload, task_id, "completed")
    save_json(_job_payload_path(job_id), payload)
    return job_payload


def load_job(job_id: str) -> dict[str, object]:
    return load_json(_job_payload_path(job_id))


def run_job_analysis(job_id: str, upload_path: Path) -> None:
    try:
        _update_job(job_id, lambda payload: payload.update({"state": "running", "error": None}))

        _update_job(job_id, lambda payload: _set_task_status(payload, "parse", "running"))
        settings = get_settings()
        raw = load_source_dataframe(upload_path)
        mapping = infer_field_mapping(raw)
        normalized = normalize_measurements(raw, mapping)
        _update_job(job_id, lambda payload: _set_task_status(payload, "parse", "completed"))

        _update_job(job_id, lambda payload: _set_task_status(payload, "analyze", "running"))
        analysis = compute_analysis(normalized)
        _update_job(job_id, lambda payload: _set_task_status(payload, "analyze", "completed"))

        _update_job(job_id, lambda payload: _set_task_status(payload, "charts", "running"))
        chart_dir = Path(settings.outputs_dir) / "charts" / job_id
        chart_paths = generate_chart_bundle(normalized, analysis, chart_dir)
        _update_job(job_id, lambda payload: _set_task_status(payload, "charts", "completed"))

        _update_job(job_id, lambda payload: _set_task_status(payload, "ai", "running"))
        planner = build_report_planner()
        report_spec = planner.plan(job_id=job_id, analysis=analysis)
        report_spec.dataset_summary["sample_count"] = len(normalized)
        report_spec.detail_rows = (
            normalized[["sample_id", "measurement_value", "lsl", "usl"]]
            .assign(
                status=lambda frame: [
                    _resolve_detail_status(
                        measurement_value=float(row.measurement_value),
                        lsl=row.lsl,
                        usl=row.usl,
                    )
                    for row in frame.itertuples(index=False)
                ]
            )
            .drop(columns=["lsl", "usl"])
            .to_dict(orient="records")
        )

        _update_job(
            job_id,
            lambda payload: (
                _set_task_status(payload, "ai", "completed"),
                payload.update(
                    {
                        "state": "analysis_completed",
                        "template_id": report_spec.template_decision.template_id,
                        "chart_paths": chart_paths,
                        "report_spec": report_spec.model_dump(),
                    }
                )
            ),
        )
    except Exception as exc:
        pending_task = "parse"
        payload = load_job(job_id)
        tasks = payload["tasks"]
        assert isinstance(tasks, list)
        for task in tasks:
            if task["status"] == "running":
                pending_task = str(task["id"])
                break
        _mark_job_failed(job_id, pending_task, exc)


def enqueue_job_analysis(upload_path: Path) -> dict[str, object]:
    job_id = f"JOB-{uuid4().hex[:8]}"
    _create_job_record(job_id, upload_path)
    Thread(target=run_job_analysis, args=(job_id, upload_path), daemon=True).start()
    return {"job_id": job_id}


def render_job_report(job_id: str) -> dict[str, object]:
    settings = get_settings()
    job_payload = load_job(job_id)
    report_id = f"RPT-{job_id.split('-')[-1]}"
    report_path = Path(settings.outputs_dir) / "reports" / f"{report_id}.xlsx"
    render_report(
        report_spec=ReportSpec.model_validate(job_payload["report_spec"]),
        chart_paths=job_payload["chart_paths"],
        templates_root=Path("templates"),
        output_path=report_path,
    )
    return {"report_id": report_id, "download_path": str(report_path)}


def run_job_render(job_id: str) -> None:
    try:
        _update_job(job_id, lambda payload: (payload.update({"state": "rendering"}), _set_task_status(payload, "render", "running")))
        render_payload = render_job_report(job_id)
        _update_job(
            job_id,
            lambda payload: (
                _set_task_status(payload, "render", "completed"),
                payload.update(
                    {
                        "state": "completed",
                        "report_id": render_payload["report_id"],
                        "download_path": render_payload["download_path"],
                    }
                )
            ),
        )
    except Exception as exc:
        _mark_job_failed(job_id, "render", exc)


def enqueue_job_render(job_id: str) -> dict[str, object]:
    payload = load_job(job_id)
    render_task = next(task for task in payload["tasks"] if task["id"] == "render")
    if payload["state"] == "completed" or render_task["status"] == "running":
        return {"job_id": job_id}
    Thread(target=run_job_render, args=(job_id,), daemon=True).start()
    return {"job_id": job_id}
