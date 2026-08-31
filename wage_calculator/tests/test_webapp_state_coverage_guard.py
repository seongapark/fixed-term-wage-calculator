"""계약 시작월부터 계산월까지 근무상황이 다 없으면 계산을 막는지(웹 상태) 검증.

제보 사례: 계약기간이 7~9월인데 8월 근무상황만 첨부하면, 7월이 통째로
'만근'으로 처리되어 연가·주휴가 실제보다 많이 잡혔다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import Config
from webapp.state import AppState

FIXTURE_DIR = Path(__file__).resolve().parent.parent.parent / "demo_assets"
A_FILE = FIXTURE_DIR / "개인정보_예시(A).xlsx"
B_FILE = FIXTURE_DIR / "근무상황_예시(B).xlsx"


def _state_with_survey(start, end):
    state = AppState()
    state.config_obj = Config({
        "surveys": [{"name": "정기조사", "start": start, "end": end}],
        "rates": {"2026": {"daily_wage": 78560, "meal_allowance": 160000}},
        "holidays": ["2026-08-15"],
    })
    state.load_files(str(A_FILE), str(B_FILE))
    if state.pending_leave_groups:
        state.confirm_special_leave(["유급특별휴가"] * len(state.pending_leave_groups))
    state.batch_assign(list(state.people.keys()), "정기조사")
    return state


def test_blocks_when_contract_starts_before_covered_months():
    # 예시 B파일은 2026-08만 담고 있는데 계약은 7월부터 -> 7월 누락으로 차단.
    state = _state_with_survey("2026-07-01", "2026-09-30")
    try:
        state.prepare_calculation(2026, 8)
    except ValueError as e:
        msg = str(e)
        assert "2026-07" in msg, msg
        assert "만근" in msg, msg
        assert state.work_year is None and state.work_month is None, "차단 시 계산월이 설정되면 안 됨"
        print("OK: test_blocks_when_contract_starts_before_covered_months")
        return
    raise AssertionError("근무상황이 빠진 달이 있는데 계산이 진행됨")


def test_allows_when_contract_period_is_within_covered_months():
    state = _state_with_survey("2026-08-01", "2026-08-31")
    state.prepare_calculation(2026, 8)
    assert state.work_year == 2026 and state.work_month == 8
    print("OK: test_allows_when_contract_period_is_within_covered_months")


if __name__ == "__main__":
    test_blocks_when_contract_starts_before_covered_months()
    test_allows_when_contract_period_is_within_covered_months()
    print("ALL OK")
