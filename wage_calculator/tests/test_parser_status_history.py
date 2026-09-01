import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import openpyxl

from core import pending
from core.parser import load_previous_status_rows, merge_status_rows
from output.raw_sheet import COLUMNS, build_raw_status_sheet


def _row(name, category, period, time_field=None, reason="", paid=None, accrual=None):
    row = {
        "소속": "본부", "직급": "기간제", "성명": name, "생년월일": "1990-01-01",
        "종별": category, "사용기간(날짜)": period, "사용시간(시분)": time_field,
        "사유": reason, "연락처": "", "결재상태": "완료", "비고": "",
    }
    if paid is not None:
        row[pending.PAID_COL] = paid
        row[pending.ACCRUAL_COL] = accrual
    return row


def _save(tmp_path, rows, name="prev.xlsx"):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    build_raw_status_sheet(wb, rows)
    path = tmp_path / name
    wb.save(path)
    return str(path)


def test_load_returns_rows_with_same_shape(tmp_path):
    path = _save(tmp_path, [_row("홍길동", "연가", "2026-07-10")])
    rows = load_previous_status_rows(path)
    assert len(rows) == 1
    assert rows[0]["성명"] == "홍길동"
    assert rows[0]["종별"] == "연가"
    assert set(COLUMNS) <= set(rows[0].keys())


def test_load_returns_decision_columns(tmp_path):
    path = _save(tmp_path, [_row("홍길동", "경조사휴가", "2026-07-10", paid="유급", accrual="발생")])
    rows = load_previous_status_rows(path)
    assert rows[0][pending.PAID_COL] == "유급"
    assert rows[0][pending.ACCRUAL_COL] == "발생"


def test_load_missing_sheet_returns_empty(tmp_path):
    wb = openpyxl.Workbook()
    path = tmp_path / "no_sheet.xlsx"
    wb.save(path)
    assert load_previous_status_rows(str(path)) == []


def test_merge_puts_previous_first_then_current():
    prev = [_row("홍길동", "연가", "2026-07-10")]
    cur = [_row("홍길동", "조퇴", "2026-08-10", time_field="15:00~18:00")]
    merged = merge_status_rows(cur, prev)
    assert [r["종별"] for r in merged] == ["연가", "조퇴"]


def test_merge_drops_duplicate_and_keeps_current():
    prev = [_row("홍길동", "연가", "2026-07-10", reason="옛 사유")]
    cur = [_row("홍길동", "연가", "2026-07-10", reason="새 사유")]
    merged = merge_status_rows(cur, prev)
    assert len(merged) == 1
    assert merged[0]["사유"] == "새 사유"


def test_merge_treats_different_person_as_different_row():
    prev = [_row("홍길동", "연가", "2026-07-10")]
    cur = [_row("김철수", "연가", "2026-07-10")]
    assert len(merge_status_rows(cur, prev)) == 2


def test_merge_treats_different_time_as_different_row():
    prev = [_row("홍길동", "조퇴", "2026-07-10", time_field="15:00~18:00")]
    cur = [_row("홍길동", "조퇴", "2026-07-10", time_field="16:00~18:00")]
    assert len(merge_status_rows(cur, prev)) == 2


def test_merge_without_previous_returns_current():
    cur = [_row("홍길동", "연가", "2026-08-10")]
    assert merge_status_rows(cur, []) == cur


if __name__ == "__main__":
    print("pytest로 실행하세요(tmp_path 픽스처 사용)")
