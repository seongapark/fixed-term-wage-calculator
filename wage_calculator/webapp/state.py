"""tkinter GUI(gui/app.py)의 orchestration 로직을 이관한 상태 객체.

원본 App(tk.Tk)이 들고 있던 데이터와 메서드를 그대로 옮긴다 - 검증 규칙과
계산 흐름은 원본과 동일하게 유지하고, tkinter 위젯을 그리던 부분만 값을
반환하도록 바뀐다.
"""
from core import date_utils
from core.config import Config
from core.parser import (
    build_target_people,
    load_employees,
    load_giganje_rows,
    load_previous_payroll,
)


def collect_pending_groups(people):
    """people(dict[key, TargetPerson]) 전체에서 classified == "특별휴가_미정"인
    이벤트를 (person_key, source_range)로 묶어 그룹 목록을 만든다.

    반환: [{"person_key", "person_name", "start", "end", "events", "status"}, ...]
    status는 None(미정) / "유급특별휴가" / "무급특별휴가".
    """
    groups = {}
    order = []
    for key, person in people.items():
        for e in person.events:
            if e.classified != "특별휴가_미정":
                continue
            gkey = (key, e.source_range)
            if gkey not in groups:
                groups[gkey] = {
                    "person_key": key,
                    "person_name": person.name,
                    "start": e.source_range[0],
                    "end": e.source_range[1],
                    "events": [],
                    "status": None,
                }
                order.append(gkey)
            groups[gkey]["events"].append(e)
    return [groups[k] for k in order]


def _find_reason_note(giganje_rows, person_name, start, end):
    """원본 B파일 행에서 이 그룹과 같은 성명·기간의 사유/비고를 찾아 힌트로 보여준다
    (자동 판정에는 쓰지 않음 - 지역마다 기재 여부가 달라 참고용일 뿐)."""
    for row in giganje_rows:
        if str(row.get("성명") or "").strip() != person_name:
            continue
        if str(row.get("종별") or "").strip() != "특별휴가":
            continue
        date_field = row.get("사용기간(날짜)")
        if date_field is None:
            continue
        try:
            row_start, row_end = date_utils.parse_date_range(date_field)
        except (ValueError, TypeError):
            continue
        if row_start == start and row_end == end:
            return str(row.get("사유") or ""), str(row.get("비고") or "")
    return "", ""


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

    def load_files(self, a_path, b_path, prev_payroll_path=None):
        self.employees = load_employees(a_path)
        self.giganje_rows = load_giganje_rows(b_path)
        self.people, self.missing_names, self.ambiguous_names = build_target_people(
            self.giganje_rows, self.employees
        )
        self.previous_payroll = load_previous_payroll(prev_payroll_path) if prev_payroll_path else {}
        self.pending_leave_groups = collect_pending_groups(self.people)
        return {
            "ambiguous_names": list(self.ambiguous_names),
            "has_pending_special_leave": bool(self.pending_leave_groups),
        }

    def special_leave_groups(self):
        out = []
        for idx, g in enumerate(self.pending_leave_groups):
            reason, note = _find_reason_note(self.giganje_rows, g["person_name"], g["start"], g["end"])
            out.append({
                "index": idx,
                "person_name": g["person_name"],
                "start": g["start"].isoformat(),
                "end": g["end"].isoformat(),
                "reason": reason,
                "note": note,
                "status": g["status"],
            })
        return out

    def confirm_special_leave(self, statuses):
        if len(statuses) != len(self.pending_leave_groups):
            raise ValueError("특별휴가 상태 값 개수가 대기 중인 건수와 맞지 않습니다.")
        if any(not s for s in statuses):
            raise ValueError("모든 건에 유급/무급을 지정해야 진행할 수 있습니다.")
        for g, status in zip(self.pending_leave_groups, statuses):
            g["status"] = status
            for e in g["events"]:
                e.classified = status
