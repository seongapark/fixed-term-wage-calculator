import sys
from pathlib import Path
from datetime import date, time
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import Config
from core.models import build_event
from webapp.state import AppState


def _state_with_person(events, work_month=7):
    state = AppState()
    state.config_obj = Config({"surveys": [], "rates": {"2026": {"daily_wage": 78560, "meal_allowance": 160000}}, "holidays": []})
    state.work_year, state.work_month = 2026, work_month
    p = SimpleNamespace(
        contract_start=date(2026, 7, 1), contract_end=date(2026, 9, 30), events=events,
        name="김테스트", birth="1990-01-01", ssn="", bank="", account="", survey_name="테스트조사",
    )
    state.people = {"김테스트::19900101": p}
    return state


def test_shortfall_with_offset_produces_warning():
    """7월 만근 -> 8/1 연가 480분 발생. 8월 조퇴/지각 합계 600분 -> 480 상계 + 120 초과.
    연가가 실제로 상계됐고(offset>0) 부족하므로 경고가 뜬다."""
    events = [
        build_event("조퇴", date(2026, 8, 10), time(13, 0), time(18, 0), 300),
        build_event("지각", date(2026, 8, 11), time(9, 0), time(14, 0), 300),
    ]
    state = _state_with_person(events, work_month=8)
    state.run_calculation()
    assert any("김테스트" in w for w in state.leave_warnings)


def test_pre_accrual_deduction_does_not_warn():
    """발생 전(연가 0) 7/10 조퇴 4h는 상계 없이(offset=0) 종전처럼 급여 공제만 된다.
    이 경우 팝업 경고를 띄우지 않는다."""
    late = build_event("조퇴", date(2026, 7, 10), time(14, 0), time(18, 0), 240)
    state = _state_with_person([late], work_month=7)
    state.run_calculation()
    assert state.leave_warnings == []


def test_no_warning_when_fully_offset():
    """가용 연가 내 상계면 경고 없음(8월 계산)."""
    late = build_event("지각", date(2026, 8, 10), time(9, 0), time(13, 0), 240)
    state = _state_with_person([late], work_month=8)
    state.run_calculation()
    assert state.leave_warnings == []


def test_evidence_late_out_rows_reconcile():
    """증거자료 조퇴외출: 각 행 사용(분)=연가상계+급여공제, 합계도 동일하게 맞는다."""
    events = [
        build_event("조퇴", date(2026, 8, 10), time(13, 0), time(18, 0), 300),
        build_event("지각", date(2026, 8, 11), time(9, 0), time(14, 0), 300),
    ]
    state = _state_with_person(events, work_month=8)
    state.run_calculation()
    ev = state.evidence_for("김테스트::1990-01-01")
    for row in ev["late_out"]:
        assert row["minutes"] == row["offset_minutes"] + row["deducted_minutes"]
    assert ev["late_out_used_total_minutes"] == ev["late_out_offset_total_minutes"] + ev["late_out_total_minutes"]
    assert ev["late_out_offset_total_minutes"] == 480
    assert ev["late_out_total_minutes"] == 120


if __name__ == "__main__":
    test_shortfall_with_offset_produces_warning()
    test_pre_accrual_deduction_does_not_warn()
    test_no_warning_when_fully_offset()
    test_evidence_late_out_rows_reconcile()
    print("ALL OK")
