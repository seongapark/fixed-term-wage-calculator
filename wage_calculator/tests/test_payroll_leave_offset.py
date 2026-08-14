import sys
from pathlib import Path
from datetime import date, time
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import Config
from core.payroll import calc_payroll
from core.models import build_event


def _config():
    return Config({"surveys": [], "rates": {"2026": {"daily_wage": 78560, "meal_allowance": 160000}}, "holidays": []})


def _person(events, start=date(2026, 7, 1), end=date(2026, 9, 30)):
    return SimpleNamespace(
        contract_start=start, contract_end=end, events=events,
        name="테스트", birth="", ssn="", bank="", account="", survey_name="테스트조사",
    )


def _all_workdays_full_attendance(start, end, extra=None):
    """start~end 사이 평일에 대해 별도 이벤트가 없으면 만근으로 인정되므로 events는
    extra만 넣으면 된다(결근/종일공제가 없으면 그 달은 자동 만근)."""
    return list(extra or [])


def test_late_out_within_balance_not_deducted_from_salary():
    """7월 만근 -> 8/1 연가 발생. 8/10 지각 4h(240분)는 연가로 상계되어 급여 공제 0."""
    late = build_event("지각", date(2026, 8, 10), time(9, 0), time(13, 0), 240)
    r = calc_payroll(_person([late]), _config(), 2026, 8)
    assert r.leave_offset_minutes == 240
    assert r.late_out_minutes == 0          # 급여 공제분 없음
    assert r.late_out_deduction == 0
    assert r.leave_shortfall is False


def test_offset_reduces_final_month_leave_compensation():
    """마지막 달(9월) 연가보상비는 상계분(0.5일)이 빠진 잔량으로 계산된다.
    발생 2일(8/1,9/1) - 지각 0.5일 = 1.5일."""
    late = build_event("지각", date(2026, 8, 10), time(9, 0), time(13, 0), 240)
    r = calc_payroll(_person([late]), _config(), 2026, 9)
    assert abs(r.remaining_leave_days - 1.5) < 1e-9
    assert r.is_final_month
    assert r.leave_compensation > 0


def test_shortfall_deducts_excess_and_flags():
    """가용 480분인데 8월 조퇴/외출/지각 합계 600분 -> 480 상계 + 120 급여 공제 + 경고."""
    e1 = build_event("조퇴", date(2026, 8, 10), time(13, 0), time(18, 0), 300)
    e2 = build_event("지각", date(2026, 8, 11), time(9, 0), time(14, 0), 300)
    r = calc_payroll(_person([e1, e2]), _config(), 2026, 8)
    assert r.leave_offset_minutes == 480
    assert r.late_out_minutes == 120
    assert r.leave_shortfall is True
    assert r.leave_shortfall_minutes == 120
    assert r.late_out_deduction > 0


def test_no_leave_available_behaves_as_before():
    """계약 첫 달(7월), 발생 전 7/10 조퇴 4h -> 상계 0, 종전대로 전액 급여 공제."""
    late = build_event("조퇴", date(2026, 7, 10), time(14, 0), time(18, 0), 240)
    r = calc_payroll(_person([late]), _config(), 2026, 7)
    assert r.leave_offset_minutes == 0
    assert r.late_out_minutes == 240
    assert r.leave_shortfall is True
    assert r.late_out_deduction > 0


if __name__ == "__main__":
    test_late_out_within_balance_not_deducted_from_salary()
    test_offset_reduces_final_month_leave_compensation()
    test_shortfall_deducts_excess_and_flags()
    test_no_leave_available_behaves_as_before()
    print("ALL OK")
