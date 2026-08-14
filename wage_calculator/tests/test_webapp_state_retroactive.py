import sys
import tempfile
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import Config
from core.models import TargetPerson
from core.parser import person_key
from core.payroll import calc_payroll
from output.build import build_workbook
from webapp.state import AppState

FIXTURE_DIR = Path(__file__).resolve().parent.parent.parent / "demo_assets"
A_FILE = FIXTURE_DIR / "개인정보_예시(A).xlsx"
B_FILE = FIXTURE_DIR / "근무상황_예시(B).xlsx"

# 아래 값들은 _build_previous_payroll_fixture()가 온더플라이로 생성하는 전월(7월)
# 픽스처가 기록하는 값들. 홍길동: 전월(7월) 파일에는 2,000,000원으로 기록돼
# 있지만, 당월 B파일 기준으로 계약기간(2026-07-01~2026-07-31)을 재계산하면
# 2,281,120원이 나와야 한다(해당 기간에는 8월 데모 이벤트가 걸리지 않으므로
# 만근 재계산).
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


def _build_previous_payroll_fixture(tmp_dir) -> Path:
    """전월(7월) 임금내역 소급테스트용 픽스처를 임시 디렉터리에 온더플라이로 생성한다.

    프로그램이 실제로 생성하는 '임금내역(월중)' 시트 포맷을 그대로 재현해야
    core/parser.py::load_previous_payroll()이 읽을 수 있다(헤더 텍스트가 아니라
    output/wage_sheet.py의 COL 고정 열 위치를 사용하는 포맷).

    홍길동(900512-1234567)의 7월(2026-07-01~2026-07-31) 급여를 실제
    core/payroll.py::calc_payroll()로 "정상적으로" 재계산한 뒤(참고용, 실제
    기록값은 아래에서 의도적으로 다르게 덮어씀), total_payment만 실제
    계산값(2,281,120원)보다 적은 2,000,000원으로 덮어써서 기록한다. 이렇게 하면
    AppState.run_calculation()이 소급계산을 수행할 때, "전월 파일에 실제로
    기록된 값(2,000,000원)"과 "당월 B파일 기준으로 재계산한 값(2,281,120원)"이
    달라 retro_adjustments가 0이 아닌 281,120원으로 나오는지 검증할 수 있다.
    """
    config = Config({
        "surveys": [{"name": "7월 정기조사", "start": "2026-07-01", "end": "2026-07-31"}],
        "rates": {"2026": {"daily_wage": 78560, "meal_allowance": 160000}},
        "holidays": ["2026-08-15"],  # 7월에는 공휴일 없음(8월 데모 데이터와 동일한 설정 유지)
    })

    person = TargetPerson(
        name="홍길동", birth="1990-05-12", ssn="900512-1234567",
        bank="국민은행", account="110-123-456789",
        survey_name="7월 정기조사",
        contract_start=date(2026, 7, 1), contract_end=date(2026, 7, 31),
        events=[],
    )
    result = calc_payroll(person, config, 2026, 7)
    assert result.total_payment == HONG_RECALCULATED, result.total_payment
    assert result.total_payment != HONG_PREV_PAID, "의도적으로 다른 값이어야 하는데 우연히 같음"

    # 전월 파일에는 "실제 지급됐던(더 적은/다른) 금액"을 기록한다 - 소급조정액이
    # 0이 아니게 만드는 핵심 포인트.
    result.total_payment = HONG_PREV_PAID

    wb = build_workbook([result], config)
    out_path = Path(tmp_dir) / "전월임금내역_예시(7월)_소급테스트용.xlsx"
    wb.save(out_path)
    return out_path


def _ready_state_with_previous_payroll():
    with tempfile.TemporaryDirectory() as tmp_dir:
        prev_payroll_file = _build_previous_payroll_fixture(tmp_dir)
        state = AppState()
        state.config_obj = _config_with_survey()
        state.load_files(str(A_FILE), str(B_FILE), prev_payroll_path=str(prev_payroll_file))
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


def test_results_summary_applies_retro_so_window_matches_excel():
    """프로그램 창이 읽는 results_summary()도 소급조정액을 반영한 최종지급액을
    내보내야 한다(엑셀 build_wage_sheet의 최종지급액 = 지급총액 + 소급조정액과
    동일). 소급 대상인 홍길동은 조정액이 붙고, 전월 파일에 없던 사람은 0이라
    최종지급액 == 지급총액이어야 한다."""
    state = _ready_state_with_previous_payroll()
    errors = state.run_calculation()
    assert errors == [], errors

    hong = next(p for p in state.people.values() if p.ssn == HONG_SSN)
    hong_key = person_key(hong.name, hong.birth)

    summary = state.results_summary()
    hong_row = next(r for r in summary if r["key"] == hong_key)

    assert hong_row["retro_adjustment"] == HONG_EXPECTED_ADJUSTMENT, hong_row
    assert hong_row["final_payment"] == hong_row["total_payment"] + HONG_EXPECTED_ADJUSTMENT, hong_row

    # 전월 파일에 없던 사람(소급 대상 아님)은 조정 0, 최종 == 지급총액.
    non_retro_rows = [r for r in summary if r["key"] != hong_key]
    assert non_retro_rows, "비교용 비소급 대상자가 있어야 함"
    for r in non_retro_rows:
        assert r["retro_adjustment"] == 0, r
        assert r["final_payment"] == r["total_payment"], r

    print("OK: test_results_summary_applies_retro_so_window_matches_excel")


if __name__ == "__main__":
    test_load_files_populates_previous_payroll_from_fixture()
    test_run_calculation_computes_nonzero_retro_adjustment_end_to_end()
    test_results_summary_applies_retro_so_window_matches_excel()
    print("ALL OK")
