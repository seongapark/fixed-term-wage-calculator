import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from webapp.state import AppState

FIXTURE_DIR = Path(__file__).resolve().parent.parent.parent / "demo_assets"
A_FILE = FIXTURE_DIR / "개인정보_예시(A).xlsx"
B_FILE = FIXTURE_DIR / "근무상황_예시(B).xlsx"


def test_load_files_populates_people_and_flags_pending_special_leave():
    state = AppState()
    result = state.load_files(str(A_FILE), str(B_FILE))

    assert len(state.people) == 5
    assert result["ambiguous_names"] == []
    assert result["has_pending_special_leave"] is True
    assert len(state.pending_leave_groups) == 1
    assert state.pending_leave_groups[0]["person_name"] == "최지은"
    print("OK: test_load_files_populates_people_and_flags_pending_special_leave")


def test_load_files_without_previous_payroll_leaves_it_empty():
    state = AppState()
    state.load_files(str(A_FILE), str(B_FILE))
    assert state.previous_payroll == {}
    print("OK: test_load_files_without_previous_payroll_leaves_it_empty")


if __name__ == "__main__":
    test_load_files_populates_people_and_flags_pending_special_leave()
    test_load_files_without_previous_payroll_leaves_it_empty()
    print("ALL OK")
