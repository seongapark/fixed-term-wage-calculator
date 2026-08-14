import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import Config


def test_set_and_get_year_rates():
    config = Config({"surveys": [], "rates": {}, "holidays": []})
    config.set_year_rates(2025, 9860, 150000)
    config.set_year_rates(2026, 9820, 160000)
    assert config.daily_wage_for(2025) == 9860
    assert config.meal_allowance_for(2025) == 150000
    assert config.daily_wage_for(2026) == 9820
    assert config.meal_allowance_for(2026) == 160000
    assert config.rate_years() == [2025, 2026]
    print("OK: test_set_and_get_year_rates")


def test_missing_year_raises_clear_error():
    config = Config({"surveys": [], "rates": {"2026": {"daily_wage": 9820, "meal_allowance": 160000}}, "holidays": []})
    try:
        config.daily_wage_for(2027)
        raise AssertionError("2027년 요율이 없는데 예외가 안 남")
    except ValueError as e:
        assert "2027" in str(e), str(e)
        print("OK: test_missing_year_raises_clear_error")


def test_legacy_common_migrates_to_current_year():
    from datetime import date
    config = Config({"surveys": [], "common": {"daily_wage": 9820, "meal_allowance": 160000}, "holidays": []})
    this_year = date.today().year
    assert config.daily_wage_for(this_year) == 9820
    assert config.meal_allowance_for(this_year) == 160000
    print("OK: test_legacy_common_migrates_to_current_year")


def test_legacy_hourly_wage_field_inside_rates_migrates_to_daily_wage():
    # v4.0/v4.1 exe(2026-08-06 빌드)는 rates 항목을 옛 필드명 hourly_wage로 저장한다.
    # 여러 버전 exe가 dist/config.json 하나를 공유하므로, 구버전이 마지막에 저장하면
    # 신버전(daily_wage 기대)이 이 파일을 읽는다. 이때 요율이 "없다"고 뜨면 안 된다.
    config = Config({"surveys": [], "rates": {"2026": {"hourly_wage": 78560, "meal_allowance": 160000}}, "holidays": []})
    assert config.daily_wage_for(2026) == 78560
    assert config.meal_allowance_for(2026) == 160000
    # 저장 시 새 필드명으로 정규화되어 파일이 자가치유돼야 한다.
    assert config.to_dict()["rates"]["2026"] == {"daily_wage": 78560, "meal_allowance": 160000}
    print("OK: test_legacy_hourly_wage_field_inside_rates_migrates_to_daily_wage")


def test_delete_year_rates():
    config = Config({"surveys": [], "rates": {"2026": {"daily_wage": 9820, "meal_allowance": 160000}}, "holidays": []})
    config.delete_year_rates(2026)
    assert config.rate_years() == []
    print("OK: test_delete_year_rates")


def test_to_dict_round_trip():
    config = Config({"surveys": [], "rates": {}, "holidays": []})
    config.set_year_rates(2026, 9820, 160000)
    data = config.to_dict()
    assert data["rates"] == {"2026": {"daily_wage": 9820, "meal_allowance": 160000}}
    assert "common" not in data
    reloaded = Config(data)
    assert reloaded.daily_wage_for(2026) == 9820
    print("OK: test_to_dict_round_trip")


if __name__ == "__main__":
    test_set_and_get_year_rates()
    test_missing_year_raises_clear_error()
    test_legacy_common_migrates_to_current_year()
    test_delete_year_rates()
    test_to_dict_round_trip()
    print("ALL OK")
