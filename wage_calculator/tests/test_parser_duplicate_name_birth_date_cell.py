import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.models import Employee
from core.parser import build_target_people, person_key


def _employees_with_same_name():
    return {
        "김철수": [
            Employee(name="김철수", ssn="900101-1234567", bank="국민은행", account="111", birth="1990-01-01"),
            Employee(name="김철수", ssn="950505-1234567", bank="국민은행", account="222", birth="1995-05-05"),
        ]
    }


def test_ambiguous_name_matches_when_birth_cell_is_plain_text():
    """대조군: 생년월일이 순수 텍스트면 지금도 정상 매칭된다."""
    employees = _employees_with_same_name()
    giganje_rows = [{
        "성명": "김철수", "생년월일": "1995-05-05", "종별": "결근",
        "사용기간(날짜)": "2026-08-03", "사용시간(시분)": None,
        "소속": "통계조사팀", "직급": "조사원",
    }]
    people, missing_names, ambiguous_names = build_target_people(giganje_rows, employees)

    assert ambiguous_names == []
    key = person_key("김철수", "1995-05-05")
    assert key in people
    assert len(people[key].events) == 1, "텍스트 생년월일 셀은 지금도 정상 매칭되어야 함(대조군)"


def test_ambiguous_name_matches_when_birth_cell_is_a_real_date():
    """openpyxl은 날짜형 셀을 datetime으로 반환하므로, 그 상태로도 동명이인
    구분이 정상 동작해야 한다 - 지금은 str() 비교라 조용히 매칭 실패하고
    그 사람의 근무상황(결근 등)이 통째로 안 붙는다(만근으로 계산되는 사고)."""
    employees = _employees_with_same_name()
    giganje_rows = [{
        "성명": "김철수", "생년월일": datetime(1995, 5, 5), "종별": "결근",
        "사용기간(날짜)": "2026-08-03", "사용시간(시분)": None,
        "소속": "통계조사팀", "직급": "조사원",
    }]
    people, missing_names, ambiguous_names = build_target_people(giganje_rows, employees)

    assert ambiguous_names == []
    key = person_key("김철수", "1995-05-05")
    assert key in people
    assert len(people[key].events) == 1, (
        "생년월일 셀이 날짜형이어도 결근 이벤트가 정상 매칭되어야 함 "
        "(만근으로 잘못 계산되는 사고 방지)"
    )
    other_key = person_key("김철수", "1990-01-01")
    assert len(people[other_key].events) == 0, "다른 동명이인에게 잘못 붙으면 안 됨"


if __name__ == "__main__":
    test_ambiguous_name_matches_when_birth_cell_is_plain_text()
    test_ambiguous_name_matches_when_birth_cell_is_a_real_date()
    print("ALL OK")
