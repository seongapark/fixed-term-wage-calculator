"""core.parser.build_target_people가 다일(多日) 특별휴가 B파일 행을 펼칠 때
source_range=(start_d, end_d)를 실제로 전달하는지 검증한다.

기존 테스트들은 모두 build_event()를 직접 호출하거나 LeaveEvent를 손으로
만들어 source_range를 이미 지정해 두므로, parser.py의 행 펼침 루프 자체
(person.events.append(build_event(raw_category, d, source_range=(start_d, end_d))))는
어느 테스트에서도 실행되지 않는다. 만약 그 kwarg가 실수로 빠지면(기본값
(d, d)로 회귀) 기존 테스트는 전부 그대로 통과하지만, 마킹 화면에서 다일
특별휴가 한 건이 날짜 수만큼 여러 행으로 쪼개져 보이는 회귀가 생긴다.
이 테스트는 그 회귀를 잡기 위해 build_target_people을 직접 호출한다.
"""
import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.parser import build_target_people, person_key
from core.models import Employee


def test_multi_day_special_leave_row_shares_source_range():
    # B파일(근무상황) 원본 행 형식을 그대로 흉내낸 합성 데이터. 실제 xlsx 로딩
    # 없이 build_target_people이 기대하는 dict 형태만 맞춘다.
    giganje_rows = [
        {
            "소속": "정보통계과",
            "직급": "기간제",
            "성명": "김철수",
            "생년월일": "19900101",
            "종별": "특별휴가",
            "사용기간(날짜)": "2026-07-20~2026-07-22",  # 월~수, 주말 없음 -> 평일 3일
            "사용시간(시분)": None,
        },
    ]
    employees = {
        "김철수": [
            Employee(name="김철수", ssn="", bank="", account="", birth="19900101"),
        ],
    }

    people, missing_names, ambiguous_names = build_target_people(giganje_rows, employees)

    assert missing_names == [], missing_names
    assert ambiguous_names == [], ambiguous_names

    person = people[person_key("김철수", "19900101")]
    events = [e for e in person.events if e.classified == "특별휴가_미정"]

    expected_range = (date(2026, 7, 20), date(2026, 7, 22))
    assert len(events) == 3, f"7/20(월)~7/22(수) 평일 3일이 펼쳐져야 하는데: {len(events)}"
    assert all(e.source_range == expected_range for e in events), [e.source_range for e in events]
    assert sorted(e.d for e in events) == [date(2026, 7, 20), date(2026, 7, 21), date(2026, 7, 22)]
    print("OK: test_multi_day_special_leave_row_shares_source_range")


if __name__ == "__main__":
    test_multi_day_special_leave_row_shares_source_range()
    print("ALL OK")
