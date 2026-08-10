"""특별휴가(유급/무급) 마킹 화면.

원본 B파일 종별이 "특별휴가"로만 기록되어 유급/무급을 구분할 수 없는 건을
파일 업로드 직후 화면에서 사람이 직접 건별(원본 행 단위)로 선택하게 한다.
선택이 끝나야 대상자 확인 화면으로 진행할 수 있다.
"""
from tkinter import messagebox, ttk

from core import date_utils
from .tree_utils import autosize_columns


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


STATUS_LABEL = {None: "미정", "유급특별휴가": "유급", "무급특별휴가": "무급"}
NEXT_STATUS = {None: "유급특별휴가", "유급특별휴가": "무급특별휴가", "무급특별휴가": "유급특별휴가"}


class SpecialLeaveScreen(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.groups = collect_pending_groups(app.people)

        ttk.Label(
            self, text="특별휴가 유급/무급 확인",
            font=("", 14, "bold"),
        ).pack(pady=(16, 4))
        ttk.Label(
            self,
            text="근무상황 파일에 \"특별휴가\"로만 기록되어 유급/무급을 알 수 없는 건입니다.\n"
                 "행을 클릭하면 미정 → 유급 → 무급 순으로 바뀝니다. 모두 지정해야 다음으로 진행됩니다.",
            foreground="gray", justify="left",
        ).pack(pady=(0, 8))

        self.columns = ("name", "period", "reason", "note", "status")
        self.headers = {"name": "성명", "period": "기간", "reason": "사유(원본)", "note": "비고(원본)", "status": "유급/무급"}
        self.tree = ttk.Treeview(self, columns=self.columns, show="headings", height=14)
        for c in self.columns:
            self.tree.heading(c, text=self.headers[c])
            self.tree.column(c, width=140 if c in ("reason", "note") else 100, anchor="center")
        self.tree.pack(fill="both", expand=True, padx=10, pady=6)
        self.tree.bind("<Button-1>", self._on_click)

        bottom = ttk.Frame(self)
        bottom.pack(fill="x", padx=10, pady=10)
        self.next_btn = ttk.Button(bottom, text="다음", command=self._proceed)
        self.next_btn.pack(side="right")

        self._refresh()

    def _refresh(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        for idx, g in enumerate(self.groups):
            period = f"{g['start']}" if g["start"] == g["end"] else f"{g['start']}~{g['end']}"
            reason, note = _find_reason_note(self.app.giganje_rows, g["person_name"], g["start"], g["end"])
            self.tree.insert("", "end", iid=str(idx), values=(
                g["person_name"], period, reason, note, STATUS_LABEL[g["status"]],
            ))
        autosize_columns(self.tree, self.columns, self.headers)
        all_decided = all(g["status"] is not None for g in self.groups)
        self.next_btn.config(state="normal" if all_decided else "disabled")

    def _on_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region != "cell":
            return
        column = self.tree.identify_column(event.x)
        if column != "#5":  # "유급/무급" 상태 컬럼(5번째)에서 클릭했을 때만 토글
            return
        row = self.tree.identify_row(event.y)
        if not row:
            return
        idx = int(row)
        self.groups[idx]["status"] = NEXT_STATUS[self.groups[idx]["status"]]
        self._refresh()

    def _proceed(self):
        undecided = [g for g in self.groups if g["status"] is None]
        if undecided:
            messagebox.showwarning("선택 필요", "모든 건에 유급/무급을 지정해야 진행할 수 있습니다.")
            return
        for g in self.groups:
            for e in g["events"]:
                e.classified = g["status"]
        self.app.show_target_screen()
