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


def _ready_state():
    state = AppState()
    state.config_obj = _config_with_survey()
    state.load_files(str(A_FILE), str(B_FILE))
    state.confirm_special_leave([{"paid": True, "accrual": True}] * len(state.pending_leave_groups))
    keys = list(state.people.keys())
    state.batch_assign(keys, "8월 정기조사")
    state.prepare_calculation(2026, 8)
    return state


def test_confirm_info_reports_holidays_and_rates():
    state = _ready_state()
    info = state.confirm_info()
    assert info["year"] == 2026
    assert info["month"] == 8
    assert info["holidays"] == ["2026-08-15"]
    assert info["daily_wage"] == 78560
    assert info["meal_allowance"] == 160000
    assert info["overridden_names"] == []
    print("OK: test_confirm_info_reports_holidays_and_rates")


def test_run_calculation_produces_results_for_all_assigned_people():
    state = _ready_state()
    errors = state.run_calculation()
    assert errors == []
    assert len(state.results) == 5
    print("OK: test_run_calculation_produces_results_for_all_assigned_people")


def test_run_calculation_skips_retroactive_when_no_previous_payroll():
    state = _ready_state()
    state.run_calculation()
    assert state.retro_adjustments == {}
    assert state.departed_results == []
    print("OK: test_run_calculation_skips_retroactive_when_no_previous_payroll")


if __name__ == "__main__":
    test_confirm_info_reports_holidays_and_rates()
    test_run_calculation_produces_results_for_all_assigned_people()
    test_run_calculation_skips_retroactive_when_no_previous_payroll()
    print("ALL OK")
