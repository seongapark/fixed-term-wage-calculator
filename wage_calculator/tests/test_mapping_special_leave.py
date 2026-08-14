import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import mapping


def test_special_leave_classifies_as_pending():
    assert mapping.classify("특별휴가") == "특별휴가_미정"
    print("OK: test_special_leave_classifies_as_pending")


def test_special_leave_does_not_break_attendance():
    assert mapping.full_day_breaks("특별휴가") is False
    print("OK: test_special_leave_does_not_break_attendance")


def test_special_leave_full_day_weight_is_one():
    assert mapping.full_day_weight("특별휴가") == 1.0
    print("OK: test_special_leave_full_day_weight_is_one")


def test_bare_early_leave_categories_classify_as_other():
    # 기간제 원본은 조퇴/외출/지각을 세부선택 없이 맨 종별로 찍어 내보낸다.
    for raw in ("조퇴", "외출", "지각"):
        assert mapping.classify(raw) == "기타", raw
    print("OK: test_bare_early_leave_categories_classify_as_other")


def test_unknown_category_still_raises():
    try:
        mapping.classify("존재하지않는종별")
        raise AssertionError("ValueError가 발생했어야 함")
    except ValueError:
        print("OK: test_unknown_category_still_raises")


if __name__ == "__main__":
    test_special_leave_classifies_as_pending()
    test_special_leave_does_not_break_attendance()
    test_special_leave_full_day_weight_is_one()
    test_bare_early_leave_categories_classify_as_other()
    test_unknown_category_still_raises()
    print("ALL OK")
