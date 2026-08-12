"""core.parser.load_employees()가 A파일(개인정보)의 '생년월일' 셀을 정규화하는지
검증한다. openpyxl은 날짜형 셀을 datetime으로 반환하므로, load_employees()가
str()로만 변환하면 Employee.birth가 "1995-05-05 00:00:00"처럼 시각이 붙은
문자열이 된다. 이 값은 TargetPerson.birth -> PayrollResult.birth로 그대로
흘러가 person_key(), evidence_for()의 원본 매칭 등 생년월일을 비교하는 모든
곳에서 조용히 실패한다(core/retroactive.py의 _row_birth_matches, 그리고
webapp/state.py·core/parser.py의 build_target_people에서 이미 같은 원인의
버그를 두 번 고쳤음 - 이 테스트는 세 번째 발생 지점인 A파일 로더 자체를 잡는다)."""
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import openpyxl
from core.parser import load_employees


def _build_a_file(path, birth_cell_value):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["성명", "생년월일", "주민번호", "은행", "계좌번호"])
    ws.append(["장수진", birth_cell_value, "950505-2234567", "국민은행", "110-123-456789"])
    wb.save(path)


def test_load_employees_normalizes_plain_text_birth_cell():
    """대조군: 텍스트 셀은 지금도 정상 동작한다."""
    fd, path = tempfile.mkstemp(suffix=".xlsx")
    os.close(fd)
    try:
        _build_a_file(path, "1995-05-05")
        employees = load_employees(path)
        emp = employees["장수진"][0]
        assert emp.birth == "1995-05-05", emp.birth
        print("OK: test_load_employees_normalizes_plain_text_birth_cell")
    finally:
        os.remove(path)


def test_load_employees_normalizes_real_date_birth_cell():
    """실제 버그 재현: 생년월일 셀이 엑셀 날짜형이면 openpyxl이 datetime으로
    돌려주므로, 정규화 없이 str()만 하면 "1995-05-05 00:00:00"이 되어
    person_key/evidence_for 등 모든 후속 생년월일 비교가 깨진다."""
    fd, path = tempfile.mkstemp(suffix=".xlsx")
    os.close(fd)
    try:
        _build_a_file(path, datetime(1995, 5, 5))
        employees = load_employees(path)
        emp = employees["장수진"][0]
        assert emp.birth == "1995-05-05", (
            f"생년월일이 정규화되지 않음: {emp.birth!r} "
            "(시각이 붙으면 person_key/산정근거 화면 매칭이 전부 깨짐)"
        )
        print("OK: test_load_employees_normalizes_real_date_birth_cell")
    finally:
        os.remove(path)


if __name__ == "__main__":
    test_load_employees_normalizes_plain_text_birth_cell()
    test_load_employees_normalizes_real_date_birth_cell()
    print("ALL OK")
