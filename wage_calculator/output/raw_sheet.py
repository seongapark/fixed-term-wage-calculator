"""B파일(근무상황) 중 직급에 '기간제'가 포함된 행만 원본 형식 그대로 옮긴 시트."""
from openpyxl.styles import Font

SHEET_NAME = "근무상황(기간제)"

COLUMNS = ["소속", "직급", "성명", "생년월일", "종별", "사용기간(날짜)", "사용시간(시분)", "사유", "연락처", "결재상태", "비고"]


def build_raw_status_sheet(wb, giganje_rows):
    ws = wb.create_sheet(SHEET_NAME)
    for c, header in enumerate(COLUMNS, start=1):
        cell = ws.cell(row=1, column=c, value=header)
        cell.font = Font(bold=True)

    for r, row in enumerate(giganje_rows, start=2):
        for c, header in enumerate(COLUMNS, start=1):
            ws.cell(row=r, column=c, value=row.get(header))

    for c in range(1, len(COLUMNS) + 1):
        ws.column_dimensions[ws.cell(row=1, column=c).column_letter].width = 16

    return ws
