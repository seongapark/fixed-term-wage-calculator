"""6장-3: 계산 실행 전 확인 대화상자."""
import tkinter as tk
from datetime import date
from tkinter import ttk

from core import date_utils


class ConfirmRunDialog(tk.Toplevel):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.title("계산 실행 확인")
        self.geometry("480x360")
        self.grab_set()

        year, month = app.work_year, app.work_month
        month_first = date(year, month, 1)
        month_last = date(year, month, date_utils.month_calendar_days(month_first))
        holidays = app.config_obj.holidays_in_range(month_first.isoformat(), month_last.isoformat())

        text = tk.Text(self, wrap="word", height=16, width=56)
        text.pack(padx=12, pady=12, fill="both", expand=True)

        if holidays:
            text.insert("end", f"[이번 달({year}년 {month}월) 공휴일]\n" + ", ".join(holidays) + "\n\n")
        else:
            text.insert("end", f"[이번 달({year}년 {month}월) 공휴일 없음]\n\n")

        text.insert("end", f"[현재 적용 공통 입력값]\n시급: {app.config_obj.hourly_wage:,}원 / 월 식대: {app.config_obj.meal_allowance:,}원\n\n")

        overridden = [p.name for p in app.people.values() if p.contract_overridden]
        if overridden:
            text.insert("end", f"[계약기간을 개별 수정한 인원]\n{', '.join(overridden)}\n")
        else:
            text.insert("end", "[계약기간을 개별 수정한 인원]\n없음\n")

        text.config(state="disabled")

        btns = ttk.Frame(self)
        btns.pack(pady=8)
        ttk.Button(btns, text="취소", command=self.destroy).pack(side="left", padx=8)
        ttk.Button(btns, text="계속(계산 실행)", command=self._run).pack(side="left", padx=8)

    def _run(self):
        self.destroy()
        self.app.run_calculation()
