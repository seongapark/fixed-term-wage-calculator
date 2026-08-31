"""유급/무급 미확정 근무상황 마킹 화면.

두 종류가 여기로 온다.
  - 특별휴가_미정: 경조사·출산·돌봄·포상 등 종별만으로 유급/무급이 정해지지
    않는 휴가(원본이 "특별휴가"로만 뭉뚱그려 나오는 경우 포함).
  - 같은 분류로, 청·지청 표기가 달라 규칙에 걸리지 않은 처음 보는 종별.

파일 업로드 직후 사람이 건별(원본 행 단위)로 유급/무급을 선택하게 한다.
판단 근거가 되도록 원본 종별 문자열을 그대로 표에 보여준다.
선택이 끝나야 대상자 확인 화면으로 진행할 수 있다.
"""
from tkinter import messagebox, ttk

from core import date_utils, mapping
from .tree_utils import autosize_columns


def collect_pending_groups(people):
    """people(dict[key, TargetPerson]) 전체에서 classified가 확인 대기("특별휴가_미정")인
    이벤트를 (person_key, source_range)로 묶어 그룹 목록을 만든다.

    반환: [{"person_key", "person_name", "start", "end", "events", "status"}, ...]
    status는 None(미정) / "유급특별휴가" / "무급특별휴가".
    """
    groups = {}
    order = []
    for key, person in people.items():
        for e in person.events:
            if not mapping.is_pending(e.classified):
                continue
            # 같은 사람·같은 기간이라도 종별이 다르면 별개 건으로 봐야 한다
            # (원본 B파일에서 같은 날짜 범위로 서로 다른 종별이 두 줄 나올 수 있음).
            gkey = (key, e.source_range, e.raw_category)
            if gkey not in groups:
                groups[gkey] = {
                    "person_key": key,
                    "person_name": person.name,
                    "raw_category": e.raw_category,
                    "classified": e.classified,
                    "start": e.source_range[0],
                    "end": e.source_range[1],
                    "events": [],
                    "status": None,
                }
                order.append(gkey)
            groups[gkey]["events"].append(e)
    return [groups[k] for k in order]


def _find_reason_note(giganje_rows, person_name, start, end, raw_category=None):
    """원본 B파일 행에서 이 그룹과 같은 성명·종별·기간의 사유/비고를 찾아 힌트로
    보여준다(자동 판정에는 쓰지 않음 - 지역마다 기재 여부가 달라 참고용일 뿐).

    종별은 "특별휴가" 고정이 아니다. 경조사·포상 등 유급/무급 미확정 휴가와
    규칙에 걸리지 않은 처음 보는 종별도 이 화면에 오므로, 그룹의 원본 종별
    문자열로 대조한다(raw_category 미지정이면 확인 대상 분류 전체를 허용).
    """
    for row in giganje_rows:
        if str(row.get("성명") or "").strip() != person_name:
            continue
        row_category = str(row.get("종별") or "").strip()
        if raw_category is not None:
            if row_category != raw_category:
                continue
        elif not mapping.is_pending(mapping.classify(row_category)):
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
            self, text="유급/무급 확인",
            font=("", 14, "bold"),
        ).pack(pady=(16, 4))
        ttk.Label(
            self,
            text="종별만으로는 유급/무급을 정할 수 없는 건입니다(경조사·출산·돌봄·포상 등\n"
                 "특별휴가, 그리고 청·지청 표기가 달라 프로그램이 알아보지 못한 종별).\n"
                 "\"종별(원본)\" 칸에 근무상황 파일에 적힌 문자열을 그대로 보여주니 이를 보고 판단하세요.\n"
                 "행을 클릭하면 미정 → 유급 → 무급 순으로 바뀝니다. 모두 지정해야 다음으로 진행됩니다.",
            foreground="gray", justify="left",
        ).pack(pady=(0, 8))

        self.columns = ("name", "category", "period", "reason", "note", "status")
        self.headers = {"name": "성명", "category": "종별(원본)", "period": "기간",
                        "reason": "사유(원본)", "note": "비고(원본)", "status": "유급/무급"}
        self.tree = ttk.Treeview(self, columns=self.columns, show="headings", height=14)
        for c in self.columns:
            self.tree.heading(c, text=self.headers[c])
            self.tree.column(c, width=140 if c in ("category", "reason", "note") else 100, anchor="center")
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
            reason, note = _find_reason_note(
                self.app.giganje_rows, g["person_name"], g["start"], g["end"], g["raw_category"],
            )
            self.tree.insert("", "end", iid=str(idx), values=(
                g["person_name"], g["raw_category"], period, reason, note, STATUS_LABEL[g["status"]],
            ))
        autosize_columns(self.tree, self.columns, self.headers)
        all_decided = all(g["status"] is not None for g in self.groups)
        self.next_btn.config(state="normal" if all_decided else "disabled")

    def _on_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region != "cell":
            return
        column = self.tree.identify_column(event.x)
        if column != "#6":  # "유급/무급" 상태 컬럼(마지막)에서 클릭했을 때만 토글
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
