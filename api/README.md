# DeepExcel 后端阅读地图

这份文档只讲后端代码怎么读。目标是先建立全景，不替源码做逐行解释。

## 后端在做什么

上传检测数据后，后端完成这条链路：

```text
文件上传
  -> 字段识别
  -> 数据标准化
  -> SPC 统计
  -> 图表生成
  -> AI 生成中文报告规划
  -> Excel 模板渲染
```

## 推荐阅读顺序

1. `api/app/main.py`
   应用入口：注册路由、CORS、暴露 `outputs/` 静态目录。

2. `api/app/routes/jobs.py`
   HTTP 接口层：上传文件、查询任务、触发渲染、下载报告。

3. `api/app/services/jobs.py`
   主流程编排：把解析、统计、图表、AI、Excel 串起来。

4. `api/app/services/ingestion.py`
   数据入口：读取 CSV/XLSX，把源表整理成内部标准表。

5. `api/app/services/analytics.py`
   统计计算：均值、标准差、合格率、Cp/Cpk、控制限、异常。

6. `api/app/agent/factory.py`
   报表规划：让 AI 根据统计结果输出模板选择、中文摘要、风险和建议。

7. `api/app/services/excel.py`
   报表落地：把 `ReportSpec` 和图表写进 Excel 模板。

先读完这 7 个文件，再看其他辅助文件。

## 请求主线

```text
POST /api/v1/jobs
  routes/jobs.py:create_job()
  services/jobs.py:enqueue_job_analysis()
  services/jobs.py:run_job_analysis()
    load_source_dataframe()
    FieldMappingPlanner.plan()
    normalize_measurements()
    compute_analysis()
    generate_chart_bundle()
    DeepAgentPlanner.plan()
    save outputs/jobs/{job_id}.json

POST /api/v1/jobs/{job_id}/render
  services/jobs.py:enqueue_job_render()
  services/jobs.py:run_job_render()
  services/excel.py:render_report()
  save outputs/reports/{report_id}.xlsx
```

## 目录职责

```text
api/app/
  main.py                    FastAPI 入口
  config.py                  DEEPEXCEL_* 配置
  storage.py                 job JSON 读写
  schemas.py                 通用接口模型
  report_models.py           Excel 报表模型

  routes/
    jobs.py                  job/report API
    health.py                健康检查 API

  services/
    jobs.py                  主业务流程
    ingestion.py             文件读取和标准化
    analytics.py             SPC 统计
    charts.py                图表生成
    excel.py                 Excel 渲染
    excel_styles.py          Excel 样式
    templates.py             模板文件读取
    report_localization.py   中文标题和兜底文案
    upstream_check.py        上游模型连通性检查

  agent/
    field_mapping_planner.py AI 识别源表字段
    factory.py               AI 生成报表规划
    tools.py                 AI 可调用工具
    subagents.py             子代理配置
```

## 关键对象

`FieldMapping`
源表字段映射。说明哪一列是测量值、上规格限、下规格限、批次、时间等。

`normalized DataFrame`
内部标准表。后续统计、图表、Excel 都围绕 `measurement_value`、`usl`、`lsl`、`sequence_index` 等标准列工作。

`analysis`
`compute_analysis()` 返回的统计结果字典。包含 KPI、异常列表、控制限和推荐图表。

`ReportSpec`
Excel 渲染的最终输入。包含元数据、模板选择、KPI、图表、明细行和 AI 中文结论。

`job payload`
保存在 `outputs/jobs/{job_id}.json`。前端轮询看到的就是它，调试任务状态也先看它。

## AI 只做两件事

`agent/field_mapping_planner.py`
根据列名、类型、前 5 行样例，识别源表字段含义。

`agent/factory.py`
根据确定性统计结果，生成中文报告规划。

AI 输出会被代码校验。模板 ID 必须在白名单里，关键中文字段不能为空。

## 运行产物

```text
outputs/uploads/          上传的原始文件
outputs/jobs/             job 状态 JSON
outputs/charts/{job_id}/  图表 PNG
outputs/reports/          Excel 报告
```

`outputs/` 是调试入口，不是源码入口。

## 调试入口

接口不通：看 `main.py`、`routes/jobs.py`、启动日志。

job 失败：看 `outputs/jobs/{job_id}.json` 里的 `state`、`error`、`tasks`。

字段识别错：看 `agent/field_mapping_planner.py` 和 `test_field_mapping_planner.py`。

统计错：看 `services/analytics.py` 和 `test_analytics.py`。

Excel 错：先看 `report_models.py` 的 `ReportSpec`，再看 `services/excel.py` 和模板 manifest。

## 测试入口

```powershell
.\.venv\Scripts\python -m pytest api/tests -v
```

如果本机 pytest 临时目录权限异常：

```powershell
.\.venv311\Scripts\python -m pytest api/tests -v --basetemp api/tests/.tmp
```

常用定位：

```text
test_ingestion.py              文件读取和标准化
test_analytics.py              SPC 统计
test_charts.py                 图表生成
test_field_mapping_planner.py  AI 字段映射
test_agent_factory.py          AI 报表规划
test_excel_renderer.py         Excel 渲染
test_jobs.py / test_jobs_api.py job 流程和接口
```
