# wage_calculator/tests/test_end_to_end_v3.py
import sys
from pathlib import Path
from datetime import date
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import openpyxl
from core.config import Config
from core.parser import person_key
from core.payroll import calc_payroll
from core.models import build_event, TargetPerson
from core import leave_engine
from gui.special_leave_screen import collect_pending_groups
from output.wage_sheet import build_wage_sheet


def test_full_pipeline_with_special_leave():
    contract_start = date(2026, 7, 1)
    contract_end = date(2026, 7, 31)

    events = []
    events += [build_event("공가", d) for d in [date(2026, 7, 6), date(2026, 7, 7)]]
    events += [build_event("결근", date(2026, 7, 13))]
    # "특별휴가" 원본 종별(파싱 시점엔 유급/무급 모름) - 7/20~7/21 연속 2일
    for d in [date(2026, 7, 20), date(2026, 7, 21)]:
        events.append(build_event("특별휴가", d, source_range=(date(2026, 7, 20), date(2026, 7, 21))))

    person = TargetPerson(
        name="홍길동", birth="19900101", ssn="", bank="", account="",
        survey_name="테스트조사", contract_start=contract_start, contract_end=contract_end,
        events=events,
    )
    people = {person_key("홍길동", "19900101"): person}

    # 1) 마킹 전: "특별휴가_미정" 그룹이 하나 잡혀야 함
    groups = collect_pending_groups(people)
    assert len(groups) == 1, groups
    assert groups[0]["person_name"] == "홍길동"

    # 2) SpecialLeaveScreen._proceed()가 하는 일을 그대로 재현: 유급으로 확정
    for e in groups[0]["events"]:
        e.classified = "유급특별휴가"

    # 3) 마킹 후: 더 이상 미정 그룹이 없어야 함
    assert collect_pending_groups(people) == []

    # 4) 급여 계산
    config = Config({"surveys": [], "common": {"hourly_wage": 9820, "meal_allowance": 160000}, "holidays": []})
    result = calc_payroll(person, config, 2026, 7)

    # workdays(2026-07-01~07-31) = 23
    # public_leave_days = 공가2 + 유급특별휴가2 = 4
    # absence_days = 결근1 = 1
    # actual_workdays = 23 - 4 - (0+1) = 18
    # total_days = 18 + 0 + 4 = 22
    assert result.public_leave_days == 4, result.public_leave_days
    assert result.absence_days == 1, result.absence_days
    assert result.total_days == 22, result.total_days
    assert result.special_leave_note == "특별휴가(유급) 7/20~7/21", result.special_leave_note

    # 5) 5-1 주휴 판정에 유급특별휴가가 껴 있어도 정상적으로 발생 판정이 나와야 함
    #    (7/20 주: 월~금 중 유급특별휴가 2일 + 정상근무 3일 -> 개근 유지)
    weekly = leave_engine.compute_weekly_holiday_windows(contract_start, contract_end, person.events)
    week_of_20 = next(w for w in weekly if w.start <= date(2026, 7, 20) <= w.effective_end)
    assert week_of_20.granted, f"유급특별휴가가 껴도 주휴가 발생해야 하는데: {week_of_20.reason}"

    # 6) 엑셀 출력까지 에러 없이 완료되는지
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    ws = build_wage_sheet(wb, [result])
    assert ws["AC4"].value == "특별휴가(유급) 7/20~7/21"

    print("OK: test_full_pipeline_with_special_leave")


if __name__ == "__main__":
    test_full_pipeline_with_special_leave()
    print("ALL OK")
