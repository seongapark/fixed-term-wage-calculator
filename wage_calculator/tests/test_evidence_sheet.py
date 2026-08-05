import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import openpyxl
from core.config import Config
from core.parser import person_key
from core.payroll import PayrollResult
from output.evidence_sheet import build_evidence_sheet, COL


def _config():
    return Config({"surveys": [], "rates": {"2026": {"hourly_wage": 9820, "meal_allowance": 160000}}, "holidays": []})


def _result():
    return PayrollResult(
        name="김철수", birth="19900101", ssn="", bank="", account="", survey_name="테스트조사",
        period_start=date(2026, 7, 1), period_end=date(2026, 7, 31),
        contract_start=date(2026, 7, 1), contract_end=date(2026, 7, 31),
        daily_wage=78560, actual_workdays=23, public_leave_days=0, paid_holiday_days=0,
        absence_days=0, total_days=23, late_out_minutes=120, weekly_holiday_days=4,
        calendar_month_days=31, meal_eligible_days=31, remaining_leave_days=1.5,
        is_final_month=True, gross_pay=1806880, late_out_deduction=19630, base_pay=1787250,
        weekly_holiday_pay=314240, meal_allowance=160000, leave_compensation=137310,
        total_payment=2398800,
    )


def test_formula_cells_reference_same_row_inputs():
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    result = _result()
    key = person_key(result.name, result.birth)
    ws = build_evidence_sheet(wb, [result], _config(), retro_adjustments={key: -10000})

    row = 2  # DATA_START_ROW
    assert ws.cell(row=row, column=COL["hourly_wage"]).value == 9820
    assert ws.cell(row=row, column=COL["daily_wage"]).value == "=ROUNDDOWN(C2*8,0)"
    assert ws.cell(row=row, column=COL["gross_pay"]).value == "=L2*D2"
    assert ws.cell(row=row, column=COL["late_out_deduction"]).value == "=ROUNDDOWN(C2/60*E2,-1)"
    assert ws.cell(row=row, column=COL["base_pay"]).value == "=ROUNDDOWN(N2-O2,-1)"
    assert ws.cell(row=row, column=COL["total_payment"]).value == "=ROUNDDOWN(P2+Q2+R2+S2,-1)"
    assert ws.cell(row=row, column=COL["retro_adjustment"]).value == -10000
    assert ws.cell(row=row, column=COL["final_payment"]).value == "=T2+U2"
    print("OK: test_formula_cells_reference_same_row_inputs")


if __name__ == "__main__":
    test_formula_cells_reference_same_row_inputs()
    print("ALL OK")
