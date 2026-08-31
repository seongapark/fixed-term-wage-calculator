"""규칙에 걸리지 않은 처음 보는 종별도 유급/무급 확인 화면에 올라오는지 검증.

이런 건은 "무슨 휴가인지"조차 화면에 안 보이면 판단이
불가능하므로, 그룹에 원본 종별 문자열(raw_category)이 실려야 한다.
"""
import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.models import TargetPerson, LeaveEvent, build_event
from gui.special_leave_screen import collect_pending_groups as gui_collect
from webapp.state import collect_pending_groups as web_collect

COLLECTORS = (gui_collect, web_collect)


def _person(*raws):
    events = []
    for i, raw in enumerate(raws):
        d = date(2026, 7, 6 + i)
        events.append(build_event(raw, d, source_range=(d, d)))
    return TargetPerson(name="홍길동", events=events)


def test_unknown_category_is_collected_as_pending():
    for collect in COLLECTORS:
        groups = collect({"홍길동::": _person("듣도보도못한휴가")})
        assert len(groups) == 1, (collect, groups)
        assert groups[0]["raw_category"] == "듣도보도못한휴가", collect
        assert groups[0]["status"] is None
    print("OK: test_unknown_category_is_collected_as_pending")


def test_special_leave_and_unknown_are_separate_groups():
    for collect in COLLECTORS:
        groups = collect({"홍길동::": _person("특별휴가", "듣도보도못한휴가")})
        assert len(groups) == 2, (collect, groups)
        assert {g["raw_category"] for g in groups} == {"특별휴가", "듣도보도못한휴가"}, collect
    print("OK: test_special_leave_and_unknown_are_separate_groups")


def test_same_period_different_category_not_merged():
    """같은 사람·같은 기간이라도 종별이 다르면 한 건으로 뭉뚱그리면 안 된다."""
    d = date(2026, 7, 6)
    events = [
        LeaveEvent(raw_category="특별휴가", classified="특별휴가_미정", d=d, is_time_based=False,
                   day_weight=1.0, breaks=False, source_range=(d, d)),
        LeaveEvent(raw_category="포상휴가", classified="특별휴가_미정", d=d, is_time_based=False,
                   day_weight=1.0, breaks=False, source_range=(d, d)),
    ]
    for collect in COLLECTORS:
        groups = collect({"홍길동::": TargetPerson(name="홍길동", events=events)})
        assert len(groups) == 2, (collect, groups)
    print("OK: test_same_period_different_category_not_merged")


def test_known_categories_are_not_collected():
    for collect in COLLECTORS:
        groups = collect({"홍길동::": _person("공가", "일반병가", "지각(연가처리)", "결근")})
        assert groups == [], (collect, groups)
    print("OK: test_known_categories_are_not_collected")


if __name__ == "__main__":
    test_unknown_category_is_collected_as_pending()
    test_special_leave_and_unknown_are_separate_groups()
    test_same_period_different_category_not_merged()
    test_known_categories_are_not_collected()
    print("ALL OK")
