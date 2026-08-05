"""4장: 설정(Config) 관리 화면. 조사종류 / 공통입력값 / 공휴일 3개 탭."""
import tkinter as tk
from tkinter import messagebox, ttk


class SettingsDialog(tk.Toplevel):
    def __init__(self, master, config, on_close=None):
        super().__init__(master)
        self.title("설정")
        self.geometry("560x480")
        self.config_obj = config
        self.on_close = on_close
        self.protocol("WM_DELETE_WINDOW", self._close)

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        self.survey_tab = ttk.Frame(nb)
        self.common_tab = ttk.Frame(nb)
        self.holiday_tab = ttk.Frame(nb)
        nb.add(self.survey_tab, text="조사종류 관리")
        nb.add(self.common_tab, text="공통 입력값")
        nb.add(self.holiday_tab, text="공휴일 관리")

        self._build_survey_tab()
        self._build_common_tab()
        self._build_holiday_tab()

        ttk.Button(self, text="닫기", command=self._close).pack(pady=(0, 8))

    def _close(self):
        self.config_obj.save()
        if self.on_close:
            self.on_close()
        self.destroy()

    # ---------------- 조사종류 관리 ----------------
    def _build_survey_tab(self):
        frame = self.survey_tab
        self.survey_list = ttk.Treeview(frame, columns=("name", "start", "end"), show="headings", height=10)
        for c, label in [("name", "조사이름"), ("start", "시작일"), ("end", "종료일")]:
            self.survey_list.heading(c, text=label)
            self.survey_list.column(c, width=150)
        self.survey_list.pack(fill="both", expand=True, padx=8, pady=8)
        self._reload_surveys()

        form = ttk.Frame(frame)
        form.pack(fill="x", padx=8)
        ttk.Label(form, text="조사이름").grid(row=0, column=0)
        ttk.Label(form, text="시작일(YYYY-MM-DD)").grid(row=0, column=1)
        ttk.Label(form, text="종료일(YYYY-MM-DD)").grid(row=0, column=2)
        self.survey_name_var = tk.StringVar()
        self.survey_start_var = tk.StringVar()
        self.survey_end_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.survey_name_var, width=18).grid(row=1, column=0, padx=2)
        ttk.Entry(form, textvariable=self.survey_start_var, width=14).grid(row=1, column=1, padx=2)
        ttk.Entry(form, textvariable=self.survey_end_var, width=14).grid(row=1, column=2, padx=2)

        btns = ttk.Frame(frame)
        btns.pack(fill="x", padx=8, pady=6)
        ttk.Button(btns, text="추가/수정", command=self._add_or_update_survey).pack(side="left")
        ttk.Button(btns, text="선택 삭제", command=self._delete_survey).pack(side="left", padx=6)
        self.survey_list.bind("<<TreeviewSelect>>", self._on_survey_select)

    def _reload_surveys(self):
        for i in self.survey_list.get_children():
            self.survey_list.delete(i)
        for s in self.config_obj.surveys:
            self.survey_list.insert("", "end", values=(s["name"], s["start"], s["end"]))

    def _on_survey_select(self, _evt=None):
        sel = self.survey_list.selection()
        if not sel:
            return
        name, start, end = self.survey_list.item(sel[0], "values")
        self.survey_name_var.set(name)
        self.survey_start_var.set(start)
        self.survey_end_var.set(end)

    def _add_or_update_survey(self):
        name = self.survey_name_var.get().strip()
        start = self.survey_start_var.get().strip()
        end = self.survey_end_var.get().strip()
        if not name or not start or not end:
            messagebox.showwarning("입력 필요", "조사이름/시작일/종료일을 모두 입력하세요.")
            return
        try:
            self.config_obj.add_or_update_survey(name, start, end)
        except ValueError:
            messagebox.showerror("형식 오류", "날짜는 YYYY-MM-DD 형식으로 입력하세요.")
            return
        self._reload_surveys()

    def _delete_survey(self):
        sel = self.survey_list.selection()
        if not sel:
            return
        name = self.survey_list.item(sel[0], "values")[0]
        self.config_obj.delete_survey(name)
        self._reload_surveys()

    # ---------------- 공통 입력값 ----------------
    def _build_common_tab(self):
        frame = self.common_tab
        ttk.Label(frame, text="시급환산 (원)").grid(row=0, column=0, sticky="w", padx=8, pady=8)
        self.hourly_var = tk.StringVar(value=str(self.config_obj.hourly_wage))
        ttk.Entry(frame, textvariable=self.hourly_var, width=15).grid(row=0, column=1, padx=8)

        ttk.Label(frame, text="월 식대 (원)").grid(row=1, column=0, sticky="w", padx=8, pady=8)
        self.meal_var = tk.StringVar(value=str(self.config_obj.meal_allowance))
        ttk.Entry(frame, textvariable=self.meal_var, width=15).grid(row=1, column=1, padx=8)

        ttk.Button(frame, text="저장", command=self._save_common).grid(row=2, column=0, columnspan=2, pady=12)

    def _save_common(self):
        try:
            self.config_obj.hourly_wage = int(self.hourly_var.get())
            self.config_obj.meal_allowance = int(self.meal_var.get())
        except ValueError:
            messagebox.showerror("형식 오류", "숫자만 입력하세요.")
            return
        self.config_obj.save()
        messagebox.showinfo("저장 완료", "공통 입력값이 저장되었습니다.")

    # ---------------- 공휴일 관리 ----------------
    def _build_holiday_tab(self):
        frame = self.holiday_tab
        self.holiday_list = tk.Listbox(frame, height=14)
        self.holiday_list.pack(fill="both", expand=True, padx=8, pady=8)
        self._reload_holidays()

        form = ttk.Frame(frame)
        form.pack(fill="x", padx=8, pady=6)
        self.holiday_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.holiday_var, width=16).pack(side="left")
        ttk.Label(form, text="예: 2026-01-01", foreground="gray").pack(side="left", padx=(4, 10))
        ttk.Button(form, text="추가", command=self._add_holiday).pack(side="left", padx=6)
        ttk.Button(form, text="선택 삭제", command=self._delete_holiday).pack(side="left")

    def _reload_holidays(self):
        self.holiday_list.delete(0, "end")
        for h in self.config_obj.holidays:
            self.holiday_list.insert("end", h)

    def _add_holiday(self):
        d = self.holiday_var.get().strip()
        if not d:
            return
        try:
            self.config_obj.add_holiday(d)
        except ValueError:
            messagebox.showerror("형식 오류", "날짜는 YYYY-MM-DD 형식으로 입력하세요.")
            return
        self._reload_holidays()

    def _delete_holiday(self):
        sel = self.holiday_list.curselection()
        if not sel:
            return
        d = self.holiday_list.get(sel[0])
        self.config_obj.remove_holiday(d)
        self._reload_holidays()
