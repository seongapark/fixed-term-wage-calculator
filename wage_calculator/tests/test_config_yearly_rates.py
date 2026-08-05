import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import Config


def test_set_and_get_year_rates():
    config = Config({"surveys": [], "rates": {}, "holidays": []})
    config.set_year_rates(2025, 9860, 150000)
    config.set_year_rates(2026, 9820, 160000)
    assert config.hourly_wage_for(2025) == 9860
    assert config.meal_allowance_for(2025) == 150000
    assert config.hourly_wage_for(2026) == 9820
    assert config.meal_allowance_for(2026) == 160000
    assert config.rate_years() == [2025, 2026]
    print("OK: test_set_and_get_year_rates")


def test_missing_year_raises_clear_error():
    config = Config({"surveys": [], "rates": {"2026": {"hourly_wage": 9820, "meal_allowance": 160000}}, "holidays": []})
    try:
        config.hourly_wage_for(2027)
        raise AssertionError("2027년 요율이 없는데 예외가 안 남")
    except ValueError as e:
        assert "2027" in str(e), str(e)
        print("OK: test_missing_year_raises_clear_error")


def test_legacy_common_migrates_to_current_year():
    from datetime import date
    config = Config({"surveys": [], "common": {"hourly_wage": 9820, "meal_allowance": 160000}, "holidays": []})
    this_year = date.today().year
    assert config.hourly_wage_for(this_year) == 9820
    assert config.meal_allowance_for(this_year) == 160000
    print("OK: test_legacy_common_migrates_to_current_year")


def test_delete_year_rates():
    config = Config({"surveys": [], "rates": {"2026": {"hourly_wage": 9820, "meal_allowance": 160000}}, "holidays": []})
    config.delete_year_rates(2026)
    assert config.rate_years() == []
    print("OK: test_delete_year_rates")


def test_to_dict_round_trip():
    config = Config({"surveys": [], "rates": {}, "holidays": []})
    config.set_year_rates(2026, 9820, 160000)
    data = config.to_dict()
    assert data["rates"] == {"2026": {"hourly_wage": 9820, "meal_allowance": 160000}}
    assert "common" not in data
    reloaded = Config(data)
    assert reloaded.hourly_wage_for(2026) == 9820
    print("OK: test_to_dict_round_trip")


if __name__ == "__main__":
    test_set_and_get_year_rates()
    test_missing_year_raises_clear_error()
    test_legacy_common_migrates_to_current_year()
    test_delete_year_rates()
    test_to_dict_round_trip()
    print("ALL OK")
