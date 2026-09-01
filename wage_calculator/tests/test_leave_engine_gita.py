import sys
from pathlib import Path
from datetime import date, time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.leave_engine import (
    compute_monthly_leave_windows,
    compute_weekly_holiday_windows,
    simulate_leave_consumption,
    weekly_holidays_for_month,
)
from core.models import build_event

START = date(2026, 7, 1)
END = date(2026, 9, 30)


def _weekly(events):
    return compute_weekly_holiday_windows(START, END, events)


def test_full_day_gita_breaks_that_week_holiday():
    """2026-08-10(월) 종일 기타 -> 그 주 창의 주휴가 발생하지 않는다."""
    events = [build_event("기타", date(2026, 8, 10))]
    granted = [w for w in _weekly(events) if w.start <= date(2026, 8, 10) <= w.effective_end]
    assert granted and granted[0].granted is False


def test_full_day_gita_breaks_monthly_full_attendance():
    events = [build_event("기타", date(2026, 8, 10))]
    windows = compute_monthly_leave_windows(START, END, events)
    hit = [w for w in windows if w.start <= date(2026, 8, 10) <= w.effective_end]
    assert hit and hit[0].accrued is False


def test_partial_gita_keeps_full_attendance():
    events = [build_event("기타", date(2026, 8, 10), time(9, 0), time(12, 0), 180)]
    windows = compute_monthly_leave_windows(START, END, events)
    hit = [w for w in windows if w.start <= date(2026, 8, 10) <= w.effective_end]
    assert hit and hit[0].accrued is True
    assert weekly_holidays_for_month(_weekly(events), 2026, 8) > 0


def test_gita_is_not_offset_by_remaining_leave():
    """7월 만근으로 8/1 연가 발생이 있어도 기타는 상계되지 않는다."""
    e = build_event("기타", date(2026, 8, 10), time(9, 0), time(12, 0), 180)
    windows = compute_monthly_leave_windows(START, END, [e])
    consumption = simulate_leave_consumption(windows, [e])
    assert consumption.total_offset_minutes == 0
    assert consumption.offset_by_id == {}


def test_early_leave_is_still_offset():
    e = build_event("조퇴", date(2026, 8, 10), time(15, 0), time(18, 0), 180)
    windows = compute_monthly_leave_windows(START, END, [e])
    consumption = simulate_leave_consumption(windows, [e])
    assert consumption.total_offset_minutes == 180


def test_full_day_sick_leave_still_breaks_attendance():
    events = [build_event("일반병가", date(2026, 8, 10))]
    windows = compute_monthly_leave_windows(START, END, events)
    hit = [w for w in windows if w.start <= date(2026, 8, 10) <= w.effective_end]
    assert hit and hit[0].accrued is False


if __name__ == "__main__":
    test_full_day_gita_breaks_that_week_holiday()
    test_full_day_gita_breaks_monthly_full_attendance()
    test_partial_gita_keeps_full_attendance()
    test_gita_is_not_offset_by_remaining_leave()
    test_early_leave_is_still_offset()
    test_full_day_sick_leave_still_breaks_attendance()
    print("ALL OK")
