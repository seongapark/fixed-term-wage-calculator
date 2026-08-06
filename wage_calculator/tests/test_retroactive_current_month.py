import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import Config
from core.models import TargetPerson
from core.parser import person_key
from core.retroactive import current_month_adjustments


def _config():
    return Config({"surveys": [], "rates": {
        "2026": {"hourly_wage": 9820, "meal_allowance": 160000},
    }, "holidays": []})


def test_adjustment_is_recalculated_minus_previously_paid():
    person = TargetPerson(
        name="김철수", birth="19900101", ssn="900101-1234567", bank="", account="",
        survey_name="테스트조사", contract_start=date(2026, 6, 1), contract_end=date(2026, 6, 30),
        events=[],
    )
    people = {person_key("김철수", "19900101"): person}
    previous_payroll = {
        "900101-1234567": {
            "ssn": "900101-1234567", "name": "김철수",
            "contract_start": date(2026, 6, 1), "contract_end": date(2026, 6, 30),
            "total_payment": 1000000,  # 전월에 실제로 지급된(더 적었던) 금액
            "bank": "", "account": "",
        },
    }
    adjustments = current_month_adjustments(people, previous_payroll, _config(), 2026, 6)
    key = person_key("김철수", "19900101")
    assert key in adjustments
    assert adjustments[key] > 0, "재계산액이 더 크므로 추가지급(양수)이어야 함: " + str(adjustments[key])
    print("OK: test_adjustment_is_recalculated_minus_previously_paid")


def test_no_previous_entry_means_zero_adjustment():
    person = TargetPerson(
        name="박신입", birth="19950505", ssn="950505-1234567", bank="", account="",
        survey_name="테스트조사", contract_start=date(2026, 6, 1), contract_end=date(2026, 6, 30),
        events=[],
    )
    people = {person_key("박신입", "19950505"): person}
    adjustments = current_month_adjustments(people, {}, _config(), 2026, 6)
    assert adjustments[person_key("박신입", "19950505")] == 0
    print("OK: test_no_previous_entry_means_zero_adjustment")


def test_reassigned_contract_does_not_cause_full_clawback():
    """당월에 새 조사로 재배정되어 계약기간이 전월보다 늦게 시작하는 사람도,
    전월 재계산은 전월 파일의 계약기간을 써야 하므로 정상 재계산되고
    전월 실지급액 전액이 소급 환수되면 안 된다(회귀 버그 재현 테스트)."""
    person = TargetPerson(
        name="김철수", birth="19900101", ssn="900101-1234567", bank="", account="",
        survey_name="새조사",
        contract_start=date(2026, 7, 1), contract_end=date(2026, 9, 30),  # 당월(7월) 재배정 계약
        events=[],
    )
    people = {person_key("김철수", "19900101"): person}
    previous_payroll = {
        "900101-1234567": {
            "ssn": "900101-1234567", "name": "김철수",
            "contract_start": date(2026, 6, 1), "contract_end": date(2026, 6, 30),  # 전월(6월) 실제 계약기간
            "total_payment": 2045440,
            "bank": "", "account": "",
        },
    }
    adjustments = current_month_adjustments(people, previous_payroll, _config(), 2026, 6)
    key = person_key("김철수", "19900101")
    # 전월 계약기간(6월 한 달)으로 정상 재계산되면 실지급액과 비슷한 범위여야 하고,
    # 절대 "-전월실지급액"(즉 전월분 전액 환수)이 나오면 안 된다.
    assert adjustments[key] != -2045440, f"버그 재현: 전월 실지급액 전액이 그대로 환수됨: {adjustments[key]}"
    assert adjustments[key] > -1000000, f"재계산액이 비정상적으로 작음(계약기간 버그 의심): {adjustments[key]}"
    print("OK: test_reassigned_contract_does_not_cause_full_clawback")


def test_blank_previous_contract_dates_skip_that_person_only():
    """전월 파일이 수기로 편집되는 등 계약일자 셀이 비어있으면(None) 그
    사람만 소급 0으로 건너뛰어야 한다 - 여기서 예외가 나면 이 함수를
    감싸는 app.py의 단일 try/except 때문에 전원의 소급계산이 통째로
    사라지는 더 나쁜 회귀가 생긴다."""
    person = TargetPerson(
        name="김철수", birth="19900101", ssn="900101-1234567", bank="", account="",
        survey_name="테스트조사", contract_start=date(2026, 6, 1), contract_end=date(2026, 6, 30),
        events=[],
    )
    people = {person_key("김철수", "19900101"): person}
    previous_payroll = {
        "900101-1234567": {
            "ssn": "900101-1234567", "name": "김철수",
            "contract_start": None, "contract_end": None,  # 수기 편집 등으로 비어있는 경우
            "total_payment": 1000000,
            "bank": "", "account": "",
        },
    }
    adjustments = current_month_adjustments(people, previous_payroll, _config(), 2026, 6)
    assert adjustments[person_key("김철수", "19900101")] == 0
    print("OK: test_blank_previous_contract_dates_skip_that_person_only")


if __name__ == "__main__":
    test_adjustment_is_recalculated_minus_previously_paid()
    test_no_previous_entry_means_zero_adjustment()
    test_reassigned_contract_does_not_cause_full_clawback()
    test_blank_previous_contract_dates_skip_that_person_only()
    print("ALL OK")
