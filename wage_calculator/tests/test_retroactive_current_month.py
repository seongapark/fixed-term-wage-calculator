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


if __name__ == "__main__":
    test_adjustment_is_recalculated_minus_previously_paid()
    test_no_previous_entry_means_zero_adjustment()
    print("ALL OK")
