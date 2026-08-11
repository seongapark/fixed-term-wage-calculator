import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import Config
from core.parser import person_key
from webapp.state import AppState

FIXTURE_DIR = Path(__file__).resolve().parent.parent.parent / "demo_assets"
A_FILE = FIXTURE_DIR / "개인정보_예시(A).xlsx"
B_FILE = FIXTURE_DIR / "근무상황_예시(B).xlsx"
PREV_PAYROLL_FILE = FIXTURE_DIR / "전월임금내역_예시(7월)_소급테스트용.xlsx"

# 픽스처 생성 스크립트(.superpowers/sdd/build_retro_fixture.py)가 기록한 값들.
# 홍길동: 전월(7월) 파일에는 2,000,000원으로 기록돼 있지만, 당월 B파일
# 기준으로 계약기간(2026-07-01~2026-07-31)을 재계산하면 2,281,120원이
# 나와야 한다(해당 기간에는 8월 데모 이벤트가 걸리지 않으므로 만근 재계산).
HONG_SSN = "900512-1234567"
HONG_PREV_PAID = 2_000_000
HONG_RECALCULATED = 2_281_120
HONG_EXPECTED_ADJUSTMENT = HONG_RECALCULATED - HONG_PREV_PAID


def _config_with_survey():
    return Config({
        "surveys": [{"name": "8월 정기조사", "start": "2026-08-01", "end": "2026-08-31"}],
        "rates": {"2026": {"daily_wage": 78560, "meal_allowance": 160000}},
        "holidays": ["2026-08-15"],
    })


def _ready_state_with_previous_payroll():
    state = AppState()
    state.config_obj = _config_with_survey()
    state.load_files(str(A_FILE), str(B_FILE), prev_payroll_path=str(PREV_PAYROLL_FILE))
    state.confirm_special_leave(["유급특별휴가"])
    keys = list(state.people.keys())
    state.batch_assign(keys, "8월 정기조사")
    state.prepare_calculation(2026, 8)
    return state


def test_load_files_populates_previous_payroll_from_fixture():
    state = _ready_state_with_previous_payroll()
    assert HONG_SSN in state.previous_payroll
    assert state.previous_payroll[HONG_SSN]["total_payment"] == HONG_PREV_PAID
    print("OK: test_load_files_populates_previous_payroll_from_fixture")


def test_run_calculation_computes_nonzero_retro_adjustment_end_to_end():
    state = _ready_state_with_previous_payroll()
    errors = state.run_calculation()

    assert errors == [], errors
    assert state.retro_adjustments != {}

    hong = next(p for p in state.people.values() if p.ssn == HONG_SSN)
    key = person_key(hong.name, hong.birth)

    assert key in state.retro_adjustments
    assert state.retro_adjustments[key] == HONG_EXPECTED_ADJUSTMENT, state.retro_adjustments

    assert key in state.retro_details
    detail = state.retro_details[key]
    assert detail.prev_paid == HONG_PREV_PAID
    assert detail.recalculated == HONG_RECALCULATED
    assert detail.adjustment == HONG_EXPECTED_ADJUSTMENT
    print("OK: test_run_calculation_computes_nonzero_retro_adjustment_end_to_end")


if __name__ == "__main__":
    test_load_files_populates_previous_payroll_from_fixture()
    test_run_calculation_computes_nonzero_retro_adjustment_end_to_end()
    print("ALL OK")
