import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import Config
import webapp.state as state_module
from webapp.state import AppState

FIXTURE_DIR = Path(__file__).resolve().parent.parent.parent / "demo_assets"
A_FILE = FIXTURE_DIR / "개인정보_예시(A).xlsx"
B_FILE = FIXTURE_DIR / "근무상황_예시(B).xlsx"


def _config_with_survey():
    return Config({
        "surveys": [{"name": "8월 정기조사", "start": "2026-08-01", "end": "2026-08-31"}],
        "rates": {"2026": {"daily_wage": 78560, "meal_allowance": 160000}},
        "holidays": ["2026-08-15"],
    })


def _calculated_state():
    state = AppState()
    state.config_obj = _config_with_survey()
    state.load_files(str(A_FILE), str(B_FILE))
    state.confirm_special_leave([{"paid": True, "accrual": True}] * len(state.pending_leave_groups))
    keys = list(state.people.keys())
    state.batch_assign(keys, "8월 정기조사")
    state.prepare_calculation(2026, 8)
    state.run_calculation()
    return state


def test_download_saves_workbook_to_configured_downloads_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(state_module, "downloads_dir", lambda: str(tmp_path))
    state = _calculated_state()

    saved = state.download()

    assert len(saved) == 1
    assert Path(saved[0]).exists()
    assert Path(saved[0]).parent == tmp_path
    print("OK: test_download_saves_workbook_to_configured_downloads_dir")
