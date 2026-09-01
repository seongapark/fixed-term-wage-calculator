"""시간 기재 항목의 급여 공제 대상 판정.

세부선택 없이 "조퇴"로만 찍은 사람이 가장 유리하고, 사유를 정확히 적을수록
손해를 보던 문제를 고정한다.

  - 조퇴(연가처리): 연가 잔량에서 이미 차감되므로 급여는 공제하지 않는다.
    (예전에는 연가도 깎이고 급여도 깎이는 이중 공제였다)
  - 조퇴(일반병가): 안내표상 연가일수 미공제이고, 종일 병가가 유급인 것과
    같은 기준이어야 하므로 연가도 급여도 깎지 않는다.
  - 조퇴(세부선택 없음, "기타"): 보유 연가로 상계하고 부족분만 급여 공제.
"""
import sys
from pathlib import Path
from datetime import date, time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import Config
from core.models import TargetPerson, build_event
from core.payroll import calc_payroll

CONTRACT_START = date(2026, 7, 1)
CONTRACT_END = date(2026, 9, 30)
# 7월 만근으로 연가 1일(480분)이 쌓인 뒤인 8월에 2시간 사용.
USED_ON = date(2026, 8, 12)


def _config():
    return Config({
        "surveys": [],
        "rates": {"2026": {"daily_wage": 78560, "meal_allowance": 160000}},
        "holidays": [],
    })


def _result(raw_category, minutes=120):
    event = build_event(raw_category, USED_ON, time(16, 0), time(18, 0), minutes)
    person = TargetPerson(
        name="홍길동", survey_name="조사", events=[event],
        contract_start=CONTRACT_START, contract_end=CONTRACT_END,
    )
    return calc_payroll(person, _config(), 2026, 8)


def test_annual_leave_marked_early_leave_is_not_deducted_twice():
    for raw in ("연가",):
        r = _result(raw)
        assert r.late_out_minutes == 0, f"{raw}: 연가에서 깎았는데 급여도 공제됨"
        assert r.remaining_leave_days == 0.75, f"{raw}: 연가 120분이 차감되어야 함"
    print("OK: test_annual_leave_marked_early_leave_is_not_deducted_twice")


def test_sick_leave_marked_early_leave_deducts_neither():
    for raw in ("일반병가",):
        r = _result(raw)
        assert r.late_out_minutes == 0, f"{raw}: 병가는 급여를 공제하지 않는다"
        assert r.remaining_leave_days == 1.0, f"{raw}: 병가는 연가일수 미공제"
    print("OK: test_sick_leave_marked_early_leave_deducts_neither")


def test_bare_early_leave_is_offset_by_remaining_leave():
    r = _result("조퇴")
    assert r.leave_offset_minutes == 120
    assert r.late_out_minutes == 0
    assert r.remaining_leave_days == 0.75
    assert r.leave_shortfall is False
    print("OK: test_bare_early_leave_is_offset_by_remaining_leave")


def test_bare_early_leave_without_balance_is_deducted_from_pay():
    """깎을 연가가 없으면 '기타'로 찍고, 그 시간은 급여에서 공제된다."""
    event = build_event("조퇴", date(2026, 7, 8), time(16, 0), time(18, 0), 120)
    person = TargetPerson(
        name="홍길동", survey_name="조사", events=[event],
        contract_start=CONTRACT_START, contract_end=CONTRACT_END,
    )
    r = calc_payroll(person, _config(), 2026, 7)   # 7월엔 아직 연가 미발생
    assert r.leave_offset_minutes == 0
    assert r.late_out_minutes == 120
    assert r.leave_shortfall is True
    print("OK: test_bare_early_leave_without_balance_is_deducted_from_pay")


def test_paid_special_leave_time_is_not_deducted():
    """공무상병가처럼 확인 화면에서 유급으로 고른 건은 그 시간을 깎지 않는다.

    무급으로 고른 건은 결근과 같은 취급이라 그대로 공제된다.
    """
    for raw in ("지각(공무상병가)", "조퇴(공무상병가)", "관외여행"):
        event = build_event(raw, USED_ON, time(16, 0), time(18, 0), 120)
        event.classified = "유급특별휴가"          # 확인 화면에서 사람이 지정
        person = TargetPerson(
            name="홍길동", survey_name="조사", events=[event],
            contract_start=CONTRACT_START, contract_end=CONTRACT_END,
        )
        r = calc_payroll(person, _config(), 2026, 8)
        assert r.late_out_minutes == 0, f"{raw}: 유급인데 급여가 공제됨"
        assert r.remaining_leave_days == 1.0, f"{raw}: 연가일수 미공제"

    event = build_event("지각(공무상병가)", USED_ON, time(16, 0), time(18, 0), 120)
    event.classified = "무급특별휴가"
    event.unpaid = True                        # 확인 화면(pending.apply_decisions)이 함께 세우는 값
    person = TargetPerson(
        name="홍길동", survey_name="조사", events=[event],
        contract_start=CONTRACT_START, contract_end=CONTRACT_END,
    )
    assert calc_payroll(person, _config(), 2026, 8).late_out_minutes == 120
    print("OK: test_paid_special_leave_time_is_not_deducted")


def test_marked_reasons_are_never_worse_than_bare_early_leave():
    """사유를 정확히 적었다고 해서 손해 보는 일이 없어야 한다."""
    bare = _result("조퇴").total_payment
    for raw in ("연가", "일반병가"):
        assert _result(raw).total_payment >= bare, raw
    print("OK: test_marked_reasons_are_never_worse_than_bare_early_leave")


if __name__ == "__main__":
    test_annual_leave_marked_early_leave_is_not_deducted_twice()
    test_sick_leave_marked_early_leave_deducts_neither()
    test_bare_early_leave_is_offset_by_remaining_leave()
    test_bare_early_leave_without_balance_is_deducted_from_pay()
    test_paid_special_leave_time_is_not_deducted()
    test_marked_reasons_are_never_worse_than_bare_early_leave()
    print("ALL OK")
