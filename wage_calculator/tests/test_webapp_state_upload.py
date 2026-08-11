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


def test_load_files_populates_people_and_flags_pending_special_leave():
    state = AppState()
    result = state.load_files(str(A_FILE), str(B_FILE))

    assert len(state.people) == 5
    assert result["ambiguous_names"] == []
    assert result["has_pending_special_leave"] is True
    assert len(state.pending_leave_groups) == 1
    assert state.pending_leave_groups[0]["person_name"] == "최지은"
    print("OK: test_load_files_populates_people_and_flags_pending_special_leave")


def test_load_files_without_previous_payroll_leaves_it_empty():
    state = AppState()
    state.load_files(str(A_FILE), str(B_FILE))
    assert state.previous_payroll == {}
    print("OK: test_load_files_without_previous_payroll_leaves_it_empty")


def test_reloading_files_clears_stale_calculation_results():
    state = AppState()
    state.config_obj = _config_with_survey()
    state.load_files(str(A_FILE), str(B_FILE))
    state.confirm_special_leave(["유급특별휴가"])
    keys = list(state.people.keys())
    state.batch_assign(keys, "8월 정기조사")
    state.prepare_calculation(2026, 8)
    state.run_calculation()

    assert state.results != []
    assert state.work_year == 2026
    assert state.work_month == 8

    # 같은 AppState에 파일을 다시 업로드하면 이전 계산 결과가 남아있으면 안 된다.
    state.load_files(str(A_FILE), str(B_FILE))

    assert state.results == []
    assert state.work_year is None
    assert state.work_month is None
    assert state.retro_adjustments == {}
    assert state.retro_details == {}
    assert state.departed_results == []
    print("OK: test_reloading_files_clears_stale_calculation_results")


if __name__ == "__main__":
    test_load_files_populates_people_and_flags_pending_special_leave()
    test_load_files_without_previous_payroll_leaves_it_empty()
    test_reloading_files_clears_stale_calculation_results()
    print("ALL OK")
