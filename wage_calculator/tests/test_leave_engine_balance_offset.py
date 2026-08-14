import sys
from pathlib import Path
from datetime import date, time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import leave_engine
from core.models import build_event

CS = date(2026, 7, 1)
CE = date(2026, 9, 30)


def test_balance_reflects_late_out_offset():
    """7월 만근 -> 8/1 480분 발생. 8/10 조퇴 4h(240) 상계 시, 8/31 시점 잔량은
    480-240=240분이어야 한다(offset_map 반영)."""
    e = build_event("조퇴", date(2026, 8, 10), time(14, 0), time(18, 0), 240)
    windows = leave_engine.compute_monthly_leave_windows(CS, CE, [e])
    sim = leave_engine.simulate_leave_consumption(windows, [e])
    balance = leave_engine.leave_balance_minutes_as_of(windows, date(2026, 8, 31), sim.offset_by_id)
    assert balance == 240


def test_balance_without_map_ignores_late_out():
    """offset_map 없이는 조퇴/외출/지각이 잔량에 영향을 주지 않아 480 그대로(하위호환)."""
    e = build_event("조퇴", date(2026, 8, 10), time(14, 0), time(18, 0), 240)
    windows = leave_engine.compute_monthly_leave_windows(CS, CE, [e])
    balance = leave_engine.leave_balance_minutes_as_of(windows, date(2026, 8, 31))
    assert balance == 480


if __name__ == "__main__":
    test_balance_reflects_late_out_offset()
    test_balance_without_map_ignores_late_out()
    print("ALL OK")
