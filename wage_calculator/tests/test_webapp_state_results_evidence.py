import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import Config
from webapp.state import AppState

FIXTURE_DIR = Path(__file__).resolve().parent.parent.parent / "demo_assets"
A_FILE = FIXTURE_DIR / "개인정보_예시(A).xlsx"
B_FILE = FIXTURE_DIR / "근무상황_예시(B).xlsx"


def _config_with_survey():
    return Config({
        "surveys": [{"name": "8월 정기조사", "start": "2026-08-01", "end": "2026-08-31"}],
        "rates": {"2026": {"daily_wage": 78560, "meal_allowance": 160000}},
        "holidays": ["2026-08-15"],
    })


def _calculated_state():
    state = AppState()
    state.config_obj = _config_with_survey()
    state.load_files(str(A_FILE), str(B_FILE))
    state.confirm_special_leave(["유급특별휴가"])
    keys = list(state.people.keys())
    state.batch_assign(keys, "8월 정기조사")
    state.prepare_calculation(2026, 8)
    state.run_calculation()
    return state


def test_results_summary_has_five_rows_with_expected_keys():
    state = _calculated_state()
    rows = state.results_summary()
    assert len(rows) == 5
    expected_keys = {"key", "label", "survey", "period", "total_days",
                      "weekly_holiday_days", "remaining_leave_days", "total_payment"}
    assert expected_keys <= rows[0].keys()
    print("OK: test_results_summary_has_five_rows_with_expected_keys")


def test_evidence_names_matches_results_count():
    state = _calculated_state()
    names = state.evidence_names()
    assert len(names) == 5
    assert {"key", "label"} <= names[0].keys()
    print("OK: test_evidence_names_matches_results_count")


def test_evidence_for_returns_none_for_unknown_key():
    state = _calculated_state()
    assert state.evidence_for("존재하지않음::19000101") is None
    print("OK: test_evidence_for_returns_none_for_unknown_key")


def test_evidence_for_known_person_has_all_sections():
    state = _calculated_state()
    key = state.evidence_names()[0]["key"]
    data = state.evidence_for(key)
    assert set(data.keys()) == {
        "raw_rows", "weekly", "late_out", "late_out_total_minutes",
        "meal", "leave", "leave_final",
    }
    assert isinstance(data["raw_rows"], list)
    assert "remaining_leave_days" in data["leave_final"]
    print("OK: test_evidence_for_known_person_has_all_sections")


if __name__ == "__main__":
    test_results_summary_has_five_rows_with_expected_keys()
    test_evidence_names_matches_results_count()
    test_evidence_for_returns_none_for_unknown_key()
    test_evidence_for_known_person_has_all_sections()
    print("ALL OK")
