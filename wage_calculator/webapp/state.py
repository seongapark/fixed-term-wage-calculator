"""tkinter GUI(gui/app.py)의 orchestration 로직을 이관한 상태 객체.

원본 App(tk.Tk)이 들고 있던 데이터와 메서드를 그대로 옮긴다 - 검증 규칙과
계산 흐름은 원본과 동일하게 유지하고, tkinter 위젯을 그리던 부분만 값을
반환하도록 바뀐다.
"""
from core.config import Config


class AppState:
    def __init__(self):
        self.config_obj = Config.load()
        self._reset_data()

    def _reset_data(self):
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
        self.retro_details = {}
        self.departed_results = []
        self.pending_leave_groups = []

    def reset(self):
        self._reset_data()
