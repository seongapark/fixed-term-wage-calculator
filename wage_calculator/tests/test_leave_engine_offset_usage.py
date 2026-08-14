import sys
from pathlib import Path
from datetime import date, time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import leave_engine
from core.models import build_event

CONTRACT_START = date(2026, 7, 1)
CONTRACT_END = date(2026, 9, 30)


def test_usage_events_now_include_late_out():
    """조퇴/외출/지각(시간 기재 '기타')도 window.usage_events에 포함되어야 한다."""
    e = build_event("지각", date(2026, 7, 6), time(9, 0), time(11, 0), 120)
    windows = leave_engine.compute_monthly_leave_windows(CONTRACT_START, CONTRACT_END, [e])
    assert e in windows[0].usage_events


def test_leave_usage_minutes_late_out_zero_without_map():
    """offset_map 없이는 조퇴/외출/지각의 사용분이 0(하위호환)."""
    e = build_event("조퇴", date(2026, 7, 6), time(17, 0), time(18, 0), 60)
    assert leave_engine.leave_usage_minutes(e) == 0


def test_leave_usage_minutes_late_out_uses_offset_map():
    """offset_map이 주어지면 그 상계분을 사용분으로 반환."""
    e = build_event("조퇴", date(2026, 7, 6), time(14, 0), time(18, 0), 240)
    assert leave_engine.leave_usage_minutes(e, {id(e): 240}) == 240


def test_leave_usage_minutes_explicit_leave_unchanged():
    """명시적 연가는 offset_map과 무관하게 종전 동작."""
    full = build_event("연가", date(2026, 7, 6))
    half = build_event("반일연가(오전)", date(2026, 7, 7))
    assert leave_engine.leave_usage_minutes(full) == 480
    assert leave_engine.leave_usage_minutes(half, {}) == 240


if __name__ == "__main__":
    test_usage_events_now_include_late_out()
    test_leave_usage_minutes_late_out_zero_without_map()
    test_leave_usage_minutes_late_out_uses_offset_map()
    test_leave_usage_minutes_explicit_leave_unchanged()
    print("ALL OK")
