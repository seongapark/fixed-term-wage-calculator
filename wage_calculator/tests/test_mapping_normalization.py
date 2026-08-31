"""청·지청마다 다른 종별 표기를 모두 인식하는지 검증.

근무상황 종별 안내표(webapp/static/reference/leave_category_guide.json)에 실린
47개 조합을 종별만/종별(세부선택)/세부선택만/괄호·공백 변형까지 전수로 넣어,
mapping.CATEGORY_MAP이 정한 분류대로 떨어지는지 확인한다.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import mapping

GUIDE_PATH = Path(__file__).resolve().parent.parent / "webapp" / "static" / "reference" / "leave_category_guide.json"
PENDING = mapping.UNDETERMINED_SPECIAL


def test_bare_sick_leave_is_recognized():
    """사용자 제보: 종별에 세부선택 없이 '일반병가'만 넣는 청이 있다."""
    for raw in ("일반병가", "병가", "일반병가(진단서첨부)", "일반병가(진단서미첨부)"):
        assert mapping.classify(raw) == "병가", raw
    print("OK: test_bare_sick_leave_is_recognized")


def test_partial_day_sick_leave_variants():
    for prefix in ("지각", "외출", "조퇴"):
        for sub in ("일반병가,진단서미첨부", "일반병가,진단서첨부", "일반병가"):
            assert mapping.classify(f"{prefix}({sub})") == "병가", (prefix, sub)
    print("OK: test_partial_day_sick_leave_variants")


def test_official_injury_leave_goes_to_pending():
    """공무상병가는 일반병가와 달리 유급/무급을 사람이 정한다."""
    for raw in ("공무상병가", "지각(공무상병가)", "외출(공무상병가)", "조퇴(공무상병가)"):
        assert mapping.classify(raw) == PENDING, raw
    print("OK: test_official_injury_leave_goes_to_pending")


def test_partial_day_annual_leave_variants():
    """안내표 세부선택은 '연가처리'인데 기존 매핑표에는 '조퇴(연가)'만 있었다."""
    for prefix in ("지각", "외출", "조퇴"):
        for sub in ("연가처리", "연가"):
            assert mapping.classify(f"{prefix}({sub})") == "연가", (prefix, sub)
    print("OK: test_partial_day_annual_leave_variants")


def test_separator_and_spacing_variants_are_normalized():
    variants = [
        "조퇴 (일반병가, 진단서 미첨부)",
        "조퇴（일반병가·진단서미첨부）",
        "조퇴[일반병가/진단서미첨부]",
        " 조퇴(일반병가,진단서미첨부) ",
        "조퇴-일반병가-진단서미첨부",
    ]
    for raw in variants:
        assert mapping.classify(raw) == "병가", raw
    print("OK: test_separator_and_spacing_variants_are_normalized")


def test_half_day_annual_leave():
    """반일연가는 연가 잔량을 240분만 소진하므로 별도 분류(일수 0.5)로 남긴다."""
    for raw in ("반일연가", "반일연가(오전)", "반일연가(오후)", "연가(오전)", "연가(오후)"):
        assert mapping.classify(raw) == "반일연가", raw
        assert mapping.full_day_weight(raw) == 0.5, raw
    assert mapping.classify("연가") == "연가"
    assert mapping.full_day_weight("연가") == 1.0
    print("OK: test_half_day_annual_leave")


def test_special_leave_family_goes_to_pending():
    """경조사·출산·돌봄 등은 유급/무급을 코드가 임의로 정하지 않고 사람에게 묻는다."""
    raws = [
        "특별휴가",
        "경조사휴가(결혼-본인)",
        "결혼(자녀)",
        "배우자출산",
        "사망(본인 및 배우자의 조부모·외조부모)",
        "사망(자녀와 그 자녀의 배우자)",
        "입양",
        "출산휴가(본인출산)",
        "유·사산휴가",
        "난임치료시술",
        "여성보건휴가",
        "모성보호시간",
        "육아시간",
        "수업휴가",
        "재해구호휴가",
        "포상휴가",
        "가족돌봄휴가",
        "자녀돌봄휴가",
        "임신검진휴가",
        "임신검진 동행휴가",
        "심리안정휴가",
        "장기재직휴가",
        "대체휴무",
        "당직휴무",
        "선거휴무",
        "관외여행",
    ]
    for raw in raws:
        assert mapping.classify(raw) == PENDING, raw
    print("OK: test_special_leave_family_goes_to_pending")


def test_plain_categories():
    assert mapping.classify("결근") == "결근"
    assert mapping.classify("공가") == "공가"
    assert mapping.classify("기타") == "기타"
    for raw in ("조퇴", "외출", "지각"):
        assert mapping.classify(raw) == "기타", raw
    print("OK: test_plain_categories")


def test_unknown_category_is_pending_not_error():
    """모르는 종별이라도 파일 로딩을 중단시키지 않고, 사람이 판단하도록 넘긴다."""
    assert mapping.classify("존재하지않는종별") == PENDING
    assert mapping.classify("") == PENDING
    assert mapping.is_pending(PENDING) is True
    print("OK: test_unknown_category_is_pending_not_error")


# 안내표(category, subtype) -> 기대 분류. subtype이 None이면 그 종별 전체 기본값.
GUIDE_EXPECTATION = {
    ("연가", ""): "연가",
    ("연가", "반일연가"): "반일연가",
    ("지각", "연가처리"): "연가",
    ("외출", "연가처리"): "연가",
    ("조퇴", "연가처리"): "연가",
    ("지각", None): "병가",   # 나머지 세부선택은 전부 일반병가/공무상병가
    ("외출", None): "병가",
    ("조퇴", None): "병가",
    ("병가", None): "병가",
    ("공가", None): "공가",
    ("결근", None): "결근",
    ("기타", "기타"): "기타",
    ("기타", "관외여행"): mapping.UNDETERMINED_SPECIAL,
}


def _expected(category, subtype):
    # 공무상병가는 종별과 무관하게 사람이 유급/무급을 정한다.
    if "공무상" in subtype:
        return mapping.UNDETERMINED_SPECIAL
    if (category, subtype) in GUIDE_EXPECTATION:
        return GUIDE_EXPECTATION[(category, subtype)]
    if (category, None) in GUIDE_EXPECTATION:
        return GUIDE_EXPECTATION[(category, None)]
    return mapping.UNDETERMINED_SPECIAL   # 경조사휴가·특별휴가 계열


def test_every_guide_combination_classifies_as_expected():
    """안내표 47행 x 표기 변형(종별만/세부만/조합)을 전수로 돌려 분류를 고정한다."""
    data = json.loads(GUIDE_PATH.read_text(encoding="utf-8"))
    wrong = []
    for e in data:
        cat, sub, detail = e["category"], e["subtype"], e["detail"]
        expected = _expected(cat, sub)
        candidates = set()
        if sub:
            candidates |= {sub, f"{cat}({sub})", f"{sub}({cat})"}
        else:
            candidates.add(cat)
        if sub and detail:
            candidates |= {f"{sub}({detail})", f"{cat}({sub},{detail})", f"{sub},{detail}"}
        if detail and not sub:
            candidates.add(f"{cat}({detail})")
        for raw in candidates:
            actual = mapping.classify(raw)
            if actual != expected:
                wrong.append((raw, actual, expected))
    assert not wrong, f"분류가 기대와 다름 (원문, 실제, 기대): {wrong}"
    print("OK: test_every_guide_combination_classifies_as_expected")


# 안내표 "공제"(연가일수에서 깎음)에 대응하는 분류.
# 결근은 여기 들어 있지만 실제로 연가 잔량을 차감하지는 않는다 - 무단결근이라
# 그날 일급·식대를 아예 안 주므로 연가까지 깎으면 이중 불이익이기 때문이다
# (leave_engine._consumes_leave_candidate 참고). 이 테스트는 종별이 어느
# 분류로 가는지만 고정하고, 실제 차감 정책은 leave_engine이 정한다.
LEAVE_CONSUMING = {"연가", "반일연가", "결근"}


def _guide_raws(entry):
    """안내표 1행을 실제 B파일에 찍힐 법한 종별 문자열들로 펼친다."""
    cat, sub = entry["category"], entry["subtype"]
    if not sub:
        return [cat]
    return [sub, f"{cat}({sub})"]


def test_deduction_column_decides_leave_consuming_classes():
    """안내표 '연가일수 공제여부'가 곧 판정 기준.

    "공제" 항목만 연가 잔량을 깎는 분류(연가/반일연가/결근)로 가고,
    "미공제" 항목은 절대 연가를 깎지 않아야 한다. 공무상병가·관외여행이
    "특별휴가_미정"인 근거가 이 칸이다.
    """
    data = json.loads(GUIDE_PATH.read_text(encoding="utf-8"))
    wrong = []
    for e in data:
        deduction = e["deduction"]
        for raw in _guide_raws(e):
            actual = mapping.classify(raw)
            if deduction == "공제" and actual not in LEAVE_CONSUMING:
                wrong.append((raw, "공제인데", actual))
            elif deduction == "미공제" and actual in LEAVE_CONSUMING:
                wrong.append((raw, "미공제인데", actual))
    assert not wrong, f"공제여부와 분류가 어긋남: {wrong}"
    print("OK: test_deduction_column_decides_leave_consuming_classes")


def test_non_deducted_edge_cases_go_to_pending():
    """미공제이면서 급여 처리 규칙이 확립돼 있지 않은 항목은 확인 화면으로."""
    for raw in ("공무상병가", "관외여행"):
        assert mapping.classify(raw) == PENDING, raw
    print("OK: test_non_deducted_edge_cases_go_to_pending")


def test_category_map_agrees_with_keyword_rules():
    """문서용 예시표(CATEGORY_MAP)와 키워드 규칙이 어긋나지 않아야 한다."""
    for raw, expected in mapping.CATEGORY_MAP.items():
        assert mapping.classify_by_rules(mapping.normalize(raw)) == expected, raw
    print("OK: test_category_map_agrees_with_keyword_rules")


if __name__ == "__main__":
    test_bare_sick_leave_is_recognized()
    test_partial_day_sick_leave_variants()
    test_official_injury_leave_goes_to_pending()
    test_partial_day_annual_leave_variants()
    test_separator_and_spacing_variants_are_normalized()
    test_half_day_annual_leave()
    test_special_leave_family_goes_to_pending()
    test_plain_categories()
    test_unknown_category_is_pending_not_error()
    test_every_guide_combination_classifies_as_expected()
    test_deduction_column_decides_leave_consuming_classes()
    test_non_deducted_edge_cases_go_to_pending()
    test_category_map_agrees_with_keyword_rules()
    print("ALL OK")
