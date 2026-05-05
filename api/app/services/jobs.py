"""作业服务，负责串联上传解析、分析、图表生成和报表渲染。

这个模块基本就是后端主流程的“总导演”：
1. 接住上传后的原始文件。
2. 调用字段识别和数据标准化，把输入整理成统一结构。
3. 基于标准化数据计算 SPC 指标并生成图表。
4. 调用 AI 规划报表内容和模板。
5. 把每个阶段的状态持续写回磁盘，供前端轮询展示。

因为这里会被后台线程并发读写，所以大部分状态更新都通过 `_update_job()`
这个统一入口完成，避免任务文件被不同线程交叉覆盖。
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from threading import Lock, Thread
from typing import Callable
from uuid import uuid4

from api.app.agent.factory import build_report_planner
from api.app.agent.field_mapping_planner import build_field_mapping_planner
from api.app.config import get_settings
from api.app.report_models import ReportSpec
from api.app.schemas import JobTask
from api.app.services.analytics import compute_analysis
from api.app.services.charts import generate_chart_bundle
from api.app.services.excel import render_report
from api.app.services.ingestion import load_source_dataframe, normalize_measurements
from api.app.storage import load_json, save_json

TASK_DEFINITIONS = [
    ("upload", "\u4e0a\u4f20\u6587\u4ef6"),
    ("parse", "\u89e3\u6790\u68c0\u6d4b\u6570\u636e"),
    ("analyze", "\u6267\u884c SPC \u5206\u6790"),
    ("charts", "\u751f\u6210\u56fe\u8868"),
    ("ai", "\u751f\u6210 AI \u7ed3\u8bba"),
    ("render", "\u6e32\u67d3 Excel \u62a5\u8868"),
]

# 前端进度条展示顺序和后端状态流转顺序保持一致。
_JOB_LOCK = Lock()
# `reasoning` 字段是可选字段，这个哨兵对象用来区分“明确写入 None”和“本次不更新”。
_REASONING_UNSET = object()


def _utc_now() -> str:
    """返回统一的 UTC ISO 时间戳。

    所有作业状态文件都使用同一种时间格式，前端可以直接展示或比较更新时间。
    """
    return datetime.now(UTC).isoformat()


def _resolve_detail_status(measurement_value: float, lsl: object, usl: object) -> str:
    """根据规格上下限给明细行打 PASS/FAIL 标签。

    明细页的状态判断故意保持简单：只看当前测量值是否落在规格范围内。
    控制限异常、趋势异常等更复杂的判断留给统计分析和 AI 叙述层处理。
    """
    if lsl is None or usl is None:
        return "PASS"
    if measurement_value < float(lsl) or measurement_value > float(usl):
        return "FAIL"
    return "PASS"


def _build_empty_tasks() -> list[dict[str, object]]:
    """初始化前端任务看板需要的默认步骤。

    这里直接复用 `JobTask` 模型导出字典，保证接口返回结构和前端类型约定一致。
    """
    return [
        JobTask(id=task_id, label=label, status="pending", error=None, reasoning=None).model_dump()
        for task_id, label in TASK_DEFINITIONS
    ]


def _job_payload_path(job_id: str) -> Path:
    """计算作业状态文件在 outputs 下的落盘路径。

    每个 job 对应一个独立 JSON 文件，便于调试时直接打开查看完整状态。
    """
    settings = get_settings()
    return Path(settings.outputs_dir) / "jobs" / f"{job_id}.json"


def _set_task_status(
    payload: dict[str, object],
    task_id: str,
    status: str,
    error: str | None = None,
    reasoning: object = _REASONING_UNSET,
) -> None:
    """更新单个步骤的状态、错误信息和可选推理文本。

    任务数组是前端直接消费的数据结构，所以这里不重建整个 tasks 列表，
    而是原地修改目标任务，尽量减少状态更新逻辑的分散。
    """
    tasks = payload["tasks"]
    assert isinstance(tasks, list)
    for task in tasks:
        if task["id"] == task_id:
            task["status"] = status
            task["error"] = error
            if reasoning is not _REASONING_UNSET:
                task["reasoning"] = reasoning
            return
    raise KeyError(f"Unknown task id: {task_id}")


def _update_job(job_id: str, mutator: Callable[[dict[str, object]], None]) -> dict[str, object]:
    """在全局锁保护下读取、修改并落盘作业状态。

    调用方只需要提供“怎么改 payload”，不用关心文件读写、时间戳刷新和并发保护。
    这样可以把所有状态更新都收敛到一个入口，避免后台线程互相覆盖写入结果。
    """
    with _JOB_LOCK:
        path = _job_payload_path(job_id)
        payload = load_json(path)
        mutator(payload)
        payload["updated_at"] = _utc_now()
        save_json(path, payload)
        return payload


def _create_job_record(job_id: str, upload_path: Path) -> dict[str, object]:
    """为新上传的文件创建初始作业记录。

    上传文件写入磁盘后，就立即创建一份 job 记录，让前端可以马上拿到 job_id
    并开始轮询，而不用等后续解析和分析全部完成。
    """
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
    """把指定步骤标记为失败，并同步更新整体作业状态。

    这里同时写两层信息：
    - 任务级别：哪个步骤失败了。
    - 作业级别：整个 job 已经失败，前端可以停止继续等待。
    """
    return _update_job(
        job_id,
        lambda payload: (
            _set_task_status(payload, task_id, "failed", str(exc)),
            payload.update({"state": "failed", "error": str(exc)}),
        ),
    )


def _parse_uploaded_measurements(upload_path: Path) -> tuple[object, str]:
    """读取原始文件，调用 AI 识别字段，再输出标准化数据。

    返回值里除了标准化后的 DataFrame，还会带上一段中文 reasoning，
    这段解释会直接展示给前端，告诉用户 AI 是如何理解源表结构的。
    """
    raw = load_source_dataframe(upload_path)
    planner = build_field_mapping_planner()
    mapping, reasoning = planner.plan(raw, upload_path.name)
    normalized = normalize_measurements(raw, mapping)
    return normalized, reasoning


def _build_detail_rows(normalized) -> list[dict[str, object]]:
    """把标准化数据裁剪成报表明细页所需的列。

    这里输出的是最适合 Excel 明细页直接写入的行结构，不再保留分析阶段使用的
    额外列和中间状态，避免报表模板依赖内部计算细节。
    """
    return (
        normalized[["sample_id", "measurement_value", "lsl", "usl"]]
        .assign(
            status=lambda frame: [
                # 明细页直接给出 PASS/FAIL，便于客户演示时快速定位异常点。
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


def _build_job_payload(job_id: str, upload_path: Path) -> dict[str, object]:
    """执行完整分析链路，并返回可落盘的核心结果。

    这是“同步版主流程”，把一个文件从原始输入一路处理到可生成报表的状态：
    标准化数据 -> 统计分析 -> 图表生成 -> AI 规划 -> 报表规格整理。
    测试里更适合直接调用这个方法，因为它不会引入线程时序问题。
    """
    settings = get_settings()
    normalized, parse_reasoning = _parse_uploaded_measurements(upload_path)
    analysis = compute_analysis(normalized)
    # 图表按 job_id 落到独立目录，避免多个作业之间互相覆盖图片文件。
    chart_dir = Path(settings.outputs_dir) / "charts" / job_id
    chart_paths = generate_chart_bundle(normalized, analysis, chart_dir)
    planner = build_report_planner()
    report_spec = planner.plan(job_id=job_id, analysis=analysis)
    # `ReportSpec` 由 AI 规划得到，但样本数和明细行这类“确定性数据”
    # 仍然由代码补齐，避免模型胡编。
    report_spec.dataset_summary["sample_count"] = len(normalized)
    report_spec.detail_rows = _build_detail_rows(normalized)

    return {
        "job_id": job_id,
        "template_id": report_spec.template_decision.template_id,
        "chart_paths": chart_paths,
        "report_spec": report_spec.model_dump(),
        "parse_reasoning": parse_reasoning,
    }


def analyze_uploaded_file(upload_path: Path) -> dict[str, object]:
    """同步执行一轮分析，主要用于测试或无队列场景。

    相比 `enqueue_job_analysis()`，这个函数不会起后台线程，
    更适合在单元测试里验证完整处理结果。
    """
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
    _set_task_status(payload, "upload", "completed")
    _set_task_status(payload, "parse", "completed", reasoning=job_payload["parse_reasoning"])
    for task_id in ["analyze", "charts", "ai"]:
        _set_task_status(payload, task_id, "completed")
    save_json(_job_payload_path(job_id), payload)
    return job_payload


def load_job(job_id: str) -> dict[str, object]:
    """读取已有作业状态。

    读操作同样走锁，是为了避免恰好读到另一个线程写入中的半成品状态。
    """
    with _JOB_LOCK:
        return load_json(_job_payload_path(job_id))


def run_job_analysis(job_id: str, upload_path: Path) -> None:
    """后台线程入口，分阶段更新分析任务状态。

    这个函数刻意把每一步拆开写状态：
    - parse: 识别字段并标准化
    - analyze: 计算 SPC 指标
    - charts: 生成图片
    - ai: 生成中文结论和模板决策

    这样前端不仅知道“有没有完成”，还知道当前卡在什么阶段。
    """
    try:
        # 整个 job 进入运行态，但具体执行到哪一步由 tasks 数组表达。
        _update_job(job_id, lambda payload: payload.update({"state": "running", "error": None}))

        _update_job(job_id, lambda payload: _set_task_status(payload, "parse", "running"))
        settings = get_settings()
        normalized, parse_reasoning = _parse_uploaded_measurements(upload_path)
        _update_job(
            job_id,
            lambda payload: _set_task_status(payload, "parse", "completed", reasoning=parse_reasoning),
        )

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
        report_spec.detail_rows = _build_detail_rows(normalized)

        _update_job(
            job_id,
            lambda payload: (
                _set_task_status(payload, "ai", "completed"),
                # 一旦 AI 阶段完成，前端分析页展示所需的核心数据就齐了。
                payload.update(
                    {
                        "state": "analysis_completed",
                        "template_id": report_spec.template_decision.template_id,
                        "chart_paths": chart_paths,
                        "report_spec": report_spec.model_dump(),
                    }
                ),
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
    """创建作业记录并启动后台分析线程。

    这里返回给前端的只有 job_id。真正的分析工作在线程里继续跑，
    前端通过轮询 `/jobs/{job_id}` 获取后续状态。
    """
    job_id = f"JOB-{uuid4().hex[:8]}"
    _create_job_record(job_id, upload_path)
    Thread(target=run_job_analysis, args=(job_id, upload_path), daemon=True).start()
    return {"job_id": job_id}


def render_job_report(job_id: str) -> dict[str, object]:
    """把已完成分析的作业渲染成 Excel 报表。

    到这里统计分析已经完成，所以只做一件事：
    把 `report_spec` 和图表路径交给 Excel 渲染服务，生成最终文件。
    """
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
    """后台线程入口，负责执行报表渲染并更新最终状态。

    渲染过程和分析过程分开，前端可以先展示分析结论，再由用户决定是否生成 Excel。
    """
    try:
        _update_job(
            job_id,
            lambda payload: (payload.update({"state": "rendering"}), _set_task_status(payload, "render", "running")),
        )
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
                ),
            ),
        )
    except Exception as exc:
        _mark_job_failed(job_id, "render", exc)


def enqueue_job_render(job_id: str) -> dict[str, object]:
    """如果当前作业允许渲染，则启动后台渲染线程。

    这里会做一个轻量幂等保护：
    - 已完成的作业不重复渲染
    - 正在渲染的作业不重复启动第二个线程
    """
    payload = load_job(job_id)
    render_task = next(task for task in payload["tasks"] if task["id"] == "render")
    if payload["state"] == "completed" or render_task["status"] == "running":
        return {"job_id": job_id}
    Thread(target=run_job_render, args=(job_id,), daemon=True).start()
    return {"job_id": job_id}
