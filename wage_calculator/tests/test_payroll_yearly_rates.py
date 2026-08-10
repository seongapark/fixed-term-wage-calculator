import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import Config
from core.models import TargetPerson
from core.payroll import calc_payroll


def _person(contract_start, contract_end):
    return TargetPerson(
        name="김철수", birth="19900101", ssn="900101-1234567", bank="", account="",
        survey_name="테스트조사", contract_start=contract_start, contract_end=contract_end,
        events=[],
    )


def test_calc_payroll_uses_rate_for_requested_year():
    config = Config({"surveys": [], "rates": {
        "2025": {"daily_wage": 9860 * 8, "meal_allowance": 150000},
        "2026": {"daily_wage": 9820 * 8, "meal_allowance": 160000},
    }, "holidays": []})

    person_2025 = _person(date(2025, 12, 1), date(2025, 12, 31))
    result_2025 = calc_payroll(person_2025, config, 2025, 12)
    assert result_2025.daily_wage == 9860 * 8, result_2025.daily_wage

    person_2026 = _person(date(2026, 1, 1), date(2026, 1, 31))
    result_2026 = calc_payroll(person_2026, config, 2026, 1)
    assert result_2026.daily_wage == 9820 * 8, result_2026.daily_wage

    print("OK: test_calc_payroll_uses_rate_for_requested_year")


def test_calc_payroll_raises_when_year_rate_missing():
    config = Config({"surveys": [], "rates": {"2026": {"daily_wage": 9820 * 8, "meal_allowance": 160000}}, "holidays": []})
    person = _person(date(2025, 12, 1), date(2025, 12, 31))
    try:
        calc_payroll(person, config, 2025, 12)
        raise AssertionError("2025년 요율이 없는데 예외가 안 남")
    except ValueError as e:
        assert "2025" in str(e), str(e)
        print("OK: test_calc_payroll_raises_when_year_rate_missing")


if __name__ == "__main__":
    test_calc_payroll_uses_rate_for_requested_year()
    test_calc_payroll_raises_when_year_rate_missing()
    print("ALL OK")
