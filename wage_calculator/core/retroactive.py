"""5장(소급계산): 전월 임금내역 파일 + 당월 B파일을 이용해 전월분을 다시
계산하고, 실제 지급됐던 금액과 비교한 차액(소급조정액)을 구한다."""
from dataclasses import dataclass

from . import date_utils
from .models import TargetPerson
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
