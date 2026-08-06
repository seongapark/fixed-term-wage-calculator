import tkinter as tk
from tkinter import messagebox, ttk

from core import date_utils
from core.config import Config
from core.parser import build_target_people, load_employees, load_giganje_rows, load_previous_payroll
from core.payroll import calc_payroll
from core.retroactive import compute_retroactive
from gui.confirm_dialog import ConfirmRunDialog, ContractPeriodCheckDialog
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
        self.previous_payroll = {}
        self.retro_adjustments = {}
        self.departed_results = []

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
        menu.add_command(label="새 파일로 시작", command=self.confirm_and_reset)
        menubar.add_cascade(label="메뉴", menu=menu)
        self.configure(menu=menubar)

    def confirm_and_reset(self):
        if messagebox.askyesno(
            "새로 계산",
            "처음(파일 업로드)부터 다시 시작하시겠습니까? 현재 업로드된 파일과 계산 결과는 모두 사라집니다.",
        ):
            self.reset()

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

    def load_files(self, a_path, b_path, prev_payroll_path=None):
        self.employees = load_employees(a_path)
        self.giganje_rows = load_giganje_rows(b_path)
        self.people, self.missing_names, self.ambiguous_names = build_target_people(
            self.giganje_rows, self.employees
        )
        self.previous_payroll = load_previous_payroll(prev_payroll_path) if prev_payroll_path else {}

    def after_upload(self):
        # A파일 데이터 문제(동명이인)는 업로드 직후 바로 알려야 한다.
        # 특별휴가 마킹 화면으로 먼저 라우팅되면, 사용자가 건별 유급/무급을
        # 전부 클릭한 뒤에야 "A파일 다시 올리세요"를 보게 되는 낭비가 생기므로
        # 이 체크는 특별휴가 라우팅 분기보다 먼저 실행한다.
        #
        # missing_names(B파일에는 있는데 A파일에 없는 성명)는 더 이상 경고하지
        # 않는다 - B파일에 직급 무관 전 직원이 섞여 나올 수 있어(직급 필터
        # 제거, parser.py 참고) A파일에 없는 사람은 애초에 급여 대상이 아니라는
        # 뜻이므로, 그냥 A파일 대상자만 정상적으로 급여 계산하면 된다.
        if self.ambiguous_names:
            messagebox.showerror(
                "동명이인 구분 필요",
                "근무상황(B)에 같은 성명·다른 생년월일을 가진 동명이인이 있는데, "
                "개인정보(A)만으로는 누가 누군지 구분할 수 없습니다:\n"
                + ", ".join(self.ambiguous_names)
                + "\n\nA파일에 '생년월일' 컬럼을 추가하고 각 동명이인의 생년월일을 "
                  "정확히 입력한 뒤 다시 업로드해야 임금 산정을 진행할 수 있습니다.",
            )
        if collect_pending_groups(self.people):
            self.show_special_leave_screen()
        else:
            self.show_target_screen()

    def show_special_leave_screen(self):
        self._set_screen(SpecialLeaveScreen(self.container, self))

    def show_target_screen(self):
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
        self.previous_payroll = {}
        self.retro_adjustments = {}
        self.departed_results = []
        self.show_upload_screen()

    def open_contract_period_check_dialog(self):
        ContractPeriodCheckDialog(self, self)

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
        self.results = results

        self.retro_adjustments = {}
        self.departed_results = []
        if self.previous_payroll:
            prev_year, prev_month = date_utils.previous_month(self.work_year, self.work_month)
            try:
                self.retro_adjustments, self.departed_results = compute_retroactive(
                    self.people, self.previous_payroll, self.giganje_rows,
                    self.config_obj, prev_year, prev_month,
                )
            except Exception as e:
                errors.append(f"소급계산 오류: {e}")

        if errors:
            messagebox.showwarning("일부 대상자 계산 오류", "\n".join(errors))
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
