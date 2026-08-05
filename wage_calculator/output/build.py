import openpyxl

from .wage_sheet import build_wage_sheet
from .raw_sheet import build_raw_status_sheet


def output_filename(year: int, month: int) -> str:
    yy = year % 100
    return f"'{yy}년 {month}월 고용노동통계조사관 임금 내역.xlsx"


def build_workbook(results, giganje_rows=None):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    build_wage_sheet(wb, results)
    if giganje_rows is not None:
        build_raw_status_sheet(wb, giganje_rows)
    return wb
