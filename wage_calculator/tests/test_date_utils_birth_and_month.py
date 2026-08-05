import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import date_utils


def test_birth_from_ssn_1900s():
    assert date_utils.birth_from_ssn("980213-2752553") == "1998-02-13"
    print("OK: test_birth_from_ssn_1900s")


def test_birth_from_ssn_2000s():
    assert date_utils.birth_from_ssn("030101-4123456") == "2003-01-01"
    print("OK: test_birth_from_ssn_2000s")


def test_birth_from_ssn_no_hyphen():
    assert date_utils.birth_from_ssn("9802132752553") == "1998-02-13"
    print("OK: test_birth_from_ssn_no_hyphen")


def test_birth_from_ssn_invalid_raises():
    try:
        date_utils.birth_from_ssn("abc")
        raise AssertionError("짧은 문자열인데 예외가 안 남")
    except ValueError:
        print("OK: test_birth_from_ssn_invalid_raises")


def test_previous_month_normal():
    assert date_utils.previous_month(2026, 7) == (2026, 6)
    print("OK: test_previous_month_normal")


def test_previous_month_year_boundary():
    assert date_utils.previous_month(2026, 1) == (2025, 12)
    print("OK: test_previous_month_year_boundary")


if __name__ == "__main__":
    test_birth_from_ssn_1900s()
    test_birth_from_ssn_2000s()
    test_birth_from_ssn_no_hyphen()
    test_birth_from_ssn_invalid_raises()
    test_previous_month_normal()
    test_previous_month_year_boundary()
    print("ALL OK")
