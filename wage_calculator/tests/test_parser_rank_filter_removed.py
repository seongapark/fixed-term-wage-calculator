import sys
from pathlib import Path
import tempfile
import os

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import openpyxl
from core.parser import load_giganje_rows


def _write_b_file(path):
    wb = openpyxl.Workbook()
    ws = wb.active
    headers = ["소속", "직급", "성명", "생년월일", "종별", "사용기간(날짜)", "사용시간(시분)", "사유", "연락처", "결재상태", "비고"]
    ws.append(headers)
    ws.append(["정보통계과", "기간제근로자", "김철수", "1990-01-01", "연가", "2026-07-06", None, None, "", "결재완료", None])
    ws.append(["정보통계과", "일반직", "박정규", "1985-05-05", "연가", "2026-07-06", None, None, "", "결재완료", None])
    wb.save(path)


def test_non_giganje_rank_rows_are_kept():
    fd, path = tempfile.mkstemp(suffix=".xlsx")
    os.close(fd)
    try:
        _write_b_file(path)
        rows = load_giganje_rows(path)
        names = [r["성명"] for r in rows]
        assert "김철수" in names, names
        assert "박정규" in names, "직급이 '기간제'가 아니어도 행이 반환되어야 함: " + str(names)
        assert len(rows) == 2, rows
        print("OK: test_non_giganje_rank_rows_are_kept")
    finally:
        os.remove(path)


if __name__ == "__main__":
    test_non_giganje_rank_rows_are_kept()
    print("ALL OK")
