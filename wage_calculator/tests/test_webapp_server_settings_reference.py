import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

import core.config as config_module
from core.config import Config
from webapp.server import create_app
from webapp.state import AppState


def _client(tmp_path, monkeypatch):
    monkeypatch.setattr(config_module, "config_path", lambda: tmp_path / "config.json")
    monkeypatch.setattr(config_module, "legacy_config_path", lambda: tmp_path / "legacy_config.json")
    state = AppState()
    state.config_obj = Config({"surveys": [], "rates": {}, "holidays": []})
    app = create_app(state)
    return TestClient(app), state


def test_settings_survey_crud(tmp_path, monkeypatch):
    client, state = _client(tmp_path, monkeypatch)
    add_resp = client.post("/api/settings/survey", json={"name": "9월 조사", "start": "2026-09-01", "end": "2026-09-30"})
    assert add_resp.status_code == 200, add_resp.text
    assert state.config_obj.survey_names() == ["9월 조사"]

    del_resp = client.delete("/api/settings/survey/9월 조사")
    assert del_resp.status_code == 200, del_resp.text
    assert state.config_obj.survey_names() == []
    print("OK: test_settings_survey_crud")


def test_settings_rate_crud(tmp_path, monkeypatch):
    client, state = _client(tmp_path, monkeypatch)
    add_resp = client.post("/api/settings/rate", json={"year": 2026, "daily_wage": 78560, "meal_allowance": 160000})
    assert add_resp.status_code == 200, add_resp.text
    assert state.config_obj.daily_wage_for(2026) == 78560

    del_resp = client.delete("/api/settings/rate/2026")
    assert del_resp.status_code == 200, del_resp.text
    assert state.config_obj.rate_years() == []
    print("OK: test_settings_rate_crud")


def test_settings_holiday_crud(tmp_path, monkeypatch):
    client, state = _client(tmp_path, monkeypatch)
    add_resp = client.post("/api/settings/holiday", json={"date": "2026-08-15"})
    assert add_resp.status_code == 200, add_resp.text
    assert state.config_obj.holidays == ["2026-08-15"]

    del_resp = client.delete("/api/settings/holiday/2026-08-15")
    assert del_resp.status_code == 200, del_resp.text
    assert state.config_obj.holidays == []
    print("OK: test_settings_holiday_crud")


def test_get_settings_returns_all_three_lists(tmp_path, monkeypatch):
    client, state = _client(tmp_path, monkeypatch)
    client.post("/api/settings/survey", json={"name": "9월 조사", "start": "2026-09-01", "end": "2026-09-30"})
    client.post("/api/settings/rate", json={"year": 2026, "daily_wage": 78560, "meal_allowance": 160000})
    client.post("/api/settings/holiday", json={"date": "2026-08-15"})

    resp = client.get("/api/settings")
    assert resp.status_code == 200
    body = resp.json()
    assert body["surveys"] == [{"name": "9월 조사", "start": "2026-09-01", "end": "2026-09-30"}]
    assert body["rates"] == {"2026": {"daily_wage": 78560, "meal_allowance": 160000}}
    assert body["holidays"] == ["2026-08-15"]
    print("OK: test_get_settings_returns_all_three_lists")


def test_reference_leave_guide_route_returns_full_list(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    resp = client.get("/api/reference/leave-guide")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["entries"]) >= 40
    print("OK: test_reference_leave_guide_route_returns_full_list")
