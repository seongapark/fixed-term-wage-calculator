import sys
from pathlib import Path
from datetime import date
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import Config
from core.payroll import calc_payroll


def _config(holidays):
    return Config({"surveys": [], "rates": {"2026": {"daily_wage": 78560, "meal_allowance": 160000}}, "holidays": holidays})


def _person():
    return SimpleNamespace(
        contract_start=date(2026, 8, 1), contract_end=date(2026, 8, 31), events=[],
        name="테스트", birth="", ssn="", bank="", account="", survey_name="테스트조사",
    )


def test_weekend_holiday_not_counted_as_paid_holiday():
    """2026-08-15는 토요일(휴무일). 유급휴일로 잡히면 안 되고 실출근도 안 줄어야 한다."""
    r = calc_payroll(_person(), _config(["2026-08-15"]), 2026, 8)
    assert r.paid_holiday_days == 0
    assert r.actual_workdays == 21   # 8월 평일 21일 전부 실출근
    assert r.total_days == 21


def test_weekday_holiday_counted_as_paid_holiday():
    """2026-08-17은 월요일(근로예정일). 유급휴일 1일로 잡히고 실출근은 20."""
    r = calc_payroll(_person(), _config(["2026-08-17"]), 2026, 8)
    assert r.paid_holiday_days == 1
    assert r.actual_workdays == 20
    assert r.total_days == 21


def test_total_pay_unchanged_by_weekend_holiday():
    """주말 공휴일 유무로 지급액(total_days 기반)은 변하지 않는다."""
    r_none = calc_payroll(_person(), _config([]), 2026, 8)
    r_sat = calc_payroll(_person(), _config(["2026-08-15"]), 2026, 8)
    assert r_none.total_days == r_sat.total_days == 21
    assert r_none.gross_pay == r_sat.gross_pay


if __name__ == "__main__":
    test_weekend_holiday_not_counted_as_paid_holiday()
    test_weekday_holiday_counted_as_paid_holiday()
    test_total_pay_unchanged_by_weekend_holiday()
    print("ALL OK")
