"""5장(소급계산): 전월 임금내역 파일 + 당월 B파일을 이용해 전월분을 다시
계산하고, 실제 지급됐던 금액과 비교한 차액(소급조정액)을 구한다."""
from dataclasses import dataclass

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


def current_month_adjustments(people, previous_payroll, config, prev_year, prev_month):
    """당월 로스터(people) 각자에 대해, 전월 파일에도 같은 주민번호가 있으면
    전월분을 다시 계산해 소급조정액(재계산액-전월실지급액)을 구한다. 전월
    파일에 없으면(신규입사자 등) 소급 없음(0)."""
    adjustments = {}
    for key, person in people.items():
        prev = previous_payroll.get(person.ssn)
        if prev is None:
            adjustments[key] = 0
            continue
        recalculated = calc_payroll(person, config, prev_year, prev_month)
        adjustments[key] = recalculated.total_payment - prev["total_payment"]
    return adjustments


def departed_retroactive(people, previous_payroll, giganje_rows, config, prev_year, prev_month):
    """당월 로스터(people)에 없는 전월파일 인원(완전퇴사) 중, 당월 B파일에
    이름+생년월일이 일치하는 잔여 근무상황 행이 남아있는 사람만 전월분을
    재계산한다. 일치하는 행이 없으면 재계산할 새 정보가 없다는 뜻이므로
    건너뛴다(소급조정액 0, 출력도 안 함). B파일에는 주민번호가 없고
    생년월일만 있으므로, 전월파일의 주민번호로부터 생년월일을 역산해
    비교한다(동명이인이 있어도 정확히 구분하기 위함)."""
    current_ssns = {p.ssn for p in people.values() if p.ssn}
    results = []
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
            and str(row.get("생년월일") or "").strip() == expected_birth
        ]
        if not matched_rows:
            continue

        temp_person = TargetPerson(
            name=prev["name"], birth=expected_birth, ssn=ssn,
            bank=prev["bank"], account=prev["account"],
            contract_start=prev["contract_start"], contract_end=prev["contract_end"],
        )
        for row in matched_rows:
            temp_person.events.extend(events_from_row(row))

        recalculated = calc_payroll(temp_person, config, prev_year, prev_month)
        results.append(DepartedRetro(
            name=prev["name"], ssn=ssn, bank=prev["bank"], account=prev["account"],
            prev_recalculated=recalculated.total_payment,
            prev_paid=prev["total_payment"],
            adjustment=recalculated.total_payment - prev["total_payment"],
        ))
    return results


def compute_retroactive(people, previous_payroll, giganje_rows, config, prev_year, prev_month):
    """당월 대상자 소급조정액 + 완전퇴사자 소급 내역을 한 번에 계산한다.
    반환: (adjustments: dict[person_key, int], departed: list[DepartedRetro])"""
    adjustments = current_month_adjustments(people, previous_payroll, config, prev_year, prev_month)
    departed = departed_retroactive(people, previous_payroll, giganje_rows, config, prev_year, prev_month)
    return adjustments, departed
