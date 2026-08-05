import openpyxl

from .wage_sheet import build_wage_sheet
from .raw_sheet import build_raw_status_sheet
from .evidence_sheet import build_evidence_sheet
from .departed_sheet import build_departed_sheet, build_departed_evidence_sheet


def output_filename(year: int, month: int) -> str:
    yy = year % 100
    return f"'{yy}년 {month}월 고용노동통계조사관 임금 내역.xlsx"


def departed_output_filename(year: int, month: int) -> str:
    yy = year % 100
    return f"'{yy}년 {month}월 소급대상자 내역.xlsx"


def build_workbook(results, config, giganje_rows=None, retro_adjustments=None):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    build_wage_sheet(wb, results, retro_adjustments=retro_adjustments)
    build_evidence_sheet(wb, results, config, retro_adjustments=retro_adjustments)
    if giganje_rows is not None:
        build_raw_status_sheet(wb, giganje_rows)
    return wb


def build_departed_workbook(departed_results):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    build_departed_sheet(wb, departed_results)
    build_departed_evidence_sheet(wb, departed_results)
    return wb
