import sys
from pathlib import Path
from datetime import date, time
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import Config
from core.models import build_event
from core.payroll import calc_payroll
from core.retroactive import current_month_adjustments


def _config():
    return Config({"surveys": [], "rates": {"2026": {"daily_wage": 78560, "meal_allowance": 160000}}, "holidays": []})


def test_retro_prev_month_reflects_leave_offset():
    """소급 재계산도 계약 전체 이벤트를 통해 연가 상계를 반영해야 한다.
    7월 만근 -> 8/1 연가 480 발생. 8/10 지각 4h(240)는 8월분에서 연가로 상계된다.
    전월(8월)을 소급 재계산한 값이, 동일 이벤트/계약으로 직접 계산한 8월분과 일치하고,
    그 8월분은 실제로 지각이 상계(급여 미공제)돼 있어야 한다."""
    events = [build_event("지각", date(2026, 8, 10), time(9, 0), time(13, 0), 240)]
    config = _config()

    # 직접 계산한 8월분(기준값)
    direct = calc_payroll(
        SimpleNamespace(contract_start=date(2026, 7, 1), contract_end=date(2026, 9, 30),
                        events=events, name="김소급", birth="1990-01-01", ssn="TESTSSN",
                        bank="", account="", survey_name="테스트조사"),
        config, 2026, 8,
    )
    assert direct.leave_offset_minutes == 240   # 지각이 연가로 상계됨(시나리오가 실제로 상계를 탄다)
    assert direct.late_out_minutes == 0         # 급여 공제 없음

    # 소급 경로: 당월 로스터 person(계약 전체 이벤트) + 전월 파일 기록
    person = SimpleNamespace(
        name="김소급", birth="1990-01-01", ssn="TESTSSN", bank="", account="",
        contract_start=date(2026, 7, 1), contract_end=date(2026, 9, 30), events=events,
    )
    people = {"김소급::1990-01-01": person}
    previous_payroll = {
        "TESTSSN": {
            "contract_start": date(2026, 7, 1), "contract_end": date(2026, 9, 30),
            "total_payment": 0, "name": "김소급", "bank": "", "account": "",
        }
    }
    adjustments, details, errors = current_month_adjustments(people, previous_payroll, config, 2026, 8)
    assert errors == []
    assert details["김소급::1990-01-01"].recalculated == direct.total_payment


if __name__ == "__main__":
    test_retro_prev_month_reflects_leave_offset()
    print("ALL OK")
