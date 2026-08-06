import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import Config
from core.retroactive import departed_retroactive, compute_retroactive


def _config():
    return Config({"surveys": [], "rates": {
        "2026": {"hourly_wage": 9820, "meal_allowance": 160000},
    }, "holidays": []})


def test_departed_person_with_leftover_rows_is_recalculated():
    # 최도영: 전월(6월)파일엔 있지만 당월(7월) A파일엔 없음(완전퇴사).
    # 당월 B파일에는 6월 말 결근 잔여행이 남아있음(export가 날짜범위로만 걸리므로).
    previous_payroll = {
        "980126-2641395": {
            "ssn": "980126-2641395", "name": "최도영",
            "contract_start": date(2026, 6, 1), "contract_end": date(2026, 6, 30),
            "total_payment": 2000000,
            "bank": "하나은행", "account": "111",
        },
    }
    giganje_rows = [
        {
            "소속": "부산지방고용노동청", "직급": "기간제근로자", "성명": "최도영",
            "생년월일": "1998-01-26", "종별": "결근",
            "사용기간(날짜)": "2026-06-29", "사용시간(시분)": None,
        },
    ]
    departed = departed_retroactive({}, previous_payroll, giganje_rows, _config(), 2026, 6)
    assert len(departed) == 1, departed
    d = departed[0]
    assert d.name == "최도영"
    assert d.prev_paid == 2000000
    assert d.adjustment == d.prev_recalculated - 2000000
    print("OK: test_departed_person_with_leftover_rows_is_recalculated")


def test_departed_person_with_no_leftover_rows_is_skipped():
    previous_payroll = {
        "980126-2641395": {
            "ssn": "980126-2641395", "name": "최도영",
            "contract_start": date(2026, 6, 1), "contract_end": date(2026, 6, 30),
            "total_payment": 2000000,
            "bank": "하나은행", "account": "111",
        },
    }
    departed = departed_retroactive({}, previous_payroll, [], _config(), 2026, 6)
    assert departed == [], "당월 B파일에 잔여 행이 없으면 출력 대상에서 빠져야 함"
    print("OK: test_departed_person_with_no_leftover_rows_is_skipped")


def test_departed_person_name_collision_with_different_birth_is_ignored():
    # B파일에 동명이인이 있고 생년월일이 다르면 매칭하지 않는다(잘못된 소급 방지).
    previous_payroll = {
        "980126-2641395": {  # -> 1998-01-26
            "ssn": "980126-2641395", "name": "최도영",
            "contract_start": date(2026, 6, 1), "contract_end": date(2026, 6, 30),
            "total_payment": 2000000, "bank": "", "account": "",
        },
    }
    giganje_rows = [
        {
            "소속": "부산지방고용노동청", "직급": "기간제근로자", "성명": "최도영",
            "생년월일": "1985-03-03",  # 전월파일 사람과 다른 생년월일 -> 동명이인
            "종별": "결근", "사용기간(날짜)": "2026-06-29", "사용시간(시분)": None,
        },
    ]
    departed = departed_retroactive({}, previous_payroll, giganje_rows, _config(), 2026, 6)
    assert departed == [], "생년월일이 다른 동명이인의 행을 매칭하면 안 됨"
    print("OK: test_departed_person_name_collision_with_different_birth_is_ignored")


def test_compute_retroactive_combines_both():
    result = compute_retroactive({}, {}, [], _config(), 2026, 6)
    assert result == ({}, [])
    print("OK: test_compute_retroactive_combines_both")


def test_departed_person_matches_when_birth_cell_is_a_real_date():
    """B파일 '생년월일' 셀이 문자열이 아니라 실제 datetime(openpyxl이 날짜형
    셀을 읽을 때 흔한 경우)이어도 정상 매칭돼야 한다(회귀 버그 재현 테스트)."""
    from datetime import date, datetime
    previous_payroll = {
        "980126-2641395": {
            "ssn": "980126-2641395", "name": "최도영",
            "contract_start": date(2026, 6, 1), "contract_end": date(2026, 6, 30),
            "total_payment": 2000000,
            "bank": "하나은행", "account": "111",
        },
    }
    giganje_rows = [
        {
            "소속": "부산지방고용노동청", "직급": "기간제근로자", "성명": "최도영",
            "생년월일": datetime(1998, 1, 26),  # 문자열이 아니라 실제 datetime 객체
            "종별": "결근", "사용기간(날짜)": "2026-06-29", "사용시간(시분)": None,
        },
    ]
    departed = departed_retroactive({}, previous_payroll, giganje_rows, _config(), 2026, 6)
    assert len(departed) == 1, f"datetime 셀 때문에 매칭 실패(버그 재현): {departed}"
    print("OK: test_departed_person_matches_when_birth_cell_is_a_real_date")


def test_departed_person_blank_contract_dates_is_skipped_not_crashed():
    """전월 파일의 계약일자 셀이 비어있으면(None) 예외 없이 건너뛰어야 한다."""
    previous_payroll = {
        "980126-2641395": {
            "ssn": "980126-2641395", "name": "최도영",
            "contract_start": None, "contract_end": None,
            "total_payment": 2000000, "bank": "", "account": "",
        },
    }
    giganje_rows = [
        {
            "소속": "부산지방고용노동청", "직급": "기간제근로자", "성명": "최도영",
            "생년월일": "1998-01-26", "종별": "결근",
            "사용기간(날짜)": "2026-06-29", "사용시간(시분)": None,
        },
    ]
    departed = departed_retroactive({}, previous_payroll, giganje_rows, _config(), 2026, 6)
    assert departed == [], departed
    print("OK: test_departed_person_blank_contract_dates_is_skipped_not_crashed")


if __name__ == "__main__":
    test_departed_person_with_leftover_rows_is_recalculated()
    test_departed_person_with_no_leftover_rows_is_skipped()
    test_departed_person_name_collision_with_different_birth_is_ignored()
    test_compute_retroactive_combines_both()
    test_departed_person_matches_when_birth_cell_is_a_real_date()
    test_departed_person_blank_contract_dates_is_skipped_not_crashed()
    print("ALL OK")
