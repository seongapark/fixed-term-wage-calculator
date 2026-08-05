import sys
from pathlib import Path
from datetime import date
import tempfile
import os

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import openpyxl
from core.parser import load_previous_payroll
from core.payroll import PayrollResult
from output.wage_sheet import build_wage_sheet


def _make_result(name, ssn, total_payment):
    return PayrollResult(
        name=name, birth="19900101", ssn=ssn, bank="하나은행", account="1234567890",
        survey_name="테스트조사",
        period_start=date(2026, 6, 1), period_end=date(2026, 6, 30),
        contract_start=date(2026, 6, 1), contract_end=date(2026, 6, 30),
        daily_wage=78560, actual_workdays=20, public_leave_days=0, paid_holiday_days=0,
        absence_days=0, total_days=20, late_out_minutes=0, weekly_holiday_days=4,
        calendar_month_days=30, meal_eligible_days=30, remaining_leave_days=0.0,
        is_final_month=False, gross_pay=1571200, late_out_deduction=0, base_pay=1571200,
        weekly_holiday_pay=314240, meal_allowance=160000, leave_compensation=0,
        total_payment=total_payment,
    )


def test_load_previous_payroll_reads_by_fixed_columns():
    fd, path = tempfile.mkstemp(suffix=".xlsx")
    os.close(fd)
    try:
        wb = openpyxl.Workbook()
        wb.remove(wb.active)
        result = _make_result("김철수", "900101-1234567", 2045440)
        build_wage_sheet(wb, [result])
        wb.save(path)

        previous = load_previous_payroll(path)
        assert "900101-1234567" in previous, previous.keys()
        entry = previous["900101-1234567"]
        assert entry["name"] == "김철수", entry
        assert entry["total_payment"] == 2045440, entry
        assert entry["contract_start"] == date(2026, 6, 1), entry
        assert entry["contract_end"] == date(2026, 6, 30), entry
        assert entry["bank"] == "하나은행", entry
        assert entry["account"] == "1234567890", entry
        print("OK: test_load_previous_payroll_reads_by_fixed_columns")
    finally:
        os.remove(path)


if __name__ == "__main__":
    test_load_previous_payroll_reads_by_fixed_columns()
    print("ALL OK")
