import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import mapping


def test_nine_known_categories_classify_to_themselves():
    for name in ("연가", "반일연가", "공가", "일반병가", "결근", "조퇴", "외출", "지각", "기타"):
        assert mapping.classify(name) == name


def test_full_width_and_padding_are_normalized():
    assert mapping.classify("  연가 ") == "연가"
    assert mapping.classify("연가") == "연가"
    assert mapping.classify("ᄀ") == mapping.UNDETERMINED_SPECIAL


def test_half_day_leave_is_written_with_morning_or_afternoon():
    """현장 표기는 "반일연가(오전)"·"반일연가(오후)"다. 둘 다 반일연가로 처리한다."""
    assert mapping.classify("반일연가(오전)") == "반일연가"
    assert mapping.classify("반일연가(오후)") == "반일연가"
    assert mapping.classify("반일연가") == "반일연가"


def test_inner_spaces_do_not_break_recognition():
    """청·지청마다 공백이 들어가도 같은 종별로 본다(의미 있는 공백이 없다)."""
    assert mapping.classify("반일연가 (오전)") == "반일연가"
    assert mapping.classify("반일연가( 오후 )") == "반일연가"
    assert mapping.classify("일반 병가") == "일반병가"


def test_spaces_do_not_make_unknown_forms_match():
    """공백만 지울 뿐 괄호는 남기므로, 안 쓰는 표기는 여전히 확인 화면으로 간다."""
    assert mapping.classify("조퇴 (연가처리)") == mapping.UNDETERMINED_SPECIAL
    assert mapping.classify("반일연가(종일)") == mapping.UNDETERMINED_SPECIAL


def test_parenthesised_variants_go_to_pending():
    for name in ("일반병가(진단서미첨부)", "조퇴(연가처리)",
                 "공무상병가", "관외여행", "경조사휴가", "자녀돌봄휴가", "대체휴무"):
        assert mapping.classify(name) == mapping.UNDETERMINED_SPECIAL


def test_empty_and_none_go_to_pending():
    assert mapping.classify(None) == mapping.UNDETERMINED_SPECIAL
    assert mapping.classify("") == mapping.UNDETERMINED_SPECIAL
    assert mapping.classify("   ") == mapping.UNDETERMINED_SPECIAL


def test_classify_never_raises():
    for value in (123, object(), ["연가"]):
        assert mapping.classify(value) == mapping.UNDETERMINED_SPECIAL


def test_property_tables():
    assert mapping.UNPAID == ("결근", "조퇴", "외출", "지각", "기타")
    assert mapping.BREAKS_WHEN_FULL_DAY == ("결근", "일반병가", "기타")
    assert mapping.OFFSETTABLE == ("조퇴", "외출", "지각")
    assert mapping.LEAVE_CONSUMING == ("연가", "반일연가", "조퇴", "외출", "지각")


def test_half_day_annual_leave_weight():
    assert mapping.full_day_weight("반일연가") == 0.5
    assert mapping.full_day_weight("반일연가(오전)") == 0.5
    assert mapping.full_day_weight("반일연가(오후)") == 0.5
    assert mapping.full_day_weight("연가") == 1.0
    assert mapping.full_day_weight("기타") == 1.0


def test_is_pending():
    assert mapping.is_pending(mapping.UNDETERMINED_SPECIAL) is True
    assert mapping.is_pending("연가") is False
    assert mapping.is_pending("유급특별휴가") is False


if __name__ == "__main__":
    test_nine_known_categories_classify_to_themselves()
    test_full_width_and_padding_are_normalized()
    test_half_day_leave_is_written_with_morning_or_afternoon()
    test_inner_spaces_do_not_break_recognition()
    test_spaces_do_not_make_unknown_forms_match()
    test_parenthesised_variants_go_to_pending()
    test_empty_and_none_go_to_pending()
    test_classify_never_raises()
    test_property_tables()
    test_half_day_annual_leave_weight()
    test_is_pending()
    print("ALL OK")
