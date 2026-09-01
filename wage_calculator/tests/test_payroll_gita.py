import sys
from pathlib import Path
from datetime import date, time
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import Config
from core.models import build_event
from core.payroll import calc_payroll


def _config():
    return Config({"surveys": [], "rates": {"2026": {"daily_wage": 78560, "meal_allowance": 160000}}, "holidays": []})


def _person(events, start=date(2026, 7, 1), end=date(2026, 9, 30)):
    return SimpleNamespace(
        contract_start=start, contract_end=end, events=events,
        name="테스트", birth="", ssn="", bank="", account="", survey_name="테스트조사",
    )


def test_full_day_gita_matches_absence():
    """종일 기타 1일 = 결근 1일. 급여일수·식대해당일이 같아야 한다."""
    gita = calc_payroll(_person([build_event("기타", date(2026, 8, 10))]), _config(), 2026, 8)
    absent = calc_payroll(_person([build_event("결근", date(2026, 8, 10))]), _config(), 2026, 8)
    assert gita.absence_days == 1.0
    assert gita.total_days == absent.total_days
    assert gita.meal_eligible_days == absent.meal_eligible_days
    assert gita.total_payment == absent.total_payment


def test_full_day_gita_removes_that_week_holiday():
    baseline = calc_payroll(_person([]), _config(), 2026, 8)
    gita = calc_payroll(_person([build_event("기타", date(2026, 8, 10))]), _config(), 2026, 8)
    assert gita.weekly_holiday_days == baseline.weekly_holiday_days - 1


def test_partial_gita_deducts_time_only_and_keeps_meal():
    baseline = calc_payroll(_person([]), _config(), 2026, 8)
    e = build_event("기타", date(2026, 8, 10), time(9, 0), time(12, 0), 180)
    r = calc_payroll(_person([e]), _config(), 2026, 8)
    assert r.late_out_minutes == 180
    assert r.leave_offset_minutes == 0
    assert r.absence_days == 0
    assert r.meal_eligible_days == baseline.meal_eligible_days
    assert r.weekly_holiday_days == baseline.weekly_holiday_days


def test_partial_gita_does_not_touch_remaining_leave():
    """8월 시점 보유 연가(7월 만근분 1일)가 기타 때문에 줄지 않는다."""
    baseline = calc_payroll(_person([]), _config(), 2026, 8)
    e = build_event("기타", date(2026, 8, 10), time(9, 0), time(12, 0), 180)
    r = calc_payroll(_person([e]), _config(), 2026, 8)
    assert r.remaining_leave_days == baseline.remaining_leave_days


def test_early_leave_is_still_offset_not_deducted():
    e = build_event("조퇴", date(2026, 8, 10), time(15, 0), time(18, 0), 180)
    r = calc_payroll(_person([e]), _config(), 2026, 8)
    assert r.leave_offset_minutes == 180
    assert r.late_out_minutes == 0
    assert r.late_out_deduction == 0


def test_full_day_sick_leave_is_paid_but_loses_weekly_holiday():
    baseline = calc_payroll(_person([]), _config(), 2026, 8)
    r = calc_payroll(_person([build_event("일반병가", date(2026, 8, 10))]), _config(), 2026, 8)
    assert r.absence_days == 0
    assert r.meal_eligible_days == baseline.meal_eligible_days
    assert r.weekly_holiday_days == baseline.weekly_holiday_days - 1


def test_annual_leave_with_time_is_not_deducted():
    e = build_event("연가", date(2026, 8, 10), time(9, 0), time(12, 0), 180)
    r = calc_payroll(_person([e]), _config(), 2026, 8)
    assert r.late_out_minutes == 0
    assert r.late_out_deduction == 0


if __name__ == "__main__":
    test_full_day_gita_matches_absence()
    test_full_day_gita_removes_that_week_holiday()
    test_partial_gita_deducts_time_only_and_keeps_meal()
    test_partial_gita_does_not_touch_remaining_leave()
    test_early_leave_is_still_offset_not_deducted()
    test_full_day_sick_leave_is_paid_but_loses_weekly_holiday()
    test_annual_leave_with_time_is_not_deducted()
    print("ALL OK")
