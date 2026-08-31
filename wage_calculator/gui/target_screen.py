"""6장-2: 대상자 확인 화면."""
import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk

from core import coverage
from core.parser import display_label
from .tree_utils import autosize_columns


class ContractEditDialog(tk.Toplevel):
    def __init__(self, master, person, on_save):
        super().__init__(master)
        self.title(f"계약기간 수정 - {person.name}")
        self.person = person
        self.on_save = on_save
        self.geometry("320x150")

        ttk.Label(self, text="계약 시작일(YYYY-MM-DD)").pack(pady=(12, 2))
        self.start_var = tk.StringVar(value=person.contract_start.isoformat() if person.contract_start else "")
        ttk.Entry(self, textvariable=self.start_var).pack()

        ttk.Label(self, text="계약 마지막일(YYYY-MM-DD)").pack(pady=(12, 2))
        self.end_var = tk.StringVar(value=person.contract_end.isoformat() if person.contract_end else "")
        ttk.Entry(self, textvariable=self.end_var).pack()

        ttk.Button(self, text="저장", command=self._save).pack(pady=12)

    def _save(self):
        try:
            start = date.fromisoformat(self.start_var.get().strip())
            end = date.fromisoformat(self.end_var.get().strip())
        except ValueError:
            messagebox.showerror("형식 오류", "날짜는 YYYY-MM-DD 형식으로 입력하세요.")
            return
        self.person.contract_start = start
        self.person.contract_end = end
        self.person.contract_overridden = True
        self.on_save()
        self.destroy()


class TargetScreen(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.checked = set()

        top = ttk.Frame(self)
        top.pack(fill="x", padx=10, pady=8)
        ttk.Label(top, text="급여산정 연도").pack(side="left")
        self.year_var = tk.StringVar(value=str(date.today().year))
        ttk.Entry(top, textvariable=self.year_var, width=6).pack(side="left", padx=(2, 12))
        ttk.Label(top, text="급여산정 월").pack(side="left")
        self.month_var = tk.StringVar(value=str(date.today().month))
        ttk.Entry(top, textvariable=self.month_var, width=4).pack(side="left", padx=(2, 12))


        self.columns = ("check", "name", "survey", "start", "end")
        self.tree = ttk.Treeview(self, columns=self.columns, show="headings", height=14)
        self.headers = {"check": "선택", "name": "성명", "survey": "담당조사", "start": "계약시작", "end": "계약마지막"}
        for c in self.columns:
            self.tree.heading(c, text=self.headers[c])
            self.tree.column(c, width=110 if c != "name" else 90, anchor="center")
        self.tree.pack(fill="both", expand=True, padx=10, pady=6)
        self.tree.bind("<Button-1>", self._on_click)
        self.tree.bind("<Double-1>", self._on_double_click)

        select_bar = ttk.Frame(self)
        select_bar.pack(fill="x", padx=10)
        ttk.Button(select_bar, text="전체선택", command=self._select_all).pack(side="left")
        ttk.Button(select_bar, text="전체해제", command=self._deselect_all).pack(side="left", padx=6)

        batch = ttk.Frame(self)
        batch.pack(fill="x", padx=10, pady=6)
        ttk.Label(batch, text="담당조사 일괄 지정:").pack(side="left")
        self.survey_var = tk.StringVar()
        self.survey_combo = ttk.Combobox(batch, textvariable=self.survey_var, state="readonly", width=25)
        self.survey_combo.pack(side="left", padx=6)
        ttk.Button(batch, text="선택 인원에 일괄 매칭", command=self._batch_assign).pack(side="left")
        ttk.Label(batch, text="(행 더블클릭: 계약기간 개별 수정)").pack(side="left", padx=12)

        bottom = ttk.Frame(self)
        bottom.pack(fill="x", padx=10, pady=10)
        ttk.Button(bottom, text="계산 실행", command=self._proceed).pack(side="right")

        self.refresh()

    def refresh(self):
        self.survey_combo["values"] = self.app.config_obj.survey_names()
        for i in self.tree.get_children():
            self.tree.delete(i)
        all_names = [p.name for p in self.app.people.values()]
        for key, person in self.app.people.items():
            mark = "☑" if key in self.checked else "☐"
            label = display_label(person.name, person.birth, all_names)
            self.tree.insert("", "end", iid=key, values=(
                mark, label, person.survey_name or "",
                person.contract_start.isoformat() if person.contract_start else "",
                person.contract_end.isoformat() if person.contract_end else "",
            ))
        autosize_columns(self.tree, self.columns, self.headers)

    def _select_all(self):
        self.checked = set(self.app.people.keys())
        self.refresh()

    def _deselect_all(self):
        self.checked.clear()
        self.refresh()

    def _on_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region != "cell":
            return
        col = self.tree.identify_column(event.x)
        row = self.tree.identify_row(event.y)
        if not row or col != "#1":
            return
        if row in self.checked:
            self.checked.remove(row)
        else:
            self.checked.add(row)
        self.refresh()

    def _on_double_click(self, event):
        row = self.tree.identify_row(event.y)
        if not row:
            return
        person = self.app.people[row]
        ContractEditDialog(self, person, self.refresh)

    def _batch_assign(self):
        survey_name = self.survey_var.get()
        if not survey_name:
            messagebox.showwarning("선택 필요", "담당조사를 선택하세요.")
            return
        if not self.checked:
            messagebox.showwarning("선택 필요", "일괄 매칭할 인원을 체크하세요.")
            return
        survey = self.app.config_obj.get_survey(survey_name)
        start = date.fromisoformat(survey["start"])
        end = date.fromisoformat(survey["end"])
        for name in self.checked:
            person = self.app.people[name]
            person.survey_name = survey_name
            person.contract_start = start
            person.contract_end = end
            person.contract_overridden = False
        self.checked.clear()
        self.refresh()

    def _proceed(self):
        if self.app.ambiguous_names:
            messagebox.showerror(
                "진행 불가",
                "동명이인을 구분할 수 없는 대상자가 있어 계산을 진행할 수 없습니다:\n"
                + ", ".join(self.app.ambiguous_names),
            )
            return
        try:
            year = int(self.year_var.get())
            month = int(self.month_var.get())
            if not (1 <= month <= 12):
                raise ValueError
        except ValueError:
            messagebox.showerror("입력 오류", "급여산정 연/월을 올바르게 입력하세요.")
            return

        # 연가·주휴는 계약 시작일부터 누적 판정하므로, 계약 시작월부터 계산월까지
        # 근무상황이 전부 있어야 한다. 빠진 달이 있으면 그 달이 '만근'으로 잘못
        # 처리되므로 계산 자체를 막는다.
        gaps = coverage.find_coverage_gaps(self.app.people, self.app.giganje_rows, year, month)
        if gaps:
            messagebox.showerror(
                "근무상황 기간 부족",
                coverage.format_gap_message(gaps, self.app.giganje_rows, year, month),
            )
            return

        unassigned = [p.name for p in self.app.people.values() if not p.survey_name]
        if unassigned:
            proceed = messagebox.askyesno(
                "담당조사 미지정 인원 있음",
                f"담당조사가 지정되지 않은 인원은 이번 계산에서 제외됩니다: {', '.join(unassigned)}\n계속하시겠습니까?",
            )
            if not proceed:
                return

        self.app.work_year = year
        self.app.work_month = month
        self.app.open_contract_period_check_dialog()
