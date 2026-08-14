import sys
from pathlib import Path
from datetime import date, time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import leave_engine
from core.models import build_event


# 계약기간을 넉넉히 잡아 첫 만근구간(7/1~7/31)이 계약경계로 잘리지 않도록 함
CONTRACT_START = date(2026, 7, 1)
CONTRACT_END = date(2026, 8, 31)
WORKDAY = date(2026, 7, 6)  # 월요일


def _first_window(events):
    windows = leave_engine.compute_monthly_leave_windows(CONTRACT_START, CONTRACT_END, events)
    return windows[0]


def test_partial_early_leave_still_accrues():
    """조퇴로 1시간만 비운 날이 있어도(하루 통으로 빠진 게 아니면) 그 달은
    만근으로 인정되어 연가 1일이 발생해야 한다(주휴와 동일 기준)."""
    events = [build_event("조퇴", WORKDAY, time(17, 0), time(18, 0), 60)]
    w = _first_window(events)
    assert w.full_attendance, "1시간 조퇴는 만근을 깨면 안 됨"
    assert w.accrued, "만근이면 연가 1일이 발생해야 함"
    print("OK: test_partial_early_leave_still_accrues")


def test_full_day_absence_breaks_accrual():
    """종일 결근이 하루라도 있으면 만근이 깨져 연가가 발생하지 않아야 한다."""
    events = [build_event("결근", WORKDAY)]
    w = _first_window(events)
    assert not w.full_attendance, "종일 결근은 만근을 깨야 함"
    assert not w.accrued, "만근이 깨지면 연가가 발생하면 안 됨"
    print("OK: test_full_day_absence_breaks_accrual")


def test_all_day_deducted_by_early_leave_breaks_accrual():
    """조퇴/외출로 소정근로 8시간(480분)을 전부 비운 날은 실근무 0분이므로
    주휴와 동일하게 만근을 깨야 한다(연가 미발생)."""
    events = [build_event("조퇴", WORKDAY, time(9, 0), time(18, 0), 480)]
    w = _first_window(events)
    assert not w.full_attendance, "8시간 전부 공제된 날은 실근무 0분이라 만근을 깨야 함"
    assert not w.accrued, "만근이 깨지면 연가가 발생하면 안 됨"
    print("OK: test_all_day_deducted_by_early_leave_breaks_accrual")


if __name__ == "__main__":
    test_partial_early_leave_still_accrues()
    test_full_day_absence_breaks_accrual()
    test_all_day_deducted_by_early_leave_breaks_accrual()
    print("ALL OK")
