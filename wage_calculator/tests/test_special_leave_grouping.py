import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.models import TargetPerson, LeaveEvent
from gui.special_leave_screen import collect_pending_groups


def test_same_source_range_merges_into_one_group():
    d1, d2 = date(2026, 7, 20), date(2026, 7, 21)
    events = [
        LeaveEvent(raw_category="특별휴가", classified="특별휴가_미정", d=d1, is_time_based=False,
                   day_weight=1.0, breaks=False, source_range=(d1, d2)),
        LeaveEvent(raw_category="특별휴가", classified="특별휴가_미정", d=d2, is_time_based=False,
                   day_weight=1.0, breaks=False, source_range=(d1, d2)),
        LeaveEvent(raw_category="공가", classified="공가", d=d1, is_time_based=False,
                   day_weight=1.0, breaks=False, source_range=(d1, d1)),
    ]
    person = TargetPerson(name="홍길동", events=events)
    groups = collect_pending_groups({"홍길동::": person})
    assert len(groups) == 1, f"공가는 제외, 특별휴가 2건은 한 그룹: {groups}"
    assert len(groups[0]["events"]) == 2
    assert groups[0]["start"] == d1 and groups[0]["end"] == d2
    assert groups[0]["status"] is None
    print("OK: test_same_source_range_merges_into_one_group")


def test_different_source_range_forms_separate_groups():
    d1 = date(2026, 7, 20)
    d2 = date(2026, 7, 27)
    events = [
        LeaveEvent(raw_category="특별휴가", classified="특별휴가_미정", d=d1, is_time_based=False,
                   day_weight=1.0, breaks=False, source_range=(d1, d1)),
        LeaveEvent(raw_category="특별휴가", classified="특별휴가_미정", d=d2, is_time_based=False,
                   day_weight=1.0, breaks=False, source_range=(d2, d2)),
    ]
    person = TargetPerson(name="홍길동", events=events)
    groups = collect_pending_groups({"홍길동::": person})
    assert len(groups) == 2, groups
    print("OK: test_different_source_range_forms_separate_groups")


def test_no_pending_events_returns_empty():
    events = [LeaveEvent(raw_category="공가", classified="공가", d=date(2026, 7, 1),
                          is_time_based=False, day_weight=1.0, breaks=False, source_range=(date(2026, 7, 1), date(2026, 7, 1)))]
    person = TargetPerson(name="홍길동", events=events)
    groups = collect_pending_groups({"홍길동::": person})
    assert groups == []
    print("OK: test_no_pending_events_returns_empty")


if __name__ == "__main__":
    test_same_source_range_merges_into_one_group()
    test_different_source_range_forms_separate_groups()
    test_no_pending_events_returns_empty()
    print("ALL OK")
