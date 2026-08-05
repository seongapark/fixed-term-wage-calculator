import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import Config
from core.parser import load_employees, load_giganje_rows, build_target_people, person_key
from core.payroll import calc_payroll
from output.build import build_workbook, output_filename

BASE = Path(__file__).resolve().parent.parent.parent
A_FILE = BASE / "A_개인정보_입력양식_예시.xlsx"
B_FILE = BASE / "B_근무상황_입력양식_예시.xlsx"


def main():
    employees = load_employees(A_FILE)
    rows = load_giganje_rows(B_FILE)
    people, missing, ambiguous = build_target_people(rows, employees)

    print(f"[기간제 대상자 수] {len(people)}명")
    print(f"[A파일 미존재(경고 대상)] {missing}")
    print(f"[동명이인 구분 불가(경고 대상)] {ambiguous}")
    print()

    config = Config.load()
    config.add_or_update_survey("테스트조사", "2026-01-05", "2026-09-30")
    survey = config.get_survey("테스트조사")
    contract_start = date.fromisoformat(survey["start"])
    contract_end = date.fromisoformat(survey["end"])
    config.set_year_rates(2026, 9820, 160000)

    for name, person in people.items():
        person.survey_name = "테스트조사"
        person.contract_start = contract_start
        person.contract_end = contract_end

    all_results = [calc_payroll(p, config, 2026, 7) for p in people.values()]
    wb = build_workbook(all_results, rows)
    out_path = Path(__file__).resolve().parent / output_filename(2026, 7)
    wb.save(out_path)
    print(f"[엑셀 저장] {out_path}")
    print()

    by_name = {p.name: p for p in people.values()}
    for name in ["이유영", "이수영", "김서진", "김유진", "강도우", "최현우", "윤성아"]:
        person = by_name[name]
        result = calc_payroll(person, config, 2026, 7)
        print(f"=== {name} ({person.rank}) ===")
        print(f"  급여계산기간: {result.period_start} ~ {result.period_end}")
        print(f"  실출근={result.actual_workdays} 공가={result.public_leave_days} "
              f"유급휴일={result.paid_holiday_days} 결근={result.absence_days} 계={result.total_days}")
        print(f"  조퇴외출(분)={result.late_out_minutes} 주휴(일)={result.weekly_holiday_days} "
              f"월력상={result.calendar_month_days} 식대해당일={result.meal_eligible_days} "
              f"잔여연가(일)={result.remaining_leave_days:.4f}")
        print(f"  급여액={result.gross_pay} 조퇴외출공제={result.late_out_deduction} 기본급={result.base_pay}")
        print(f"  주휴수당={result.weekly_holiday_pay} 정액급식비={result.meal_allowance} "
              f"연가보상비={result.leave_compensation}")
        print(f"  지급총액={result.total_payment}")
        print("  -- 주휴 산정근거 --")
        for w in result.weekly_windows:
            print(f"    창{w.index} {w.start}~{w.effective_end} 근무일수={w.workdays} "
                  f"결근={w.absence_days} 공가={w.public_leave_days} 병가={w.sick_full_days} "
                  f"판정={'O' if w.granted else 'X'} 사유={w.reason} 귀속={w.accrual_year}-{w.accrual_month}")
        print()


if __name__ == "__main__":
    main()
