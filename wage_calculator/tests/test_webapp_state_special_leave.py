import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from webapp.state import AppState

FIXTURE_DIR = Path(__file__).resolve().parent.parent.parent / "demo_assets"
A_FILE = FIXTURE_DIR / "개인정보_예시(A).xlsx"
B_FILE = FIXTURE_DIR / "근무상황_예시(B).xlsx"


def _loaded_state():
    state = AppState()
    state.load_files(str(A_FILE), str(B_FILE))
    return state


def test_special_leave_groups_includes_reason_and_note():
    state = _loaded_state()
    groups = state.special_leave_groups()
    assert len(groups) == 1
    g = groups[0]
    assert g["index"] == 0
    assert g["person_name"] == "최지은"
    assert g["start"] == "2026-08-17"
    assert g["end"] == "2026-08-18"
    assert g["reason"] == "본인결혼"
    assert g["note"] == "경조사"
    assert g["status"] is None
    print("OK: test_special_leave_groups_includes_reason_and_note")


def test_confirm_special_leave_sets_event_classification():
    state = _loaded_state()
    state.confirm_special_leave(["유급특별휴가"])
    events = state.pending_leave_groups[0]["events"]
    assert all(e.classified == "유급특별휴가" for e in events)
    print("OK: test_confirm_special_leave_sets_event_classification")


def test_confirm_special_leave_rejects_wrong_length():
    state = _loaded_state()
    try:
        state.confirm_special_leave([])
        assert False, "ValueError를 기대했지만 발생하지 않음"
    except ValueError:
        pass
    print("OK: test_confirm_special_leave_rejects_wrong_length")


def test_confirm_special_leave_rejects_empty_status():
    state = _loaded_state()
    try:
        state.confirm_special_leave([""])
        assert False, "ValueError를 기대했지만 발생하지 않음"
    except ValueError:
        pass
    print("OK: test_confirm_special_leave_rejects_empty_status")


if __name__ == "__main__":
    test_special_leave_groups_includes_reason_and_note()
    test_confirm_special_leave_sets_event_classification()
    test_confirm_special_leave_rejects_wrong_length()
    test_confirm_special_leave_rejects_empty_status()
    print("ALL OK")
