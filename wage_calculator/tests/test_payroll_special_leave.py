import sys
from pathlib import Path
from datetime import date
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import Config
from core.payroll import calc_payroll
from core.models import build_event, LeaveEvent


def _config():
    return Config({"surveys": [], "rates": {"2026": {"daily_wage": 78560, "meal_allowance": 160000}}, "holidays": []})


def _person(events):
    return SimpleNamespace(
        contract_start=date(2026, 7, 1), contract_end=date(2026, 7, 31), events=events,
        name="테스트", birth="", ssn="", bank="", account="", survey_name="테스트조사",
    )


def test_public_leave_no_longer_reduces_total_days():
    """공가 3일만 있는 달: workdays=23(2026-07 NETWORKDAYS). 버그 수정 전에는
    total_days가 20으로 깎였는데, 수정 후에는 공가가 급여에 영향을 주지
    않아야 하므로 23이어야 한다(결근 없음)."""
    events = [build_event("공가", d) for d in [date(2026, 7, 6), date(2026, 7, 7), date(2026, 7, 8)]]
    r = calc_payroll(_person(events), _config(), 2026, 7)
    assert r.total_days == 23, f"공가만 있으면 total_days가 workdays(23)와 같아야 하는데: {r.total_days}"
    print("OK: test_public_leave_no_longer_reduces_total_days")


def test_absence_reduces_total_days():
    """결근 2일만 있는 달: total_days = workdays(23) - absence_days(2) = 21이어야 한다."""
    events = [build_event("결근", d) for d in [date(2026, 7, 13), date(2026, 7, 14)]]
    r = calc_payroll(_person(events), _config(), 2026, 7)
    assert r.total_days == 21, f"결근 2일이면 total_days=21이어야 하는데: {r.total_days}"
    print("OK: test_absence_reduces_total_days")


def test_special_leave_folds_into_buckets_and_note():
    d1, d2, d3 = date(2026, 7, 6), date(2026, 7, 7), date(2026, 7, 8)   # 공가 3일
    a1, a2 = date(2026, 7, 13), date(2026, 7, 14)                       # 결근 2일
    p1, p2 = date(2026, 7, 20), date(2026, 7, 21)                       # 유급특별휴가 2일(한 그룹)
    u1 = date(2026, 7, 27)                                              # 무급특별휴가 1일

    events = [build_event("공가", d) for d in (d1, d2, d3)]
    events += [build_event("결근", d) for d in (a1, a2)]
    events += [
        LeaveEvent(raw_category="특별휴가", classified="유급특별휴가", d=d, is_time_based=False,
                   day_weight=1.0, unpaid=False, breaks=False, source_range=(p1, p2))
        for d in (p1, p2)
    ]
    events.append(
        LeaveEvent(raw_category="특별휴가", classified="무급특별휴가", d=u1, is_time_based=False,
                   day_weight=1.0, unpaid=True, breaks=False, source_range=(u1, u1))
    )

    r = calc_payroll(_person(events), _config(), 2026, 7)

    assert r.public_leave_days == 5, f"공가3+유급특별휴가2=5이어야 하는데: {r.public_leave_days}"
    assert r.absence_days == 3, f"결근2+무급특별휴가1=3이어야 하는데: {r.absence_days}"
    # total_days = actual_workdays + paid_holiday_days + public_leave_days
    #            = (23-5-(0+3)) + 0 + 5 = 20
    assert r.total_days == 20, f"total_days=20이어야 하는데: {r.total_days}"
    # meal_eligible_days = period_total_days(31) - absence_days(3) = 28
    assert r.meal_eligible_days == 28, f"meal_eligible_days=28이어야 하는데: {r.meal_eligible_days}"
    assert r.special_leave_note == "특별휴가(유급) 7/20~7/21, 특별휴가(무급) 7/27", r.special_leave_note
    print("OK: test_special_leave_folds_into_buckets_and_note")


if __name__ == "__main__":
    test_public_leave_no_longer_reduces_total_days()
    test_absence_reduces_total_days()
    test_special_leave_folds_into_buckets_and_note()
    print("ALL OK")
