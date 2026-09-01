import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import openpyxl

from webapp.state import AppState


def _write_a(path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["성명", "주민번호", "은행", "계좌번호", "생년월일"])
    ws.append(["홍길동", "900101-1234567", "농협", "123-456", "1990-01-01"])
    wb.save(path)


def _write_b(path, rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["소속", "직급", "성명", "생년월일", "종별", "사용기간(날짜)", "사용시간(시분)", "사유", "비고"])
    for row in rows:
        ws.append(row)
    wb.save(path)


def _state(tmp_path, rows):
    a, b = tmp_path / "a.xlsx", tmp_path / "b.xlsx"
    _write_a(a)
    _write_b(b, rows)
    state = AppState()
    state.load_files(str(a), str(b))
    return state


def _row(category, reason="", note=""):
    return ["본부", "기간제", "홍길동", "1990-01-01", category, "2026-08-10", None, reason, note]


def test_unknown_category_group_has_no_defaults(tmp_path):
    state = _state(tmp_path, [_row("경조사휴가")])
    groups = state.special_leave_groups()
    assert len(groups) == 1
    assert groups[0]["raw_category"] == "경조사휴가"
    assert groups[0]["default_paid"] is None
    assert groups[0]["default_accrual"] is None


def test_known_category_with_reason_carries_defaults(tmp_path):
    state = _state(tmp_path, [_row("연가", reason="집안일")])
    groups = state.special_leave_groups()
    assert len(groups) == 1
    assert groups[0]["reason"] == "집안일"
    assert groups[0]["default_paid"] is True
    assert groups[0]["default_accrual"] is True


def test_known_category_without_reason_is_not_pending(tmp_path):
    state = _state(tmp_path, [_row("연가")])
    assert state.special_leave_groups() == []


def test_confirm_sets_axes(tmp_path):
    state = _state(tmp_path, [_row("경조사휴가")])
    state.confirm_special_leave([{"paid": False, "accrual": False}])
    events = [e for p in state.people.values() for e in p.events]
    assert events[0].unpaid is True
    assert events[0].breaks is True


def test_confirm_rejects_wrong_length(tmp_path):
    state = _state(tmp_path, [_row("경조사휴가")])
    try:
        state.confirm_special_leave([])
    except ValueError:
        return
    raise AssertionError("개수가 다르면 ValueError")


def test_confirm_rejects_missing_choice(tmp_path):
    state = _state(tmp_path, [_row("경조사휴가")])
    try:
        state.confirm_special_leave([{"paid": True, "accrual": None}])
    except ValueError:
        return
    raise AssertionError("미선택이면 ValueError")


def test_prepare_calculation_blocks_when_undecided(tmp_path):
    state = _state(tmp_path, [_row("경조사휴가")])
    try:
        state.prepare_calculation(2026, 8)
    except ValueError as e:
        assert "확인" in str(e)
        return
    raise AssertionError("미확인 건이 있으면 계산을 막아야 한다")
