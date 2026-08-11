import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from core.config import Config
import webapp.state as state_module
from webapp.server import create_app
from webapp.state import AppState

FIXTURE_DIR = Path(__file__).resolve().parent.parent.parent / "demo_assets"
A_FILE = FIXTURE_DIR / "개인정보_예시(A).xlsx"
B_FILE = FIXTURE_DIR / "근무상황_예시(B).xlsx"


def _ready_client(tmp_path, monkeypatch):
    monkeypatch.setattr(state_module, "downloads_dir", lambda: str(tmp_path))
    state = AppState()
    state.config_obj = Config({
        "surveys": [{"name": "8월 정기조사", "start": "2026-08-01", "end": "2026-08-31"}],
        "rates": {"2026": {"daily_wage": 78560, "meal_allowance": 160000}},
        "holidays": ["2026-08-15"],
    })
    app = create_app(state)
    client = TestClient(app)

    client.post("/api/upload", json={"a_path": str(A_FILE), "b_path": str(B_FILE)})
    client.post("/api/special-leave/confirm", json={"statuses": ["유급특별휴가"]})
    keys = [t["key"] for t in client.get("/api/targets").json()["targets"]]
    client.post("/api/targets/batch-assign", json={"keys": keys, "survey_name": "8월 정기조사"})
    client.post("/api/targets/proceed", json={"year": 2026, "month": 8})
    return client


def test_confirm_info_then_calculate_then_results(tmp_path, monkeypatch):
    client = _ready_client(tmp_path, monkeypatch)

    info_resp = client.get("/api/confirm-info")
    assert info_resp.status_code == 200
    assert info_resp.json()["holidays"] == ["2026-08-15"]

    calc_resp = client.post("/api/calculate")
    assert calc_resp.status_code == 200, calc_resp.text
    assert calc_resp.json()["errors"] == []

    results_resp = client.get("/api/results")
    assert results_resp.status_code == 200
    assert len(results_resp.json()["results"]) == 5
    print("OK: test_confirm_info_then_calculate_then_results")


def test_download_returns_saved_paths(tmp_path, monkeypatch):
    client = _ready_client(tmp_path, monkeypatch)
    client.post("/api/calculate")

    download_resp = client.post("/api/download")
    assert download_resp.status_code == 200, download_resp.text
    saved = download_resp.json()["saved_paths"]
    assert len(saved) == 1
    assert Path(saved[0]).exists()
    print("OK: test_download_returns_saved_paths")


def test_evidence_route_returns_sections_for_first_result(tmp_path, monkeypatch):
    client = _ready_client(tmp_path, monkeypatch)
    client.post("/api/calculate")
    results = client.get("/api/results").json()["results"]
    key = results[0]["key"]

    evidence_resp = client.get(f"/api/evidence?key={key}")
    assert evidence_resp.status_code == 200, evidence_resp.text
    body = evidence_resp.json()
    assert "weekly" in body and "leave" in body
    print("OK: test_evidence_route_returns_sections_for_first_result")


def test_evidence_route_returns_404_for_unknown_key(tmp_path, monkeypatch):
    client = _ready_client(tmp_path, monkeypatch)
    client.post("/api/calculate")

    resp = client.get("/api/evidence?key=없음::19000101")
    assert resp.status_code == 404
    print("OK: test_evidence_route_returns_404_for_unknown_key")
