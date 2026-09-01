import sys
from pathlib import Path
from datetime import date, time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.models import build_event


def test_full_day_gita_is_unpaid_and_breaks_attendance():
    """종일 기타는 결근과 같은 모양 - 일급·식대 미지급 + 만근 깨짐."""
    e = build_event("기타", date(2026, 8, 10))
    assert e.unpaid is True
    assert e.breaks is True
    assert e.day_weight == 1.0
    assert e.is_time_based is False


def test_time_based_gita_deducts_but_keeps_attendance():
    e = build_event("기타", date(2026, 8, 10), time(9, 0), time(12, 0), 180)
    assert e.unpaid is True
    assert e.breaks is False
    assert e.day_weight == 0.0


def test_full_day_sick_leave_is_paid_but_breaks_attendance():
    e = build_event("일반병가", date(2026, 8, 10))
    assert e.unpaid is False
    assert e.breaks is True


def test_annual_and_public_leave_keep_everything():
    for name in ("연가", "반일연가", "공가"):
        e = build_event(name, date(2026, 8, 10))
        assert e.unpaid is False, name
        assert e.breaks is False, name


def test_absence_is_unpaid_and_breaks():
    e = build_event("결근", date(2026, 8, 10))
    assert e.unpaid is True
    assert e.breaks is True


def test_time_based_early_leave_is_unpaid_but_not_breaking():
    e = build_event("조퇴", date(2026, 8, 10), time(14, 0), time(18, 0), 240)
    assert e.unpaid is True
    assert e.breaks is False


def test_unknown_category_starts_undecided_and_neutral():
    e = build_event("경조사휴가", date(2026, 8, 10))
    assert e.classified == "특별휴가_미정"
    assert e.unpaid is False
    assert e.breaks is False
    assert e.decided is False


def test_source_row_is_carried():
    row = {"성명": "홍길동", "종별": "경조사휴가"}
    e = build_event("경조사휴가", date(2026, 8, 10), source_row=row)
    assert e.source_row is row


if __name__ == "__main__":
    test_full_day_gita_is_unpaid_and_breaks_attendance()
    test_time_based_gita_deducts_but_keeps_attendance()
    test_full_day_sick_leave_is_paid_but_breaks_attendance()
    test_annual_and_public_leave_keep_everything()
    test_absence_is_unpaid_and_breaks()
    test_time_based_early_leave_is_unpaid_but_not_breaking()
    test_unknown_category_starts_undecided_and_neutral()
    test_source_row_is_carried()
    print("ALL OK")
