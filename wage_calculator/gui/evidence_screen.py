"""6장-5: 산정근거 확인 화면 (7장 산정근거 4종 + 원본 근무현황 비교)."""
import tkinter as tk
from tkinter import ttk

from core import date_utils, leave_engine
from core.leave_engine import leave_usage_minutes
from core.parser import display_label, person_key


class EvidenceScreen(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.label_to_key = {}

        top = ttk.Frame(self)
        top.pack(fill="x", padx=10, pady=8)
        ttk.Label(top, text="성명 선택").pack(side="left")
        self.name_var = tk.StringVar()
        self.combo = ttk.Combobox(top, textvariable=self.name_var, state="readonly", width=20)
        self.combo.pack(side="left", padx=6)
        self.combo.bind("<<ComboboxSelected>>", lambda e: self.render())
        ttk.Button(top, text="← 결과 화면", command=self.app.show_result_screen).pack(side="right")

        paned = ttk.PanedWindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=10, pady=6)

        raw_frame = ttk.Frame(paned)
        paned.add(raw_frame, weight=1)
        ttk.Label(raw_frame, text="근무현황 원본(B파일)", font=("", 10, "bold")).pack(anchor="w", pady=(0, 4))
        raw_columns = ["종별", "사용기간(날짜)", "사용시간(시분)", "사유", "비고"]
        self.raw_tree = ttk.Treeview(raw_frame, columns=raw_columns, show="headings", height=20)
        for c in raw_columns:
            self.raw_tree.heading(c, text=c)
            self.raw_tree.column(c, width=100, anchor="center")
        self.raw_tree.pack(fill="both", expand=True)

        evidence_frame = ttk.Frame(paned)
        paned.add(evidence_frame, weight=2)
        nb = ttk.Notebook(evidence_frame)
        nb.pack(fill="both", expand=True)

        self.weekly_tree = self._make_tab(nb, "주휴 산정근거",
            ["창번호", "시작일", "종료일", "근무일수", "결근", "공가", "병가", "판정", "미발생사유"])
        self.lateout_tree = self._make_tab(nb, "조퇴외출 산정근거",
            ["날짜", "종별", "시작", "종료", "점심포함", "공제(분)"])
        self.meal_tree = self._make_tab(nb, "식대해당일 산정근거",
            ["급여계산기간 시작", "급여계산기간 종료", "총일수", "결근일수", "식대해당일"])
        self.leave_tree = self._make_tab(nb, "잔여연가 산정근거",
            ["구간번호", "구간시작", "구간종료", "상태", "발생", "구간내 사용", "누적잔여(분)"])

    def _make_tab(self, nb, title, columns):
        frame = ttk.Frame(nb)
        nb.add(frame, text=title)
        tree = ttk.Treeview(frame, columns=columns, show="headings", height=14)
        for c in columns:
            tree.heading(c, text=c)
            tree.column(c, width=90, anchor="center")
        tree.pack(fill="both", expand=True, padx=6, pady=6)
        return tree

    def refresh(self, selected_key=None):
        all_names = [r.name for r in self.app.results]
        self.label_to_key = {
            display_label(r.name, r.birth, all_names): person_key(r.name, r.birth)
            for r in self.app.results
        }
        labels = list(self.label_to_key.keys())
        self.combo["values"] = labels

        current_key = selected_key or (self.label_to_key.get(self.name_var.get()))
        if current_key:
            match = [lbl for lbl, k in self.label_to_key.items() if k == current_key]
            if match:
                self.name_var.set(match[0])
        elif labels and not self.name_var.get():
            self.name_var.set(labels[0])
        self.render()

    def _result(self):
        key = self.label_to_key.get(self.name_var.get())
        if key is None:
            return None
        for r in self.app.results:
            if person_key(r.name, r.birth) == key:
                return r
        return None

    def render(self):
        for tree in (self.raw_tree, self.weekly_tree, self.lateout_tree, self.meal_tree, self.leave_tree):
            for i in tree.get_children():
                tree.delete(i)

        r = self._result()
        if r is None:
            return

        for row in self.app.giganje_rows:
            if row["성명"] != r.name:
                continue
            if str(row.get("생년월일") or "").strip() != r.birth:
                continue
            self.raw_tree.insert("", "end", values=(
                row.get("종별") or "", row.get("사용기간(날짜)") or "",
                row.get("사용시간(시분)") or "", row.get("사유") or "", row.get("비고") or "",
            ))

        for w in r.weekly_windows:
            self.weekly_tree.insert("", "end", values=(
                w.index, w.start, w.effective_end, w.workdays, w.absence_days,
                w.public_leave_days, w.sick_full_days, "O" if w.granted else "X", w.reason,
            ))

        for e in r.late_out_events:
            lunch = "포함" if (e.time_start < date_utils.LUNCH_START and e.time_end > date_utils.LUNCH_END) else "미포함"
            self.lateout_tree.insert("", "end", values=(
                e.d, e.raw_category, e.time_start.strftime("%H:%M"), e.time_end.strftime("%H:%M"),
                lunch, e.minutes,
            ))
        self.lateout_tree.insert("", "end", values=("", "", "", "", "합계(분)", r.late_out_minutes))

        total_days = (r.period_end - r.period_start).days + 1
        self.meal_tree.insert("", "end", values=(
            r.period_start, r.period_end, total_days, r.absence_days, r.meal_eligible_days,
        ))

        for w in r.monthly_windows:
            if w.start > r.period_end:
                continue
            usage_text = ", ".join(f"{e.d.strftime('%m-%d')}:{leave_usage_minutes(e)}" for e in w.usage_events)
            concluded = w.effective_end <= r.period_end
            status = ("만근" if w.full_attendance else ("기간중 종료" if w.truncated else "미만근")) if concluded else "진행중"
            as_of = min(w.effective_end, r.period_end)
            balance_at_row = leave_engine.leave_balance_minutes_as_of(r.monthly_windows, as_of)
            self.leave_tree.insert("", "end", values=(
                w.index, w.start, w.effective_end, status,
                (1 if w.accrued else 0) if concluded else 0,
                usage_text, balance_at_row,
            ))
        self.leave_tree.insert("", "end", values=(
            "", "", "", "최종", "", f"{round(r.remaining_leave_days,4)}일", round(r.remaining_leave_days * 480),
        ))
