import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import Config
from core.payroll import PayrollResult
from core.retroactive import DepartedRetro
from output.build import build_workbook, build_departed_workbook, departed_output_filename


def _config():
    return Config({"surveys": [], "rates": {"2026": {"daily_wage": 78560, "meal_allowance": 160000}}, "holidays": []})


def _result():
    return PayrollResult(
        name="김철수", birth="19900101", ssn="", bank="", account="", survey_name="테스트조사",
        period_start=date(2026, 7, 1), period_end=date(2026, 7, 31),
        contract_start=date(2026, 7, 1), contract_end=date(2026, 7, 31),
        daily_wage=78560, actual_workdays=23, public_leave_days=0, paid_holiday_days=0,
        absence_days=0, total_days=23, late_out_minutes=0, weekly_holiday_days=4,
        calendar_month_days=31, meal_eligible_days=31, remaining_leave_days=0.0,
        is_final_month=False, gross_pay=1806880, late_out_deduction=0, base_pay=1806880,
        weekly_holiday_pay=314240, meal_allowance=160000, leave_compensation=0,
        total_payment=2281120,
    )


def test_build_workbook_includes_wage_and_evidence_sheets():
    wb = build_workbook([_result()], _config())
    assert "임금내역(월중)" in wb.sheetnames, wb.sheetnames
    assert "산정근거(수식)" in wb.sheetnames, wb.sheetnames
    print("OK: test_build_workbook_includes_wage_and_evidence_sheets")


def test_build_departed_workbook_includes_both_sheets():
    d = DepartedRetro(name="최도영", ssn="980126-2641395", bank="", account="",
                       prev_recalculated=1950000, prev_paid=2000000, adjustment=-50000)
    wb = build_departed_workbook([d])
    assert "소급대상자 내역" in wb.sheetnames
    assert "산정근거(수식)" in wb.sheetnames
    print("OK: test_build_departed_workbook_includes_both_sheets")


def test_departed_output_filename():
    assert departed_output_filename(2026, 7) == "'26년 7월 소급대상자 내역.xlsx"
    print("OK: test_departed_output_filename")


if __name__ == "__main__":
    test_build_workbook_includes_wage_and_evidence_sheets()
    test_build_departed_workbook_includes_both_sheets()
    test_departed_output_filename()
    print("ALL OK")
