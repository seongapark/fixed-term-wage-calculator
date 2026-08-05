import tkinter as tk
from tkinter import messagebox, ttk

from core.config import Config
from core.parser import build_target_people, load_employees, load_giganje_rows
from core.payroll import calc_payroll
from gui.confirm_dialog import ConfirmRunDialog
from gui.evidence_screen import EvidenceScreen
from gui.result_screen import ResultScreen
from gui.settings_dialog import SettingsDialog
from gui.special_leave_screen import SpecialLeaveScreen, collect_pending_groups
from gui.target_screen import TargetScreen
from gui.upload_screen import UploadScreen


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("통계조사관 임금계산 v3.0")
        self.geometry("820x600")

        self.config_obj = Config.load()
        self.employees = {}
        self.giganje_rows = []
        self.people = {}
        self.missing_names = []
        self.ambiguous_names = []
        self.work_year = None
        self.work_month = None
        self.results = []

        self._build_menu()
        self.container = ttk.Frame(self)
        self.container.pack(fill="both", expand=True)
        self.current_screen = None

        self.show_upload_screen()
        self.after(100, self._show_settings_reminder)

    # 주의: tkinter의 Tk.config()/configure()와 이름이 겹치면 안 되므로
    # 설정 객체는 self.config_obj로만 접근한다(속성명 config는 예약됨).
    def _build_menu(self):
        menubar = tk.Menu(self)
        menu = tk.Menu(menubar, tearoff=0)
        menu.add_command(label="설정", command=self.open_settings)
        menubar.add_cascade(label="메뉴", menu=menu)
        self.configure(menu=menubar)

    def _show_settings_reminder(self):
        self.open_settings()

    def open_settings(self):
        SettingsDialog(self, self.config_obj)

    def _set_screen(self, screen):
        if self.current_screen is not None:
            self.current_screen.destroy()
        self.current_screen = screen
        screen.pack(fill="both", expand=True)

    def show_upload_screen(self):
        self._set_screen(UploadScreen(self.container, self))

    def load_files(self, a_path, b_path):
        self.employees = load_employees(a_path)
        self.giganje_rows = load_giganje_rows(b_path)
        self.people, self.missing_names, self.ambiguous_names = build_target_people(
            self.giganje_rows, self.employees
        )

    def after_upload(self):
        if collect_pending_groups(self.people):
            self.show_special_leave_screen()
        else:
            self.show_target_screen()

    def show_special_leave_screen(self):
        self._set_screen(SpecialLeaveScreen(self.container, self))

    def show_target_screen(self):
        if self.missing_names:
            messagebox.showerror(
                "대상자 확인 필요",
                "B파일(근무상황)의 기간제 대상자 중 A파일(개인정보)에 없는 성명이 있습니다:\n"
                + ", ".join(self.missing_names)
                + "\n\nA파일을 보완한 뒤 다시 업로드해야 임금 산정을 진행할 수 있습니다.",
            )
        if self.ambiguous_names:
            messagebox.showerror(
                "동명이인 구분 필요",
                "근무상황(B)에 같은 성명·다른 생년월일을 가진 동명이인이 있는데, "
                "개인정보(A)만으로는 누가 누군지 구분할 수 없습니다:\n"
                + ", ".join(self.ambiguous_names)
                + "\n\nA파일에 '생년월일' 컬럼을 추가하고 각 동명이인의 생년월일을 "
                  "정확히 입력한 뒤 다시 업로드해야 임금 산정을 진행할 수 있습니다.",
            )
        self._set_screen(TargetScreen(self.container, self))

    def reset(self):
        self.employees = {}
        self.giganje_rows = []
        self.people = {}
        self.missing_names = []
        self.ambiguous_names = []
        self.work_year = None
        self.work_month = None
        self.results = []
        self.show_upload_screen()

    def open_confirm_dialog(self):
        ConfirmRunDialog(self, self)

    def run_calculation(self):
        targets = [p for p in self.people.values() if p.survey_name and p.contract_start and p.contract_end]
        results = []
        errors = []
        for person in targets:
            try:
                results.append(calc_payroll(person, self.config_obj, self.work_year, self.work_month))
            except Exception as e:
                errors.append(f"{person.name}: {e}")
        if errors:
            messagebox.showwarning("일부 대상자 계산 오류", "\n".join(errors))
        self.results = results
        self.show_result_screen()

    def show_result_screen(self):
        self._set_screen(ResultScreen(self.container, self))

    def show_evidence_screen(self, selected_key=None):
        screen = EvidenceScreen(self.container, self)
        self._set_screen(screen)
        screen.refresh(selected_key=selected_key)


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
