import sys
from pathlib import Path
from datetime import date, time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import leave_engine
from core.models import build_event

# 7/1~9/30 계약: 7월 만근 -> 8/1 연가 1일(480분) 발생, 8월 만근 -> 9/1 발생
CS = date(2026, 7, 1)
CE = date(2026, 9, 30)


def _sim(events):
    windows = leave_engine.compute_monthly_leave_windows(CS, CE, events)
    return windows, leave_engine.simulate_leave_consumption(windows, events)


def test_late_out_before_accrual_not_offset():
    """발생(8/1) 전인 7/10 조퇴 4h는 가용 연가가 없어 상계 0."""
    e = build_event("조퇴", date(2026, 7, 10), time(14, 0), time(18, 0), 240)
    _, sim = _sim([e])
    assert sim.offset_by_id.get(id(e), 0) == 0
    assert sim.total_offset_minutes == 0


def test_late_out_after_accrual_offset_up_to_balance():
    """7월 만근 -> 8/1 연가 480분 발생. 8/10 조퇴 4h(240분)는 전액 상계."""
    e = build_event("지각", date(2026, 8, 10), time(9, 0), time(13, 0), 240)
    _, sim = _sim([e])
    assert sim.offset_by_id[id(e)] == 240
    assert sim.total_offset_minutes == 240


def test_late_out_shortfall_partial_offset():
    """가용 480분인데 조퇴/외출/지각 합계 600분 -> 480 상계 + 120 미상계."""
    e1 = build_event("조퇴", date(2026, 8, 10), time(13, 0), time(18, 0), 300)
    e2 = build_event("지각", date(2026, 8, 11), time(9, 0), time(14, 0), 300)
    _, sim = _sim([e1, e2])
    # 날짜순: e1(300) 먼저 480 중 300 상계, e2는 남은 180만 상계
    assert sim.offset_by_id[id(e1)] == 300
    assert sim.offset_by_id[id(e2)] == 180
    assert sim.total_offset_minutes == 480


def test_explicit_leave_consumes_before_late_out_same_pool():
    """8/1 발생 480분을, 8/5 명시적 연가(480)가 먼저 소진 -> 8/10 조퇴는 상계 0."""
    leave = build_event("연가", date(2026, 8, 5))
    late = build_event("조퇴", date(2026, 8, 10), time(14, 0), time(18, 0), 240)
    _, sim = _sim([leave, late])
    assert sim.offset_by_id.get(id(late), 0) == 0


def test_same_date_accrual_before_late_out():
    """발생일(8/1, 7월 만근분)과 같은 날짜의 조퇴는 그날 발생분(+480)이 먼저
    반영된 뒤 상계돼야 한다(정렬 종류 0 -> 2). 발생이 나중에 처리되면 상계 0이 되어 실패."""
    late = build_event("조퇴", date(2026, 8, 1), time(14, 0), time(18, 0), 240)
    _, sim = _sim([late])
    assert sim.offset_by_id[id(late)] == 240


def test_same_date_explicit_leave_before_late_out():
    """같은 날짜(8/1)에 명시적 연가(480)와 조퇴(240)가 함께 있으면 연가가 먼저
    풀을 소진(종류 1 -> 2)하므로 조퇴 상계는 0이어야 한다. 정렬이 깨져 조퇴가
    먼저면 240이 상계되어 실패."""
    leave = build_event("연가", date(2026, 8, 1))
    late = build_event("조퇴", date(2026, 8, 1), time(14, 0), time(18, 0), 240)
    _, sim = _sim([leave, late])
    assert sim.offset_by_id.get(id(late), 0) == 0


if __name__ == "__main__":
    test_late_out_before_accrual_not_offset()
    test_late_out_after_accrual_offset_up_to_balance()
    test_late_out_shortfall_partial_offset()
    test_explicit_leave_consumes_before_late_out_same_pool()
    test_same_date_accrual_before_late_out()
    test_same_date_explicit_leave_before_late_out()
    print("ALL OK")
