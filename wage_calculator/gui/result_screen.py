"""6장-4: 결과 화면."""
from pathlib import Path
from tkinter import messagebox, ttk

from core.parser import display_label, person_key
from core.paths import downloads_dir
from output.build import build_workbook, output_filename


class ResultScreen(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app

        ttk.Label(self, text="계산 결과", font=("", 14, "bold")).pack(pady=(16, 8))

        columns = ("name", "survey", "period", "total_days", "weekly", "remain_leave", "total_pay")
        headers = {
            "name": "성명", "survey": "조사", "period": "급여계산기간",
            "total_days": "계(일)", "weekly": "주휴(일)", "remain_leave": "잔여연가(일)",
            "total_pay": "지급총액",
        }
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=16)
        for c in columns:
            self.tree.heading(c, text=headers[c])
            self.tree.column(c, width=110, anchor="center")
        self.tree.pack(fill="both", expand=True, padx=10, pady=6)
        self.tree.bind("<Double-1>", self._open_evidence)

        bottom = ttk.Frame(self)
        bottom.pack(fill="x", padx=10, pady=10)
        ttk.Button(bottom, text="엑셀 다운로드", command=self._download).pack(side="left")
        ttk.Button(bottom, text="산정근거 확인", command=self.app.show_evidence_screen).pack(side="left", padx=8)
        ttk.Button(bottom, text="새로 계산(처음부터)", command=self.app.confirm_and_reset).pack(side="right")
        ttk.Button(bottom, text="뒤로가기", command=self._back).pack(side="right", padx=8)

        self.refresh()

    def refresh(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        all_names = [r.name for r in self.app.results]
        for r in self.app.results:
            label = display_label(r.name, r.birth, all_names)
            self.tree.insert("", "end", iid=person_key(r.name, r.birth), values=(
                label, r.survey_name, f"{r.period_start}~{r.period_end}",
                r.total_days, r.weekly_holiday_days, round(r.remaining_leave_days, 2),
                f"{r.total_payment:,}",
            ))

    def _open_evidence(self, _evt=None):
        sel = self.tree.selection()
        if sel:
            self.app.show_evidence_screen(selected_key=sel[0])

    def _download(self):
        wb = build_workbook(self.app.results, self.app.giganje_rows)
        filename = output_filename(self.app.work_year, self.app.work_month)
        path = Path(downloads_dir()) / filename
        wb.save(path)
        messagebox.showinfo("저장 완료", f"저장되었습니다:\n{path}")

    def _back(self):
        self.app.show_target_screen()
