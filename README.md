## DeepExcel Demo

本项目是一个本地运行的质检报告 Demo：上传 `csv/xlsx` 检测数据，自动完成字段识别、SPC 分析、图表生成、AI 结论生成，并导出带模板的 Excel 报告。

## Back end

后端代码阅读地图见 [`api/README.md`](api/README.md)。如果只关心后端，先读那份文档，再回来看这里的启动命令。

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r api/requirements-dev.txt
$env:DEEPEXCEL_MODEL_NAME="gpt-5.4"
$env:DEEPEXCEL_OPENAI_BASE_URL="http://your-openai-compatible-endpoint/v1"
$env:DEEPEXCEL_OPENAI_API_KEY="your-api-key"
.\.venv\Scripts\uvicorn api.app.main:app --reload --port 8000
```

`DEEPEXCEL_OPENAI_BASE_URL` 建议直接填 API 基址，例如 `http://host:port/v1`。如果只填网关根地址且路径为空，后端会自动补成 `/v1`。

## Front end

```powershell
cd web
npm install
$env:NEXT_PUBLIC_API_BASE_URL="http://127.0.0.1:8000"
npm run dev
```

## One-command local startup

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-local.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\stop-local.ps1
```

- `scripts/start-local.ps1` 会同时启动后端 `http://127.0.0.1:8000` 和前端 `http://127.0.0.1:3000`
- 脚本会把 PID 和日志写入 `outputs/dev/`
- 前端会自动使用 `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000`

## Demo flow

1. 打开 `http://127.0.0.1:3000`
2. 上传 `sample_data/out_of_spec_batch.csv`
3. 查看分析页中的 KPI、图表和 AI 摘要
4. 进入报告下载页并下载 Excel，`Summary` 页左侧展示总结，右侧根据实际图数自动排版 1~4 张图表

- `Summary` export now uses a formal report layout: title band, left-side `KPI -> Conclusion -> Risk -> Actions`, and right-side auto-arranged `1~4` charts.

## Test commands

```powershell
.\.venv\Scripts\python -m pytest api/tests -v
cd web
npm test
```

## Upstream connectivity check

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/health/upstream-check
```
