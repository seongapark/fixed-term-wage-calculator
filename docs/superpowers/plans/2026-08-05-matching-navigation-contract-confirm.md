# B파일 매칭 단순화 / 비파괴 뒤로가기 / 계약기간 사전확인 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** B파일(근무상황) 매칭 시 직급 필터를 없애고, 결과화면에 데이터를 보존한 채 되돌아갈 수 있는 뒤로가기를 추가하고, 계산 실행 전 계약기간을 재확인하는 확인창을 추가한다.

**Architecture:** 기존 `wage_calculator`(tkinter GUI + core 계산 로직) 구조를 그대로 따르는 3건의 국소적 변경. 새 모듈은 만들지 않는다.

**Tech Stack:** Python 3, tkinter, openpyxl. 테스트는 pytest 없이 순수 `assert` + `if __name__ == "__main__"` 스크립트(`python tests/test_x.py`로 개별 실행) — 이 저장소의 기존 관례를 그대로 따른다.

## Global Constraints

- 설계 문서: [`docs/superpowers/specs/2026-08-05-matching-navigation-retroactive-design.md`](../specs/2026-08-05-matching-navigation-retroactive-design.md) §1~§3
- 기존 동작을 바꾸지 않는 범위(예: `missing_names`/`ambiguous_names` 검증)는 그대로 유지한다.
- GUI(tkinter) 코드는 이 저장소에 자동화 테스트가 없다(기존 관례) — 이 플랜의 GUI 작업은 "앱을 실행해 직접 확인" 스텝으로 검증한다.

---

### Task 1: `load_giganje_rows`에서 직급 필터 제거

**Files:**
- Modify: `wage_calculator/core/parser.py:53-74`
- Test: `wage_calculator/tests/test_parser_rank_filter_removed.py` (create)

**Interfaces:**
- Consumes: 없음(기존 `load_giganje_rows(path) -> list[dict]` 시그니처 그대로)
- Produces: `load_giganje_rows(path)`가 직급과 무관하게 성명이 있는 모든 행을 반환

- [ ] **Step 1: 실패하는 테스트 작성**

`wage_calculator/tests/test_parser_rank_filter_removed.py`:

```python
import sys
from pathlib import Path
import tempfile
import os

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import openpyxl
from core.parser import load_giganje_rows


def _write_b_file(path):
    wb = openpyxl.Workbook()
    ws = wb.active
    headers = ["소속", "직급", "성명", "생년월일", "종별", "사용기간(날짜)", "사용시간(시분)", "사유", "연락처", "결재상태", "비고"]
    ws.append(headers)
    ws.append(["정보통계과", "기간제근로자", "김철수", "1990-01-01", "연가", "2026-07-06", None, None, "", "결재완료", None])
    ws.append(["정보통계과", "일반직", "박정규", "1985-05-05", "연가", "2026-07-06", None, None, "", "결재완료", None])
    wb.save(path)


def test_non_giganje_rank_rows_are_kept():
    fd, path = tempfile.mkstemp(suffix=".xlsx")
    os.close(fd)
    try:
        _write_b_file(path)
        rows = load_giganje_rows(path)
        names = [r["성명"] for r in rows]
        assert "김철수" in names, names
        assert "박정규" in names, "직급이 '기간제'가 아니어도 행이 반환되어야 함: " + str(names)
        assert len(rows) == 2, rows
        print("OK: test_non_giganje_rank_rows_are_kept")
    finally:
        os.remove(path)


if __name__ == "__main__":
    test_non_giganje_rank_rows_are_kept()
    print("ALL OK")
```

- [ ] **Step 2: 테스트 실행해 실패 확인**

Run: `python wage_calculator/tests/test_parser_rank_filter_removed.py`
Expected: `AssertionError: 직급이 '기간제'가 아니어도 행이 반환되어야 함: ['김철수']` (박정규 행이 필터링되어 빠짐)

- [ ] **Step 3: 필터 제거**

[`wage_calculator/core/parser.py:53-74`](../../../wage_calculator/core/parser.py) 전체를 아래로 교체:

```python
def load_giganje_rows(path) -> list:
    """B파일(근무상황) 로드(원본 dict 리스트).

    직급으로 거르지 않는다 - A파일(개인정보)이 이미 급여계산 대상자만
    추려서 관리되므로, build_target_people()에서 이름+생년월일로 A파일과
    매칭되는 행만 자연스럽게 급여 계산에 반영된다.
    """
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.worksheets[0]
    headers = _header_index(ws)
    required = ["소속", "직급", "성명", "생년월일", "종별", "사용기간(날짜)", "사용시간(시분)"]
    missing = [h for h in required if h not in headers]
    if missing:
        raise ValueError(f"B파일(근무상황)에 필수 컬럼이 없습니다: {missing}")

    rows = []
    for r in range(2, ws.max_row + 1):
        row = _row_dict(ws, r, headers)
        name = row.get("성명")
        if name is None or str(name).strip() == "":
            continue
        row["성명"] = str(name).strip()
        rows.append(row)
    return rows
```

- [ ] **Step 4: 테스트 실행해 통과 확인**

Run: `python wage_calculator/tests/test_parser_rank_filter_removed.py`
Expected: `OK: test_non_giganje_rank_rows_are_kept` / `ALL OK`

- [ ] **Step 5: 기존 테스트 전체 회귀 확인**

Run 아래 파일들을 각각 실행(직급 필터를 전제로 한 기존 테스트가 있었다면 여기서 깨짐):
```bash
python wage_calculator/tests/test_end_to_end_v3.py
python wage_calculator/tests/test_parser_source_range.py
python wage_calculator/tests/test_source_range.py
python wage_calculator/tests/test_special_leave_grouping.py
python wage_calculator/tests/test_mapping_special_leave.py
python wage_calculator/tests/test_leave_engine_weekly.py
python wage_calculator/tests/test_payroll_special_leave.py
python wage_calculator/tests/test_wage_sheet_special_leave.py
```
Expected: 전부 `ALL OK`

- [ ] **Step 6: 커밋**

```bash
git add wage_calculator/core/parser.py wage_calculator/tests/test_parser_rank_filter_removed.py
git commit -m "fix: B파일 매칭 시 직급 필터 제거, A파일 로스터+이름생년월일 매칭에 위임"
```

---

### Task 2: 결과화면 비파괴 뒤로가기 + 메뉴바 전체초기화

**Files:**
- Modify: `wage_calculator/gui/app.py`
- Modify: `wage_calculator/gui/result_screen.py`

**Interfaces:**
- Consumes: 기존 `App.show_target_screen()`, `App.reset()`(수정 없음)
- Produces: `App.confirm_and_reset()`(신규, 확인 팝업 후 `reset()` 호출) — 메뉴바와 결과화면 둘 다 이걸 씀

- [ ] **Step 1: `app.py`에 `confirm_and_reset()` 추가 + 메뉴에 항목 추가**

[`wage_calculator/gui/app.py`](../../../wage_calculator/gui/app.py)의 `_build_menu`를 아래로 교체:

```python
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
```

(`_show_settings_reminder` 등 그 아래 메서드들은 그대로 둔다. `messagebox`는 이미 `from tkinter import messagebox, ttk`로 임포트되어 있음.)

- [ ] **Step 2: `result_screen.py`에 뒤로가기 버튼 추가 + 새로계산 버튼이 `confirm_and_reset` 재사용**

[`wage_calculator/gui/result_screen.py`](../../../wage_calculator/gui/result_screen.py)에서 아래 부분을:

```python
        bottom = ttk.Frame(self)
        bottom.pack(fill="x", padx=10, pady=10)
        ttk.Button(bottom, text="엑셀 다운로드", command=self._download).pack(side="left")
        ttk.Button(bottom, text="산정근거 확인", command=self.app.show_evidence_screen).pack(side="left", padx=8)
        ttk.Button(bottom, text="새로 계산(처음부터)", command=self._reset).pack(side="right")
```

아래로 교체:

```python
        bottom = ttk.Frame(self)
        bottom.pack(fill="x", padx=10, pady=10)
        ttk.Button(bottom, text="엑셀 다운로드", command=self._download).pack(side="left")
        ttk.Button(bottom, text="산정근거 확인", command=self.app.show_evidence_screen).pack(side="left", padx=8)
        ttk.Button(bottom, text="새로 계산(처음부터)", command=self.app.confirm_and_reset).pack(side="right")
        ttk.Button(bottom, text="뒤로가기", command=self._back).pack(side="right", padx=8)
```

그리고 파일 하단의 `_reset` 메서드를 지우고 그 자리에 `_back`을 추가한다(기존):

```python
    def _reset(self):
        if messagebox.askyesno("새로 계산", "처음(파일 업로드)부터 다시 시작하시겠습니까? 현재 계산 결과는 사라집니다."):
            self.app.reset()
```

를 아래로 교체:

```python
    def _back(self):
        self.app.show_target_screen()
```

- [ ] **Step 3: 수동 확인**

앱 실행:
```bash
python wage_calculator/main.py
```
1. A/B파일 업로드 → 대상자 확인 화면에서 아무 인원 조사 매칭 후 연/월 입력 → 계산 실행 → 확인창들 진행 → 결과화면 도달.
2. "뒤로가기" 클릭 → 대상자 확인 화면(TargetScreen)으로 돌아가고, 업로드했던 파일 기반 인원 목록과 조사 매칭이 그대로 남아있는지 확인(팝업 없이 즉시 이동해야 함).
3. 연/월을 바꾸고 다시 "계산 실행" → 정상적으로 재계산되는지 확인.
4. 결과화면에서 "새로 계산(처음부터)" 클릭 → 확인 팝업 후 업로드 화면으로 돌아가고 입력값이 전부 비어있는지 확인(기존 동작 유지).
5. 메뉴 > "새 파일로 시작" 클릭 → 어느 화면에서 클릭해도 동일한 확인 팝업 후 업로드 화면으로 돌아가는지 확인.

- [ ] **Step 4: 커밋**

```bash
git add wage_calculator/gui/app.py wage_calculator/gui/result_screen.py
git commit -m "feat: 결과화면에 상태 보존 뒤로가기 추가, 전체초기화는 메뉴바로도 접근 가능하게"
```

---

### Task 3: 계산 실행 전 계약기간 사전확인 확인창

**Files:**
- Modify: `wage_calculator/gui/confirm_dialog.py`
- Modify: `wage_calculator/gui/app.py`
- Modify: `wage_calculator/gui/target_screen.py`

**Interfaces:**
- Consumes: `App.open_confirm_dialog()`(기존, 수정 없음)
- Produces: `App.open_contract_period_check_dialog()`(신규) — `TargetScreen._proceed()`가 계산 실행 진입점으로 이걸 호출

- [ ] **Step 1: `ContractPeriodCheckDialog` 추가**

[`wage_calculator/gui/confirm_dialog.py`](../../../wage_calculator/gui/confirm_dialog.py) 맨 위 `class ConfirmRunDialog` 앞에 새 클래스를 추가:

```python
class ContractPeriodCheckDialog(tk.Toplevel):
    """6장-3 앞단: 기존 ConfirmRunDialog보다 먼저 떠서, 중도퇴사자·추가입사자의
    계약기간을 담당자가 직접 다시 확인하도록 유도하는 확인창."""

    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.title("계약기간 확인")
        self.geometry("420x180")
        self.grab_set()

        msg = (
            "중도퇴사자와 추가입사자의 계약기간을 정확히 입력했는지 확인하세요.\n\n"
            "계약기간이 틀리면 급여계산기간과 주휴/연차 판정이 모두 잘못 나옵니다."
        )
        ttk.Label(self, text=msg, wraplength=380, justify="left").pack(padx=16, pady=16)

        btns = ttk.Frame(self)
        btns.pack(pady=8)
        ttk.Button(btns, text="아니오(다시입력)", command=self.destroy).pack(side="left", padx=8)
        ttk.Button(btns, text="네(진행)", command=self._proceed).pack(side="left", padx=8)

    def _proceed(self):
        self.destroy()
        self.app.open_confirm_dialog()
```

- [ ] **Step 2: `app.py`에 헬퍼 추가**

[`wage_calculator/gui/app.py`](../../../wage_calculator/gui/app.py) 상단 임포트를:

```python
from gui.confirm_dialog import ConfirmRunDialog
```

에서 아래로 교체:

```python
from gui.confirm_dialog import ConfirmRunDialog, ContractPeriodCheckDialog
```

그리고 기존 `open_confirm_dialog` 메서드 바로 위나 아래에 추가:

```python
    def open_contract_period_check_dialog(self):
        ContractPeriodCheckDialog(self, self)
```

- [ ] **Step 3: `target_screen.py` 진입점 교체**

[`wage_calculator/gui/target_screen.py`](../../../wage_calculator/gui/target_screen.py) `_proceed()` 맨 마지막 줄:

```python
        self.app.work_year = year
        self.app.work_month = month
        self.app.open_confirm_dialog()
```

를:

```python
        self.app.work_year = year
        self.app.work_month = month
        self.app.open_contract_period_check_dialog()
```

로 교체.

- [ ] **Step 4: 수동 확인**

```bash
python wage_calculator/main.py
```
1. 업로드 → 대상자 확인 화면에서 연/월 입력 후 "계산 실행" 클릭.
2. "계약기간을 정확히 입력했는지 확인하세요" 확인창이 **가장 먼저** 뜨는지 확인.
3. "아니오(다시입력)" 클릭 → 창만 닫히고 대상자 확인 화면에 그대로 남아있는지(값 보존) 확인.
4. 다시 "계산 실행" → 이번엔 "네(진행)" 클릭 → 기존 `ConfirmRunDialog`(공휴일/공통입력값 안내)가 이어서 뜨는지 확인.
5. 거기서 "계속(계산 실행)" 클릭 → 정상적으로 결과화면까지 도달하는지 확인.

- [ ] **Step 5: 커밋**

```bash
git add wage_calculator/gui/confirm_dialog.py wage_calculator/gui/app.py wage_calculator/gui/target_screen.py
git commit -m "feat: 계산 실행 전 중도퇴사자/추가입사자 계약기간 사전확인 확인창 추가"
```
