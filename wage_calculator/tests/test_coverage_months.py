"""B파일(근무상황) 조회기간이 계약 시작월~계산월을 덮는지 월 단위 검증."""
import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import coverage
from core.models import TargetPerson


def _row(period, category="연가"):
    return {"성명": "홍길동", "종별": category, "사용기간(날짜)": period, "사용시간(시분)": None}


def _person(name, start, end, survey="지역별고용조사"):
    return TargetPerson(name=name, survey_name=survey, contract_start=start, contract_end=end)


def test_covered_months_from_single_dates_and_ranges():
    rows = [_row("2026-07-15"), _row("2026-08-28~2026-09-02")]
    assert coverage.covered_months(rows) == {(2026, 7), (2026, 8), (2026, 9)}
    print("OK: test_covered_months_from_single_dates_and_ranges")


def test_covered_months_ignores_unparseable_rows():
    rows = [_row("2026-07-15"), _row(None), _row(""), _row("날짜아님")]
    assert coverage.covered_months(rows) == {(2026, 7)}
    print("OK: test_covered_months_ignores_unparseable_rows")


def test_required_months_span_contract_start_to_pay_month():
    req = coverage.required_months(date(2026, 7, 1), date(2026, 9, 30), 2026, 8)
    assert req == [(2026, 7), (2026, 8)]
    print("OK: test_required_months_span_contract_start_to_pay_month")


def test_required_months_stop_at_contract_end():
    req = coverage.required_months(date(2026, 7, 1), date(2026, 7, 31), 2026, 9)
    assert req == [(2026, 7)]
    print("OK: test_required_months_stop_at_contract_end")


def test_required_months_empty_when_contract_starts_after_pay_month():
    assert coverage.required_months(date(2026, 9, 1), date(2026, 12, 31), 2026, 8) == []
    print("OK: test_required_months_empty_when_contract_starts_after_pay_month")


def test_required_months_cross_year():
    req = coverage.required_months(date(2025, 11, 10), date(2026, 3, 31), 2026, 1)
    assert req == [(2025, 11), (2025, 12), (2026, 1)]
    print("OK: test_required_months_cross_year")


def test_gap_detected_when_earlier_contract_month_missing():
    """계약 7~9월, 8월 계산인데 8월 근무상황만 넣은 경우 -> 7월 누락."""
    people = {"홍길동::": _person("홍길동", date(2026, 7, 1), date(2026, 9, 30))}
    rows = [_row("2026-08-10")]
    gaps = coverage.find_coverage_gaps(people, rows, 2026, 8)
    assert len(gaps) == 1, gaps
    assert gaps[0]["name"] == "홍길동"
    assert gaps[0]["missing"] == [(2026, 7)]
    print("OK: test_gap_detected_when_earlier_contract_month_missing")


def test_no_gap_when_all_required_months_present():
    people = {"홍길동::": _person("홍길동", date(2026, 7, 1), date(2026, 9, 30))}
    rows = [_row("2026-07-03"), _row("2026-08-10")]
    assert coverage.find_coverage_gaps(people, rows, 2026, 8) == []
    print("OK: test_no_gap_when_all_required_months_present")


def test_no_gap_when_contract_starts_in_pay_month():
    people = {"홍길동::": _person("홍길동", date(2026, 8, 1), date(2026, 9, 30))}
    rows = [_row("2026-08-10")]
    assert coverage.find_coverage_gaps(people, rows, 2026, 8) == []
    print("OK: test_no_gap_when_contract_starts_in_pay_month")


def test_unassigned_or_incomplete_people_are_skipped():
    """담당조사 미지정(계약기간 없음) 인원은 계산 대상이 아니므로 검사도 안 한다."""
    people = {
        "무지정::": TargetPerson(name="무지정"),
        "홍길동::": _person("홍길동", date(2026, 8, 1), date(2026, 8, 31)),
    }
    rows = [_row("2026-08-10")]
    assert coverage.find_coverage_gaps(people, rows, 2026, 8) == []
    print("OK: test_unassigned_or_incomplete_people_are_skipped")


def test_message_lists_missing_months_and_people():
    people = {
        "홍길동::": _person("홍길동", date(2026, 7, 1), date(2026, 9, 30)),
        "김철수::": _person("김철수", date(2026, 6, 15), date(2026, 9, 30)),
    }
    rows = [_row("2026-08-10")]
    gaps = coverage.find_coverage_gaps(people, rows, 2026, 8)
    msg = coverage.format_gap_message(gaps, rows, 2026, 8)
    assert "2026-06" in msg and "2026-07" in msg, msg
    assert "홍길동" in msg and "김철수" in msg, msg
    assert "계약" in msg and "근무상황" in msg, msg
    print("OK: test_message_lists_missing_months_and_people")


if __name__ == "__main__":
    test_covered_months_from_single_dates_and_ranges()
    test_covered_months_ignores_unparseable_rows()
    test_required_months_span_contract_start_to_pay_month()
    test_required_months_stop_at_contract_end()
    test_required_months_empty_when_contract_starts_after_pay_month()
    test_required_months_cross_year()
    test_gap_detected_when_earlier_contract_month_missing()
    test_no_gap_when_all_required_months_present()
    test_no_gap_when_contract_starts_in_pay_month()
    test_unassigned_or_incomplete_people_are_skipped()
    test_message_lists_missing_months_and_people()
    print("ALL OK")
