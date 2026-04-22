from pathlib import Path


def test_local_dev_scripts_exist_and_define_expected_contract() -> None:
    start_script = Path("scripts/start-local.ps1")
    stop_script = Path("scripts/stop-local.ps1")

    assert start_script.exists()
    assert stop_script.exists()

    start_content = start_script.read_text(encoding="utf-8")
    stop_content = stop_script.read_text(encoding="utf-8")

    assert "127.0.0.1:8000" in start_content
    assert "127.0.0.1:3000" in start_content
    assert "NEXT_PUBLIC_API_BASE_URL" in start_content
    assert "outputs\\dev" in start_content
    assert "backend.pid" in start_content
    assert "frontend.pid" in start_content

    assert "backend.pid" in stop_content
    assert "frontend.pid" in stop_content
    assert "taskkill" in stop_content.lower()
