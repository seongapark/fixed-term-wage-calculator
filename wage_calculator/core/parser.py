"""3-A/3-B 입력 파일(A: 개인정보, B: 근무상황) 로더."""
import openpyxl

from . import date_utils, mapping, pending
from .models import Employee, TargetPerson, build_event
from output.wage_sheet import COL, SHEET_NAME, DATA_START_ROW


def _header_index(ws):
    headers = {}
    for c in range(1, ws.max_column + 1):
        v = ws.cell(row=1, column=c).value
        if v is not None:
            headers[str(v).strip()] = c
    return headers


def _row_dict(ws, row, headers):
    return {name: ws.cell(row=row, column=col).value for name, col in headers.items()}


def load_employees(path) -> dict:
    """A파일(개인정보) -> {성명: [Employee, ...]}(동명이인 대비 리스트).

    '생년월일' 컬럼은 필수는 아니지만, 있으면 동명이인을 구분하는 데 사용된다.
    """
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.worksheets[0]
    headers = _header_index(ws)
    required = ["성명", "주민번호", "은행", "계좌번호"]
    missing = [h for h in required if h not in headers]
    if missing:
        raise ValueError(f"A파일(개인정보)에 필수 컬럼이 없습니다: {missing}")
    has_birth = "생년월일" in headers

    employees = {}
    for r in range(2, ws.max_row + 1):
        row = _row_dict(ws, r, headers)
        name = row.get("성명")
        if name is None or str(name).strip() == "":
            continue
        name = str(name).strip()
        # 생년월일 셀도 B파일과 동일하게 정규화한다 - 이 값(Employee.birth)이
        # TargetPerson.birth -> PayrollResult.birth로 그대로 흘러가 person_key(),
        # 산정근거 화면의 원본 매칭 등 생년월일을 비교하는 모든 곳의 기준값이
        # 되므로, 여기서 안 고치면 B파일 쪽만 고쳐도 계속 어긋난다.
        raw_birth = row.get("생년월일") if has_birth else None
        if raw_birth in (None, ""):
            birth = ""
        else:
            try:
                birth = date_utils.parse_date(raw_birth).isoformat()
            except ValueError:
                birth = str(raw_birth).strip()
        emp = Employee(
            name=name,
            ssn=str(row.get("주민번호") or "").strip(),
            bank=str(row.get("은행") or "").strip(),
            account=str(row.get("계좌번호") or "").strip(),
            birth=birth,
        )
        employees.setdefault(name, []).append(emp)
    return employees


def load_giganje_rows(path) -> list:
    """B파일(근무상황) 로드(원본 dict 리스트).

    직급으로 거르지 않는다 - A파일(개인정보)이 이미 급여계산 대상자만
    추려서 관리되므로, build_target_people()에서 이름+생년월일로 A파일과
    매칭되는 행만 자연스럽게 급여 계산에 반영된다.
    """
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.worksheets[0]
    headers = _header_index(ws)
    required = ["소속", "직급", "성명", "생년월일", "종별", "사용기간(날짜)", "사용시간(시분)"]
    missing = [h for h in required if h not in headers]
    if missing:
        raise ValueError(f"B파일(근무상황)에 필수 컬럼이 없습니다: {missing}")

    rows = []
    for r in range(2, ws.max_row + 1):
        row = _row_dict(ws, r, headers)
        name = row.get("성명")
        if name is None or str(name).strip() == "":
            continue
        row["성명"] = str(name).strip()
        rows.append(row)
    return rows


def person_key(name: str, birth: str) -> str:
    return f"{name}::{birth}"


def display_label(name: str, birth: str, all_names: list) -> str:
    """동명이인이 있는 경우에만 성명 뒤에 생년월일을 붙여 화면에 구분 표시."""
    if all_names.count(name) > 1:
        return f"{name}({birth})" if birth else name
    return name


def build_target_people(giganje_rows, employees: dict):
    """A파일(개인정보) 전원을 급여 대상자 로스터로 삼고, B파일(근무상황) 전체 행의
    사용 이력을 이름/생년월일로 매칭해 이벤트로 붙인다.

    B파일(근무상황현황)은 실제로는 "사용 이력이 있는 건(행)만" 나열되는 방식이라,
    이번 달에 조퇴/외출/공가 등 아무 이력이 없는 사람(만근자)은 B파일에 행 자체가
    없다. 로스터를 B파일 기준으로 잡으면 그런 만근자가 급여 계산에서 통째로
    빠지므로, 로스터는 반드시 A파일 기준으로 잡고 B파일은 이벤트 매칭용
    보조데이터로만 사용한다. 매칭되는 이벤트가 하나도 없으면 공제 없는 만근으로
    남아 풀로 급여가 지급된다.

    키는 '성명::생년월일' 문자열(동명이인이어도 서로 다른 사람으로 분리됨).
    반환값: (people, missing_names, ambiguous_names)
      - missing_names: B파일 근무상황에는 있는데 A파일에 아예 없는 성명(오탈자/누락 의심)
      - ambiguous_names: A파일에 동명이인이 있는데 생년월일로 구분할 수 없는 성명
        (잘못된 사람에게 계좌/주민번호가 붙는 사고를 막기 위해 로스터에서 제외됨 ->
        A파일 보완 전까지 급여 계산 불가)
    """
    people = {}
    ambiguous_names = []
    name_index = {}  # 성명 -> [TargetPerson, ...] (로스터에 실제로 올라간 사람만)

    for name, candidates in employees.items():
        if len(candidates) == 1:
            emp = candidates[0]
            person = TargetPerson(
                name=name, birth=emp.birth, ssn=emp.ssn, bank=emp.bank, account=emp.account,
            )
            people[person_key(name, emp.birth)] = person
            name_index[name] = [person]
            continue

        # A파일 내 동명이인: 생년월일이 전원 채워져 있고 서로 달라야 안전하게 구분 가능.
        # 그렇지 않으면 절대 임의로 매칭하지 않는다(잘못된 사람에게 계좌/주민번호가
        # 붙는 사고를 막기 위함).
        births = [c.birth for c in candidates]
        if any(not b for b in births) or len(set(births)) != len(births):
            ambiguous_names.append(name)
            continue

        persons = []
        for emp in candidates:
            person = TargetPerson(
                name=name, birth=emp.birth, ssn=emp.ssn, bank=emp.bank, account=emp.account,
            )
            people[person_key(name, emp.birth)] = person
            persons.append(person)
        name_index[name] = persons

    missing_names = []

    for row in giganje_rows:
        name = row["성명"]
        raw_birth = row.get("생년월일")
        # openpyxl은 날짜형 셀을 datetime으로 반환하므로 str()로 그냥 비교하면
        # "1995-05-05 00:00:00" 같은 시간 포함 문자열이 되어 동명이인 매칭이
        # 조용히 실패한다(core/retroactive.py의 _row_birth_matches와 동일한 문제).
        # date_utils.parse_date로 정규화한 뒤 비교해야 한다. 형식이 이상한
        # 값은 기존 동작대로 원문 문자열 비교로 안전하게 폴백한다.
        try:
            birth = date_utils.parse_date(raw_birth).isoformat() if raw_birth not in (None, "") else ""
        except ValueError:
            birth = str(raw_birth or "").strip()

        candidates = name_index.get(name, [])
        person = None
        if len(candidates) == 1:
            person = candidates[0]
        elif len(candidates) > 1:
            person = people.get(person_key(name, birth))

        if person is None:
            if name not in ambiguous_names and name not in missing_names:
                missing_names.append(name)
            continue

        person.dept = str(row.get("소속") or "") or person.dept
        person.rank = str(row.get("직급") or "") or person.rank

        person.events.extend(events_from_row(row))

    return people, missing_names, ambiguous_names


def events_from_row(row) -> list:
    """B파일 원본 행 1개(dict)를 LeaveEvent 리스트로 변환. 사용 내역이 없는
    (만근) 행이면 빈 리스트. build_target_people()의 매칭 로직과 분리해 두면,
    소급계산(완전퇴사자)처럼 로스터 밖의 임시 인물에게도 같은 파싱 규칙을
    재사용할 수 있다."""
    raw_category = row.get("종별")
    date_field = row.get("사용기간(날짜)")
    if raw_category is None or str(raw_category).strip() == "" or date_field is None:
        return []
    raw_category = str(raw_category).strip()

    time_field = row.get("사용시간(시분)")
    time_range = date_utils.parse_time_range(time_field)
    start_d, end_d = date_utils.parse_date_range(date_field)

    events = []
    if time_range is not None:
        t_start, t_end = time_range
        minutes = date_utils.deduct_minutes(t_start, t_end)
        events.append(build_event(raw_category, start_d, t_start, t_end, minutes, source_row=row))
    else:
        for d in date_utils.daterange(start_d, end_d):
            if d.weekday() < 5:
                events.append(build_event(raw_category, d, source_range=(start_d, end_d), source_row=row))

    _apply_saved_decision(row, events)
    return events


def _apply_saved_decision(row, events) -> None:
    """전월 결과파일에 저장된 판정을 이벤트에 되살린다.

    양쪽 칸이 다 채워져 있을 때만 판정으로 인정한다 - 한 칸만 있으면 수기 편집
    중일 수 있으므로 다시 묻는 편이 안전하다. 인식된 9종의 분류는 덮어쓰지
    않는다(덮어쓰면 "연가"의 잔량 소진이 사라진다)."""
    paid_text = str(row.get(pending.PAID_COL) or "").strip()
    accrual_text = str(row.get(pending.ACCRUAL_COL) or "").strip()
    if paid_text not in (pending.PAID_YES, pending.PAID_NO):
        return
    if accrual_text not in (pending.ACCRUAL_YES, pending.ACCRUAL_NO):
        return
    paid = paid_text == pending.PAID_YES
    accrual = accrual_text == pending.ACCRUAL_YES
    for e in events:
        e.unpaid = not paid
        e.breaks = not accrual
        e.decided = True
        if mapping.is_pending(e.classified):
            e.classified = "유급특별휴가" if paid else "무급특별휴가"


def load_previous_payroll(path) -> dict:
    """이 프로그램이 직전에 생성한 임금내역(월중) 엑셀을 다시 읽어, 소급계산에
    필요한 전월 정보를 주민번호를 키로 돌려준다. 이 파일은 프로그램이 직접
    만든 것이라 헤더 텍스트가 아니라 output/wage_sheet.py의 COL과 동일한
    고정 열 위치로 읽는다(헤더가 병합 셀이라 텍스트 파싱이 불안정함)."""
    wb = openpyxl.load_workbook(path, data_only=True)
    if SHEET_NAME not in wb.sheetnames:
        raise ValueError(f"전월 임금내역 파일에 '{SHEET_NAME}' 시트가 없습니다.")
    ws = wb[SHEET_NAME]

    result = {}
    for r in range(DATA_START_ROW, ws.max_row + 1):
        name = ws.cell(row=r, column=COL["name"]).value
        ssn = ws.cell(row=r, column=COL["ssn"]).value
        if name is None or str(name).strip() == "" or ssn is None or str(ssn).strip() == "":
            continue
        ssn = str(ssn).strip()
        contract_start = ws.cell(row=r, column=COL["contract_start"]).value
        contract_end = ws.cell(row=r, column=COL["contract_end"]).value
        result[ssn] = {
            "ssn": ssn,
            "name": str(name).strip(),
            "contract_start": date_utils.parse_date(contract_start) if contract_start else None,
            "contract_end": date_utils.parse_date(contract_end) if contract_end else None,
            "total_payment": ws.cell(row=r, column=COL["total_payment"]).value or 0,
            "bank": ws.cell(row=r, column=COL["bank"]).value or "",
            "account": ws.cell(row=r, column=COL["account"]).value or "",
        }
    return result
