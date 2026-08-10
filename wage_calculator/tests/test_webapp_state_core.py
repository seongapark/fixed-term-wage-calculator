import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from webapp.state import AppState


def test_initial_state_has_empty_collections():
    state = AppState()
    assert state.employees == {}
    assert state.people == {}
    assert state.results == []
    assert state.work_year is None
    assert state.work_month is None
    assert state.pending_leave_groups == []
    print("OK: test_initial_state_has_empty_collections")


def test_reset_clears_mutated_fields_but_keeps_config():
    state = AppState()
    original_config = state.config_obj
    state.employees = {"홍길동": []}
    state.work_year = 2026
    state.work_month = 8
    state.results = ["더미"]

    state.reset()

    assert state.employees == {}
    assert state.work_year is None
    assert state.work_month is None
    assert state.results == []
    assert state.config_obj is original_config
    print("OK: test_reset_clears_mutated_fields_but_keeps_config")


if __name__ == "__main__":
    test_initial_state_has_empty_collections()
    test_reset_clears_mutated_fields_but_keeps_config()
    print("ALL OK")
