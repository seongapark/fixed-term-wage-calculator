import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from core.config import Config
from webapp.server import create_app
from webapp.state import AppState

FIXTURE_DIR = Path(__file__).resolve().parent.parent.parent / "demo_assets"
A_FILE = FIXTURE_DIR / "개인정보_예시(A).xlsx"
B_FILE = FIXTURE_DIR / "근무상황_예시(B).xlsx"


def _client():
    state = AppState()
    state.config_obj = Config({
        "surveys": [{"name": "8월 정기조사", "start": "2026-08-01", "end": "2026-08-31"}],
        "rates": {"2026": {"daily_wage": 78560, "meal_allowance": 160000}},
        "holidays": ["2026-08-15"],
    })
    app = create_app(state)
    return TestClient(app), state


def test_upload_route_returns_pending_special_leave_flag():
    client, _ = _client()
    resp = client.post("/api/upload", json={"a_path": str(A_FILE), "b_path": str(B_FILE)})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ambiguous_names"] == []
    assert body["has_pending_special_leave"] is True
    print("OK: test_upload_route_returns_pending_special_leave_flag")


def test_upload_route_returns_400_on_missing_file():
    client, _ = _client()
    resp = client.post("/api/upload", json={"a_path": "존재하지않는파일.xlsx", "b_path": str(B_FILE)})
    assert resp.status_code == 400
    print("OK: test_upload_route_returns_400_on_missing_file")


def test_special_leave_flow_then_targets_flow():
    client, _ = _client()
    client.post("/api/upload", json={"a_path": str(A_FILE), "b_path": str(B_FILE)})

    groups_resp = client.get("/api/special-leave")
    assert groups_resp.status_code == 200
    groups = groups_resp.json()["groups"]
    # 미인식 종별(특별휴가) 1건 + 사유가 적힌 인식 종별(연가) 1건
    assert len(groups) == 2

    confirm_resp = client.post("/api/special-leave/confirm", json={"decisions": [{"paid": True, "accrual": True}] * len(groups)})
    assert confirm_resp.status_code == 200, confirm_resp.text

    targets_resp = client.get("/api/targets")
    assert targets_resp.status_code == 200
    targets_body = targets_resp.json()
    assert len(targets_body["targets"]) == 5
    assert targets_body["survey_names"] == ["8월 정기조사"]

    keys = [t["key"] for t in targets_body["targets"]]
    assign_resp = client.post("/api/targets/batch-assign", json={"keys": keys, "survey_name": "8월 정기조사"})
    assert assign_resp.status_code == 200, assign_resp.text
    assert all(t["survey_name"] == "8월 정기조사" for t in assign_resp.json()["targets"])

    edit_resp = client.post("/api/targets/contract-edit", json={"key": keys[0], "start": "2026-08-02", "end": "2026-08-25"})
    assert edit_resp.status_code == 200, edit_resp.text

    proceed_resp = client.post("/api/targets/proceed", json={"year": 2026, "month": 8})
    assert proceed_resp.status_code == 200, proceed_resp.text
    assert proceed_resp.json()["unassigned_names"] == []
    print("OK: test_special_leave_flow_then_targets_flow")


def test_reset_route_clears_state():
    client, _ = _client()
    client.post("/api/upload", json={"a_path": str(A_FILE), "b_path": str(B_FILE)})

    targets_resp = client.get("/api/targets")
    assert len(targets_resp.json()["targets"]) == 5

    reset_resp = client.post("/api/reset")
    assert reset_resp.status_code == 200, reset_resp.text
    assert reset_resp.json() == {"ok": True}

    targets_resp_after = client.get("/api/targets")
    assert len(targets_resp_after.json()["targets"]) == 0
    print("OK: test_reset_route_clears_state")


def test_proceed_route_returns_400_when_special_leave_undecided():
    client, _ = _client()
    client.post("/api/upload", json={"a_path": str(A_FILE), "b_path": str(B_FILE)})
    # 특별휴가 확정(/api/special-leave/confirm) 없이 바로 진행을 시도한다.
    resp = client.post("/api/targets/proceed", json={"year": 2026, "month": 8})
    assert resp.status_code == 400, resp.text
    print("OK: test_proceed_route_returns_400_when_special_leave_undecided")


if __name__ == "__main__":
    test_upload_route_returns_pending_special_leave_flag()
    test_upload_route_returns_400_on_missing_file()
    test_special_leave_flow_then_targets_flow()
    test_reset_route_clears_state()
    test_proceed_route_returns_400_when_special_leave_undecided()
    print("ALL OK")
