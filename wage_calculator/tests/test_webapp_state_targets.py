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


def _loaded_state():
    state = AppState()
    state.config_obj = _config_with_survey()
    state.load_files(str(A_FILE), str(B_FILE))
    return state


def test_targets_lists_all_people():
    state = _loaded_state()
    rows = state.targets()
    assert len(rows) == 5
    assert {"key", "label", "survey_name", "contract_start", "contract_end"} <= rows[0].keys()
    print("OK: test_targets_lists_all_people")


def test_survey_names_reflects_config():
    state = _loaded_state()
    assert state.survey_names() == ["8월 정기조사"]
    print("OK: test_survey_names_reflects_config")


def test_batch_assign_sets_survey_and_contract_dates():
    state = _loaded_state()
    keys = list(state.people.keys())
    state.batch_assign(keys, "8월 정기조사")
    for person in state.people.values():
        assert person.survey_name == "8월 정기조사"
        assert person.contract_start.isoformat() == "2026-08-01"
        assert person.contract_end.isoformat() == "2026-08-31"
        assert person.contract_overridden is False
    print("OK: test_batch_assign_sets_survey_and_contract_dates")


def test_batch_assign_rejects_unknown_survey():
    state = _loaded_state()
    keys = list(state.people.keys())
    try:
        state.batch_assign(keys, "존재하지않는조사")
        assert False, "ValueError를 기대했지만 발생하지 않음"
    except ValueError:
        pass
    print("OK: test_batch_assign_rejects_unknown_survey")


def test_edit_contract_marks_overridden():
    state = _loaded_state()
    key = next(iter(state.people.keys()))
    state.edit_contract(key, "2026-08-05", "2026-08-20")
    person = state.people[key]
    assert person.contract_start.isoformat() == "2026-08-05"
    assert person.contract_end.isoformat() == "2026-08-20"
    assert person.contract_overridden is True
    print("OK: test_edit_contract_marks_overridden")


def test_prepare_calculation_rejects_invalid_month():
    state = _loaded_state()
    state.confirm_special_leave([{"paid": True, "accrual": True}] * len(state.pending_leave_groups))
    try:
        state.prepare_calculation(2026, 13)
        assert False, "ValueError를 기대했지만 발생하지 않음"
    except ValueError:
        pass
    print("OK: test_prepare_calculation_rejects_invalid_month")


def test_prepare_calculation_returns_unassigned_and_sets_work_period():
    state = _loaded_state()
    state.confirm_special_leave([{"paid": True, "accrual": True}] * len(state.pending_leave_groups))
    unassigned = state.prepare_calculation(2026, 8)
    assert state.work_year == 2026
    assert state.work_month == 8
    assert len(unassigned) == 5  # 아직 담당조사 미배정
    print("OK: test_prepare_calculation_returns_unassigned_and_sets_work_period")


if __name__ == "__main__":
    test_targets_lists_all_people()
    test_survey_names_reflects_config()
    test_batch_assign_sets_survey_and_contract_dates()
    test_batch_assign_rejects_unknown_survey()
    test_edit_contract_marks_overridden()
    test_prepare_calculation_rejects_invalid_month()
    test_prepare_calculation_returns_unassigned_and_sets_work_period()
    print("ALL OK")
