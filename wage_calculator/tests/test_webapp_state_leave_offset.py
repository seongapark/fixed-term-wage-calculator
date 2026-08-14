import sys
from pathlib import Path
from datetime import date, time
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import Config
from core.models import build_event
from webapp.state import AppState


def _state_with_person(events):
    state = AppState()
    state.config_obj = Config({"surveys": [], "rates": {"2026": {"daily_wage": 78560, "meal_allowance": 160000}}, "holidays": []})
    state.work_year, state.work_month = 2026, 7
    p = SimpleNamespace(
        contract_start=date(2026, 7, 1), contract_end=date(2026, 9, 30), events=events,
        name="김테스트", birth="1990-01-01", ssn="", bank="", account="", survey_name="테스트조사",
    )
    state.people = {"김테스트::19900101": p}
    return state


def test_shortfall_produces_leave_warning():
    """발생 전 7/10 조퇴 4h -> 상계 불가 -> leave_warnings에 이름이 담긴다."""
    late = build_event("조퇴", date(2026, 7, 10), time(14, 0), time(18, 0), 240)
    state = _state_with_person([late])
    state.run_calculation()
    assert any("김테스트" in w for w in state.leave_warnings)


def test_no_warning_when_fully_offset():
    """가용 연가 내 상계면 경고 없음(8월 계산)."""
    late = build_event("지각", date(2026, 8, 10), time(9, 0), time(13, 0), 240)
    state = _state_with_person([late])
    state.work_month = 8
    state.run_calculation()
    assert state.leave_warnings == []


if __name__ == "__main__":
    test_shortfall_produces_leave_warning()
    test_no_warning_when_fully_offset()
    print("ALL OK")
