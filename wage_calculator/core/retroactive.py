"""5장(소급계산): 전월 임금내역 파일 + 당월 B파일을 이용해 전월분을 다시
계산하고, 실제 지급됐던 금액과 비교한 차액(소급조정액)을 구한다."""
from dataclasses import dataclass, field

from . import date_utils
from .models import TargetPerson
from .parser import events_from_row
from .payroll import calc_payroll


@dataclass
class DepartedRetro:
    name: str
    ssn: str
    bank: str
    account: str
    prev_recalculated: int   # 전월 재계산 지급총액
    prev_paid: int           # 전월 실지급액(전월 파일에 기록된 값)
    adjustment: int          # prev_recalculated - prev_paid


@dataclass
class RetroDetail:
    """당월 대상자 1명의 소급조정 근거(재계산액/전월실지급액). 산정근거(수식)
    시트에서 소급조정액을 리터럴이 아니라 '=재계산액-전월실지급액' 수식으로
    보여주기 위한 보조 정보 - retro_adjustments(dict[person_key,int])는
    기존 형태 그대로 두고, 이 정보는 산정근거 시트를 만들 때만 추가로 쓴다."""
    recalculated: int
    prev_paid: int
    adjustment: int


@dataclass
class RetroResult:
    adjustments: dict = field(default_factory=dict)   # person_key -> int (환수/추가지급, 기존 형태 유지)
    details: dict = field(default_factory=dict)        # person_key -> RetroDetail (산정근거 시트용)
    departed: list = field(default_factory=list)       # list[DepartedRetro]
    errors: list = field(default_factory=list)         # list[str] (사람별 소급계산 실패 사유)


def current_month_adjustments(people, previous_payroll, config, prev_year, prev_month):
    """당월 로스터(people) 각자에 대해, 전월 파일에도 같은 주민번호가 있으면
    전월분을 다시 계산해 소급조정액(재계산액-전월실지급액)을 구한다. 전월
    파일에 없으면(신규입사자 등) 소급 없음(0).

    재계산은 반드시 전월 파일에 기록된 '전월 계약기간'(prev)을 써야 한다 -
    당월 계약기간(person.contract_start/end)은 이번 달에 새 조사로 재배정되며
    바뀌어 있을 수 있고, 그 경우 전월 시점 기준으로는 계약이 아직 시작 전이라
    급여기간이 통째로 비어(전월 총액이 0으로 재계산되어) 실지급액 전액이
    그대로 환수로 잡히는 사고가 난다. 이벤트(person.events)는 당월 B파일의
    더 완전한 데이터를 그대로 써야 하므로 person 것을 재사용한다.

    반환: (adjustments: dict[person_key,int], details: dict[person_key,RetroDetail],
           errors: list[str]) - 사람별 재계산이 실패해도 그 사람만 소급 0으로
    건너뛰고 나머지는 정상 처리한다(예외 하나로 전원의 소급계산이 사라지는
    것을 막기 위함). 실패 사유는 errors에 담아 호출측(app.py)이 사용자에게
    보여줄 수 있게 한다."""
    adjustments = {}
    details = {}
    errors = []
    for key, person in people.items():
        prev = previous_payroll.get(person.ssn)
        if prev is None:
            adjustments[key] = 0
            continue
        if prev["contract_start"] is None or prev["contract_end"] is None:
            # 전월 파일이 수기로 편집되는 등 계약일자 셀이 비어있으면 그 사람만
            # 건너뛴다(소급 0).
            adjustments[key] = 0
            continue
        temp_person = TargetPerson(
            name=person.name, birth=person.birth, ssn=person.ssn,
            bank=person.bank, account=person.account,
            contract_start=prev["contract_start"], contract_end=prev["contract_end"],
            events=person.events,
        )
        try:
            recalculated = calc_payroll(temp_person, config, prev_year, prev_month)
        except Exception as e:
            errors.append(f"[소급] {person.name}: {e}")
            adjustments[key] = 0
            continue
        adjustment = recalculated.total_payment - prev["total_payment"]
        adjustments[key] = adjustment
        details[key] = RetroDetail(
            recalculated=recalculated.total_payment, prev_paid=prev["total_payment"], adjustment=adjustment,
        )
    return adjustments, details, errors


def _row_birth_matches(row, expected_birth):
    """B파일 행의 '생년월일' 셀을 expected_birth("YYYY-MM-DD" 문자열)와
    비교한다. openpyxl은 날짜형 셀을 datetime으로 반환하므로 str()로 그냥
    비교하면 "1998-01-26 00:00:00" 같은 시간 포함 문자열이 되어 매칭이
    조용히 실패한다 - date_utils.parse_date로 정규화한 뒤 비교해야 한다."""
    raw = row.get("생년월일")
    if raw is None or str(raw).strip() == "":
        return False
    try:
        return date_utils.parse_date(raw).isoformat() == expected_birth
    except ValueError:
        return False  # 형식이 이상한 값은 안전하게 비매칭 처리(전체 실패 방지)


def departed_retroactive(people, previous_payroll, giganje_rows, config, prev_year, prev_month):
    """당월 로스터(people)에 없는 전월파일 인원(완전퇴사) 중, 당월 B파일에
    이름+생년월일이 일치하는 잔여 근무상황 행이 남아있는 사람만 전월분을
    재계산한다. 일치하는 행이 없으면 재계산할 새 정보가 없다는 뜻이므로
    건너뛴다(소급조정액 0, 출력도 안 함). B파일에는 주민번호가 없고
    생년월일만 있으므로, 전월파일의 주민번호로부터 생년월일을 역산해
    비교한다(동명이인이 있어도 정확히 구분하기 위함).

    반환: (results: list[DepartedRetro], errors: list[str]) - 한 명의 재계산이
    실패해도 그 사람만 목록에서 빠지고 나머지는 정상 처리한다."""
    current_ssns = {p.ssn for p in people.values() if p.ssn}
    results = []
    errors = []
    for ssn, prev in previous_payroll.items():
        if ssn in current_ssns:
            continue
        try:
            expected_birth = date_utils.birth_from_ssn(ssn)
        except ValueError:
            continue  # 주민번호 형식이 이상하면 안전하게 건너뜀(잘못된 매칭 방지)

        matched_rows = [
            row for row in giganje_rows
            if str(row.get("성명") or "").strip() == prev["name"]
            and _row_birth_matches(row, expected_birth)
        ]
        if not matched_rows:
            continue
        if prev["contract_start"] is None or prev["contract_end"] is None:
            # current_month_adjustments와 동일한 이유로, 계약일자가 비어있는
            # 사람만 건너뛴다(전체 소급계산이 죽는 것을 막기 위함).
            continue

        temp_person = TargetPerson(
            name=prev["name"], birth=expected_birth, ssn=ssn,
            bank=prev["bank"], account=prev["account"],
            contract_start=prev["contract_start"], contract_end=prev["contract_end"],
        )
        for row in matched_rows:
            temp_person.events.extend(events_from_row(row))

        try:
            recalculated = calc_payroll(temp_person, config, prev_year, prev_month)
        except Exception as e:
            errors.append(f"[소급-퇴사자] {prev['name']}: {e}")
            continue

        results.append(DepartedRetro(
            name=prev["name"], ssn=ssn, bank=prev["bank"], account=prev["account"],
            prev_recalculated=recalculated.total_payment,
            prev_paid=prev["total_payment"],
            adjustment=recalculated.total_payment - prev["total_payment"],
        ))
    return results, errors


def compute_retroactive(people, previous_payroll, giganje_rows, config, prev_year, prev_month):
    """당월 대상자 소급조정액 + 완전퇴사자 소급 내역을 한 번에 계산한다.
    반환: RetroResult(adjustments, details, departed, errors)"""
    adjustments, details, adj_errors = current_month_adjustments(
        people, previous_payroll, config, prev_year, prev_month,
    )
    departed, dep_errors = departed_retroactive(
        people, previous_payroll, giganje_rows, config, prev_year, prev_month,
    )
    return RetroResult(
        adjustments=adjustments, details=details, departed=departed,
        errors=adj_errors + dep_errors,
    )
