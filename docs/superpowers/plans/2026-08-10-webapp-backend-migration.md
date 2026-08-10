# 웹 백엔드(AppState + FastAPI) 마이그레이션 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `wage_calculator/gui/*`의 orchestration/검증 로직을 tkinter에서 분리해 `webapp/state.py`(AppState)로 옮기고, 그 위에 FastAPI JSON API(`webapp/server.py`)를 얹어 `TestClient`로 완전히 검증 가능한 백엔드를 만든다. 프론트엔드(HTML/JS)와 pywebview 부트스트랩, PyInstaller 패키징은 이후 별도 계획에서 다룬다.

**Architecture:** `AppState`는 지금 `App(tk.Tk)`가 들고 있던 데이터(`employees`, `people`, `results` 등)와 orchestration 메서드(`load_files`, `run_calculation` 등)를 그대로 옮긴 평범한 Python 객체다. FastAPI 라우트는 이 메서드를 호출하고 결과를 JSON으로 감싸기만 한다. `core/`, `output/`은 전혀 수정하지 않는다(계산 결과가 마이그레이션 전후로 완전히 동일해야 함).

**Tech Stack:** Python, FastAPI, pydantic, uvicorn(런타임에만 필요, 이 계획에서는 미사용), httpx(TestClient 의존성), 기존 `core`/`output` 모듈.

## Global Constraints

- `wage_calculator/core/*`, `wage_calculator/output/*`의 계산 로직은 수정하지 않는다(설계 문서 §1 원칙). 이 계획에서 `core/config.py`에 `last_upload_dir` 필드를 추가하는 것만 유일한 예외다(설계 문서 §5-1에서 이미 승인됨).
- 이 저장소의 테스트는 pytest 설정 파일 없이 스크립트 방식으로 작성되어 있다(`sys.path.insert(0, ...)` + `assert` + `if __name__ == "__main__":`). 새 테스트도 이 관례를 따른다. 단, FastAPI `TestClient`를 쓰는 테스트는 `pytest`로 실행한다(아래 각 태스크의 Run 명령 참고).
- 참조: `docs/superpowers/specs/2026-08-10-pywebview-webapp-migration-design.md`, `docs/superpowers/specs/reference/근무상황_종별_안내_전사.md`
- 이 계획을 시작하기 전에 로컬 개발 환경에 `pip install fastapi httpx`를 실행해 둔다(uvicorn/pywebview는 다음 계획에서 필요하므로 여기서는 설치하지 않아도 됨).
- 테스트 픽스처는 `demo_assets/개인정보_예시(A).xlsx`, `demo_assets/근무상황_예시(B).xlsx`(이미 검증된 더미 데이터, 5명, 특별휴가 1건 포함)를 사용한다. `*.xlsx`는 `.gitignore`로 전역 차단되어 있으므로 이 파일들은 로컬에만 존재한다 — 이 계획을 실행하는 개발자의 로컬 저장소에 이미 파일이 있는지 Task 1 시작 전에 확인한다.

---

### Task 1: `Config`에 `last_upload_dir` 필드 추가

**Files:**
- Modify: `wage_calculator/core/config.py`
- Test: `wage_calculator/tests/test_config_last_upload_dir.py`

**Interfaces:**
- Produces: `Config.last_upload_dir: str`(기본값 `""`), `Config.set_last_upload_dir(path: str) -> None`, `Config.to_dict()`에 `"last_upload_dir"` 키 포함.

- [ ] **Step 1: 실패하는 테스트 작성**

`wage_calculator/tests/test_config_last_upload_dir.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import Config


def test_last_upload_dir_defaults_to_empty_string():
    config = Config({"surveys": [], "rates": {}, "holidays": []})
    assert config.last_upload_dir == ""
    print("OK: test_last_upload_dir_defaults_to_empty_string")


def test_set_last_upload_dir_updates_to_dict():
    config = Config({"surveys": [], "rates": {}, "holidays": []})
    config.set_last_upload_dir("C:/Users/example/Desktop")
    assert config.to_dict()["last_upload_dir"] == "C:/Users/example/Desktop"
    print("OK: test_set_last_upload_dir_updates_to_dict")


def test_last_upload_dir_round_trips_through_load():
    data = {"surveys": [], "rates": {}, "holidays": [], "last_upload_dir": "D:/data"}
    config = Config(data)
    assert config.last_upload_dir == "D:/data"
    print("OK: test_last_upload_dir_round_trips_through_load")


if __name__ == "__main__":
    test_last_upload_dir_defaults_to_empty_string()
    test_set_last_upload_dir_updates_to_dict()
    test_last_upload_dir_round_trips_through_load()
    print("ALL OK")
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python wage_calculator/tests/test_config_last_upload_dir.py`
Expected: `AttributeError: 'Config' object has no attribute 'last_upload_dir'`

- [ ] **Step 3: `Config`에 필드/메서드 추가**

`wage_calculator/core/config.py`의 `__init__` 마지막 줄(`self.holidays = sorted(set(data.get("holidays", [])))`) 바로 뒤에 추가:

```python
        self.last_upload_dir = str(data.get("last_upload_dir", ""))
```

`# ---- 공휴일 ----` 섹션과 `# ---- 연도별 요율 ----` 섹션 사이, 또는 파일 마지막 섹션 앞에 새 섹션 추가:

```python
    # ---- 파일 선택 경로 ----
    def set_last_upload_dir(self, path: str):
        self.last_upload_dir = path
```

`to_dict()` 메서드를 다음과 같이 수정:

```python
    def to_dict(self):
        return {
            "surveys": self.surveys,
            "rates": self.rates,
            "holidays": self.holidays,
            "last_upload_dir": self.last_upload_dir,
        }
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python wage_calculator/tests/test_config_last_upload_dir.py`
Expected: `ALL OK`

- [ ] **Step 5: 커밋**

```bash
git add wage_calculator/core/config.py wage_calculator/tests/test_config_last_upload_dir.py
git commit -m "feat: Config에 last_upload_dir 필드 추가"
```

---

### Task 2: `webapp` 패키지 + `AppState` 스켈레톤(reset)

**Files:**
- Create: `wage_calculator/webapp/__init__.py`
- Create: `wage_calculator/webapp/state.py`
- Test: `wage_calculator/tests/test_webapp_state_core.py`

**Interfaces:**
- Consumes: `core.config.Config`(Task 1에서 확장됨)
- Produces: `AppState` 클래스, `AppState().config_obj: Config`, `AppState().reset() -> None`, 그리고 `employees/giganje_rows/people/missing_names/ambiguous_names/work_year/work_month/results/previous_payroll/retro_adjustments/retro_details/departed_results/pending_leave_groups` 속성.

- [ ] **Step 1: 실패하는 테스트 작성**

`wage_calculator/tests/test_webapp_state_core.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from webapp.state import AppState


def test_initial_state_has_empty_collections():
    state = AppState()
    assert state.employees == {}
    assert state.people == {}
    assert state.results == []
    assert state.work_year is None
    assert state.work_month is None
    assert state.pending_leave_groups == []
    print("OK: test_initial_state_has_empty_collections")


def test_reset_clears_mutated_fields_but_keeps_config():
    state = AppState()
    original_config = state.config_obj
    state.employees = {"홍길동": []}
    state.work_year = 2026
    state.work_month = 8
    state.results = ["더미"]

    state.reset()

    assert state.employees == {}
    assert state.work_year is None
    assert state.work_month is None
    assert state.results == []
    assert state.config_obj is original_config
    print("OK: test_reset_clears_mutated_fields_but_keeps_config")


if __name__ == "__main__":
    test_initial_state_has_empty_collections()
    test_reset_clears_mutated_fields_but_keeps_config()
    print("ALL OK")
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python wage_calculator/tests/test_webapp_state_core.py`
Expected: `ModuleNotFoundError: No module named 'webapp'`

- [ ] **Step 3: 패키지와 `AppState` 스켈레톤 작성**

`wage_calculator/webapp/__init__.py` (빈 파일):

```python
```

`wage_calculator/webapp/state.py`:

```python
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
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python wage_calculator/tests/test_webapp_state_core.py`
Expected: `ALL OK`

- [ ] **Step 5: 커밋**

```bash
git add wage_calculator/webapp/__init__.py wage_calculator/webapp/state.py wage_calculator/tests/test_webapp_state_core.py
git commit -m "feat: webapp 패키지 + AppState 스켈레톤 추가"
```

---

### Task 3: `AppState.load_files()` + 특별휴가 대기 그룹 수집

**Files:**
- Modify: `wage_calculator/webapp/state.py`
- Test: `wage_calculator/tests/test_webapp_state_upload.py`

**Interfaces:**
- Consumes: `core.parser.{load_employees, load_giganje_rows, build_target_people, load_previous_payroll}`
- Produces: `AppState.load_files(a_path, b_path, prev_payroll_path=None) -> dict`(키: `ambiguous_names: list[str]`, `has_pending_special_leave: bool`), 모듈 함수 `collect_pending_groups(people) -> list[dict]`(키: `person_key, person_name, start, end, events, status`)

- [ ] **Step 1: 실패하는 테스트 작성**

`wage_calculator/tests/test_webapp_state_upload.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from webapp.state import AppState

FIXTURE_DIR = Path(__file__).resolve().parent.parent.parent / "demo_assets"
A_FILE = FIXTURE_DIR / "개인정보_예시(A).xlsx"
B_FILE = FIXTURE_DIR / "근무상황_예시(B).xlsx"


def test_load_files_populates_people_and_flags_pending_special_leave():
    state = AppState()
    result = state.load_files(str(A_FILE), str(B_FILE))

    assert len(state.people) == 5
    assert result["ambiguous_names"] == []
    assert result["has_pending_special_leave"] is True
    assert len(state.pending_leave_groups) == 1
    assert state.pending_leave_groups[0]["person_name"] == "최지은"
    print("OK: test_load_files_populates_people_and_flags_pending_special_leave")


def test_load_files_without_previous_payroll_leaves_it_empty():
    state = AppState()
    state.load_files(str(A_FILE), str(B_FILE))
    assert state.previous_payroll == {}
    print("OK: test_load_files_without_previous_payroll_leaves_it_empty")


if __name__ == "__main__":
    test_load_files_populates_people_and_flags_pending_special_leave()
    test_load_files_without_previous_payroll_leaves_it_empty()
    print("ALL OK")
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python wage_calculator/tests/test_webapp_state_upload.py`
Expected: `AttributeError: 'AppState' object has no attribute 'load_files'`

- [ ] **Step 3: `load_files()` + `collect_pending_groups()` 구현**

`wage_calculator/webapp/state.py` 맨 위 import를 다음으로 교체(기존 `from core.config import Config` 포함):

```python
from core import date_utils
from core.config import Config
from core.parser import (
    build_target_people,
    load_employees,
    load_giganje_rows,
    load_previous_payroll,
)
```

`AppState` 클래스 정의 **앞**(모듈 레벨)에 `gui/special_leave_screen.py`에서 그대로 옮긴 두 함수를 추가:

```python
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
```

`AppState` 클래스 안, `reset` 메서드 뒤에 추가:

```python
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
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python wage_calculator/tests/test_webapp_state_upload.py`
Expected: `ALL OK`

- [ ] **Step 5: 커밋**

```bash
git add wage_calculator/webapp/state.py wage_calculator/tests/test_webapp_state_upload.py
git commit -m "feat: AppState.load_files + 특별휴가 대기 그룹 수집 이관"
```

---

### Task 4: 특별휴가 그룹 조회/확정

**Files:**
- Modify: `wage_calculator/webapp/state.py`
- Test: `wage_calculator/tests/test_webapp_state_special_leave.py`

**Interfaces:**
- Produces: `AppState.special_leave_groups() -> list[dict]`(키: `index, person_name, start, end, reason, note, status`), `AppState.confirm_special_leave(statuses: list[str]) -> None`(raises `ValueError`)

- [ ] **Step 1: 실패하는 테스트 작성**

`wage_calculator/tests/test_webapp_state_special_leave.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from webapp.state import AppState

FIXTURE_DIR = Path(__file__).resolve().parent.parent.parent / "demo_assets"
A_FILE = FIXTURE_DIR / "개인정보_예시(A).xlsx"
B_FILE = FIXTURE_DIR / "근무상황_예시(B).xlsx"


def _loaded_state():
    state = AppState()
    state.load_files(str(A_FILE), str(B_FILE))
    return state


def test_special_leave_groups_includes_reason_and_note():
    state = _loaded_state()
    groups = state.special_leave_groups()
    assert len(groups) == 1
    g = groups[0]
    assert g["index"] == 0
    assert g["person_name"] == "최지은"
    assert g["start"] == "2026-08-17"
    assert g["end"] == "2026-08-18"
    assert g["reason"] == "본인결혼"
    assert g["note"] == "경조사"
    assert g["status"] is None
    print("OK: test_special_leave_groups_includes_reason_and_note")


def test_confirm_special_leave_sets_event_classification():
    state = _loaded_state()
    state.confirm_special_leave(["유급특별휴가"])
    events = state.pending_leave_groups[0]["events"]
    assert all(e.classified == "유급특별휴가" for e in events)
    print("OK: test_confirm_special_leave_sets_event_classification")


def test_confirm_special_leave_rejects_wrong_length():
    state = _loaded_state()
    try:
        state.confirm_special_leave([])
        assert False, "ValueError를 기대했지만 발생하지 않음"
    except ValueError:
        pass
    print("OK: test_confirm_special_leave_rejects_wrong_length")


def test_confirm_special_leave_rejects_empty_status():
    state = _loaded_state()
    try:
        state.confirm_special_leave([""])
        assert False, "ValueError를 기대했지만 발생하지 않음"
    except ValueError:
        pass
    print("OK: test_confirm_special_leave_rejects_empty_status")


if __name__ == "__main__":
    test_special_leave_groups_includes_reason_and_note()
    test_confirm_special_leave_sets_event_classification()
    test_confirm_special_leave_rejects_wrong_length()
    test_confirm_special_leave_rejects_empty_status()
    print("ALL OK")
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python wage_calculator/tests/test_webapp_state_special_leave.py`
Expected: `AttributeError: 'AppState' object has no attribute 'special_leave_groups'`

- [ ] **Step 3: 구현**

`wage_calculator/webapp/state.py`의 `load_files` 메서드 뒤에 추가:

```python
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
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python wage_calculator/tests/test_webapp_state_special_leave.py`
Expected: `ALL OK`

- [ ] **Step 5: 커밋**

```bash
git add wage_calculator/webapp/state.py wage_calculator/tests/test_webapp_state_special_leave.py
git commit -m "feat: AppState 특별휴가 조회/확정 이관"
```

---

### Task 5: 대상자 조회 / 담당조사 일괄 매칭 / 계약기간 수정 / 계산 진입 검증

**Files:**
- Modify: `wage_calculator/webapp/state.py`
- Test: `wage_calculator/tests/test_webapp_state_targets.py`

**Interfaces:**
- Produces: `AppState.targets() -> list[dict]`(키: `key, label, survey_name, contract_start, contract_end`), `AppState.survey_names() -> list[str]`, `AppState.batch_assign(keys: list[str], survey_name: str) -> None`(raises `ValueError`), `AppState.edit_contract(key: str, start: str, end: str) -> None`, `AppState.prepare_calculation(year: int, month: int) -> list[str]`(unassigned 이름 목록, raises `ValueError`)

- [ ] **Step 1: 실패하는 테스트 작성**

`wage_calculator/tests/test_webapp_state_targets.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import Config
from webapp.state import AppState

FIXTURE_DIR = Path(__file__).resolve().parent.parent.parent / "demo_assets"
A_FILE = FIXTURE_DIR / "개인정보_예시(A).xlsx"
B_FILE = FIXTURE_DIR / "근무상황_예시(B).xlsx"


def _config_with_survey():
    return Config({
        "surveys": [{"name": "8월 정기조사", "start": "2026-08-01", "end": "2026-08-31"}],
        "rates": {"2026": {"daily_wage": 78560, "meal_allowance": 160000}},
        "holidays": ["2026-08-15"],
    })


def _loaded_state():
    state = AppState()
    state.config_obj = _config_with_survey()
    state.load_files(str(A_FILE), str(B_FILE))
    return state


def test_targets_lists_all_people():
    state = _loaded_state()
    rows = state.targets()
    assert len(rows) == 5
    assert {"key", "label", "survey_name", "contract_start", "contract_end"} <= rows[0].keys()
    print("OK: test_targets_lists_all_people")


def test_survey_names_reflects_config():
    state = _loaded_state()
    assert state.survey_names() == ["8월 정기조사"]
    print("OK: test_survey_names_reflects_config")


def test_batch_assign_sets_survey_and_contract_dates():
    state = _loaded_state()
    keys = list(state.people.keys())
    state.batch_assign(keys, "8월 정기조사")
    for person in state.people.values():
        assert person.survey_name == "8월 정기조사"
        assert person.contract_start.isoformat() == "2026-08-01"
        assert person.contract_end.isoformat() == "2026-08-31"
        assert person.contract_overridden is False
    print("OK: test_batch_assign_sets_survey_and_contract_dates")


def test_batch_assign_rejects_unknown_survey():
    state = _loaded_state()
    keys = list(state.people.keys())
    try:
        state.batch_assign(keys, "존재하지않는조사")
        assert False, "ValueError를 기대했지만 발생하지 않음"
    except ValueError:
        pass
    print("OK: test_batch_assign_rejects_unknown_survey")


def test_edit_contract_marks_overridden():
    state = _loaded_state()
    key = next(iter(state.people.keys()))
    state.edit_contract(key, "2026-08-05", "2026-08-20")
    person = state.people[key]
    assert person.contract_start.isoformat() == "2026-08-05"
    assert person.contract_end.isoformat() == "2026-08-20"
    assert person.contract_overridden is True
    print("OK: test_edit_contract_marks_overridden")


def test_prepare_calculation_rejects_invalid_month():
    state = _loaded_state()
    try:
        state.prepare_calculation(2026, 13)
        assert False, "ValueError를 기대했지만 발생하지 않음"
    except ValueError:
        pass
    print("OK: test_prepare_calculation_rejects_invalid_month")


def test_prepare_calculation_returns_unassigned_and_sets_work_period():
    state = _loaded_state()
    unassigned = state.prepare_calculation(2026, 8)
    assert state.work_year == 2026
    assert state.work_month == 8
    assert len(unassigned) == 5  # 아직 담당조사 미배정
    print("OK: test_prepare_calculation_returns_unassigned_and_sets_work_period")


if __name__ == "__main__":
    test_targets_lists_all_people()
    test_survey_names_reflects_config()
    test_batch_assign_sets_survey_and_contract_dates()
    test_batch_assign_rejects_unknown_survey()
    test_edit_contract_marks_overridden()
    test_prepare_calculation_rejects_invalid_month()
    test_prepare_calculation_returns_unassigned_and_sets_work_period()
    print("ALL OK")
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python wage_calculator/tests/test_webapp_state_targets.py`
Expected: `AttributeError: 'AppState' object has no attribute 'targets'`

- [ ] **Step 3: 구현**

`wage_calculator/webapp/state.py` 상단 import 블록의 `from core.parser import (...)`를 다음으로 교체(마지막 줄에 `display_label` 추가):

```python
from core.parser import (
    build_target_people,
    display_label,
    load_employees,
    load_giganje_rows,
    load_previous_payroll,
)
```

`confirm_special_leave` 메서드 뒤에 추가:

```python
    def targets(self):
        all_names = [p.name for p in self.people.values()]
        out = []
        for key, person in self.people.items():
            out.append({
                "key": key,
                "label": display_label(person.name, person.birth, all_names),
                "survey_name": person.survey_name or "",
                "contract_start": person.contract_start.isoformat() if person.contract_start else "",
                "contract_end": person.contract_end.isoformat() if person.contract_end else "",
            })
        return out

    def survey_names(self):
        return self.config_obj.survey_names()

    def batch_assign(self, keys, survey_name):
        survey = self.config_obj.get_survey(survey_name)
        if survey is None:
            raise ValueError(f"등록되지 않은 담당조사입니다: {survey_name}")
        start = date_utils.parse_date(survey["start"])
        end = date_utils.parse_date(survey["end"])
        for key in keys:
            person = self.people[key]
            person.survey_name = survey_name
            person.contract_start = start
            person.contract_end = end
            person.contract_overridden = False

    def edit_contract(self, key, start, end):
        person = self.people[key]
        person.contract_start = date_utils.parse_date(start)
        person.contract_end = date_utils.parse_date(end)
        person.contract_overridden = True

    def prepare_calculation(self, year, month):
        """대상자 확인 화면의 '계산 실행' 검증. 통과하면 work_year/work_month를
        세팅하고 담당조사 미지정 인원 명단을 돌려준다(경고 표시용, 차단은 아님)."""
        if self.ambiguous_names:
            raise ValueError(
                "동명이인을 구분할 수 없는 대상자가 있어 계산을 진행할 수 없습니다: "
                + ", ".join(self.ambiguous_names)
            )
        if not (1 <= month <= 12):
            raise ValueError("급여산정 연/월을 올바르게 입력하세요.")
        self.work_year = year
        self.work_month = month
        return [p.name for p in self.people.values() if not p.survey_name]
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python wage_calculator/tests/test_webapp_state_targets.py`
Expected: `ALL OK`

- [ ] **Step 5: 커밋**

```bash
git add wage_calculator/webapp/state.py wage_calculator/tests/test_webapp_state_targets.py
git commit -m "feat: AppState 대상자 조회/일괄매칭/계약수정/진입검증 이관"
```

---

### Task 6: 계산 실행 확인 정보 + 계산 실행(소급 포함)

**Files:**
- Modify: `wage_calculator/webapp/state.py`
- Test: `wage_calculator/tests/test_webapp_state_calculate.py`

**Interfaces:**
- Consumes: `core.payroll.calc_payroll`, `core.retroactive.compute_retroactive`
- Produces: `AppState.confirm_info() -> dict`(키: `year, month, holidays, daily_wage, meal_allowance, overridden_names`), `AppState.run_calculation() -> list[str]`(에러 메시지 목록, 성공 시 빈 리스트)

- [ ] **Step 1: 실패하는 테스트 작성**

`wage_calculator/tests/test_webapp_state_calculate.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import Config
from webapp.state import AppState

FIXTURE_DIR = Path(__file__).resolve().parent.parent.parent / "demo_assets"
A_FILE = FIXTURE_DIR / "개인정보_예시(A).xlsx"
B_FILE = FIXTURE_DIR / "근무상황_예시(B).xlsx"


def _config_with_survey():
    return Config({
        "surveys": [{"name": "8월 정기조사", "start": "2026-08-01", "end": "2026-08-31"}],
        "rates": {"2026": {"daily_wage": 78560, "meal_allowance": 160000}},
        "holidays": ["2026-08-15"],
    })


def _ready_state():
    state = AppState()
    state.config_obj = _config_with_survey()
    state.load_files(str(A_FILE), str(B_FILE))
    state.confirm_special_leave(["유급특별휴가"])
    keys = list(state.people.keys())
    state.batch_assign(keys, "8월 정기조사")
    state.prepare_calculation(2026, 8)
    return state


def test_confirm_info_reports_holidays_and_rates():
    state = _ready_state()
    info = state.confirm_info()
    assert info["year"] == 2026
    assert info["month"] == 8
    assert info["holidays"] == ["2026-08-15"]
    assert info["daily_wage"] == 78560
    assert info["meal_allowance"] == 160000
    assert info["overridden_names"] == []
    print("OK: test_confirm_info_reports_holidays_and_rates")


def test_run_calculation_produces_results_for_all_assigned_people():
    state = _ready_state()
    errors = state.run_calculation()
    assert errors == []
    assert len(state.results) == 5
    print("OK: test_run_calculation_produces_results_for_all_assigned_people")


def test_run_calculation_skips_retroactive_when_no_previous_payroll():
    state = _ready_state()
    state.run_calculation()
    assert state.retro_adjustments == {}
    assert state.departed_results == []
    print("OK: test_run_calculation_skips_retroactive_when_no_previous_payroll")


if __name__ == "__main__":
    test_confirm_info_reports_holidays_and_rates()
    test_run_calculation_produces_results_for_all_assigned_people()
    test_run_calculation_skips_retroactive_when_no_previous_payroll()
    print("ALL OK")
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python wage_calculator/tests/test_webapp_state_calculate.py`
Expected: `AttributeError: 'AppState' object has no attribute 'confirm_info'`

- [ ] **Step 3: 구현**

`wage_calculator/webapp/state.py` 파일 맨 위, `from core import date_utils` 다음 줄에 추가:

```python
from datetime import date

from core.payroll import calc_payroll
from core.retroactive import compute_retroactive
```

(import 순서는 파일 상단에 몰아서 정리한다 - 최종 import 블록은 Task 8까지 완료되면 아래와 같아진다. 지금은 `from datetime import date`, `from core.payroll import calc_payroll`, `from core.retroactive import compute_retroactive` 세 줄만 추가하면 된다.)

`prepare_calculation` 메서드 뒤에 추가:

```python
    def confirm_info(self):
        year, month = self.work_year, self.work_month
        month_first = date(year, month, 1)
        month_last = date(year, month, date_utils.month_calendar_days(month_first))
        holidays = self.config_obj.holidays_in_range(month_first.isoformat(), month_last.isoformat())
        overridden = [p.name for p in self.people.values() if p.contract_overridden]
        return {
            "year": year,
            "month": month,
            "holidays": holidays,
            "daily_wage": self.config_obj.daily_wage_for(year),
            "meal_allowance": self.config_obj.meal_allowance_for(year),
            "overridden_names": overridden,
        }

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
        self.retro_details = {}
        self.departed_results = []
        if self.previous_payroll:
            prev_year, prev_month = date_utils.previous_month(self.work_year, self.work_month)
            try:
                retro = compute_retroactive(
                    self.people, self.previous_payroll, self.giganje_rows,
                    self.config_obj, prev_year, prev_month,
                )
                self.retro_adjustments = retro.adjustments
                self.retro_details = retro.details
                self.departed_results = retro.departed
                errors.extend(retro.errors)
            except Exception as e:
                errors.append(f"소급계산 오류: {e}")
        return errors
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python wage_calculator/tests/test_webapp_state_calculate.py`
Expected: `ALL OK`

만약 `test_run_calculation_produces_results_for_all_assigned_people`에서 `errors`가 비어있지 않다면(더미 데이터 조합이 실제 급여 엔진의 특정 검증에 걸리는 경우), 출력된 에러 메시지를 확인하고 `assert errors == []`를 실제 반환값에 맞게 조정한 뒤 원인을 `docs/superpowers/plans/`에 메모로 남긴다 — 이 단계는 실제 실행 결과로 확정한다.

- [ ] **Step 5: 커밋**

```bash
git add wage_calculator/webapp/state.py wage_calculator/tests/test_webapp_state_calculate.py
git commit -m "feat: AppState 계산 실행 확인정보/계산 실행 이관"
```

---

### Task 7: 결과 목록 / 산정근거 데이터

**Files:**
- Modify: `wage_calculator/webapp/state.py`
- Test: `wage_calculator/tests/test_webapp_state_results_evidence.py`

**Interfaces:**
- Consumes: `core.leave_engine.{leave_usage_minutes, leave_balance_minutes_as_of}`, `core.parser.person_key`
- Produces: `AppState.results_summary() -> list[dict]`, `AppState.evidence_names() -> list[dict]`(키: `key, label`), `AppState.evidence_for(key: str) -> dict | None`(키: `raw_rows, weekly, late_out, late_out_total_minutes, meal, leave, leave_final`)

- [ ] **Step 1: 실패하는 테스트 작성**

`wage_calculator/tests/test_webapp_state_results_evidence.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import Config
from webapp.state import AppState

FIXTURE_DIR = Path(__file__).resolve().parent.parent.parent / "demo_assets"
A_FILE = FIXTURE_DIR / "개인정보_예시(A).xlsx"
B_FILE = FIXTURE_DIR / "근무상황_예시(B).xlsx"


def _config_with_survey():
    return Config({
        "surveys": [{"name": "8월 정기조사", "start": "2026-08-01", "end": "2026-08-31"}],
        "rates": {"2026": {"daily_wage": 78560, "meal_allowance": 160000}},
        "holidays": ["2026-08-15"],
    })


def _calculated_state():
    state = AppState()
    state.config_obj = _config_with_survey()
    state.load_files(str(A_FILE), str(B_FILE))
    state.confirm_special_leave(["유급특별휴가"])
    keys = list(state.people.keys())
    state.batch_assign(keys, "8월 정기조사")
    state.prepare_calculation(2026, 8)
    state.run_calculation()
    return state


def test_results_summary_has_five_rows_with_expected_keys():
    state = _calculated_state()
    rows = state.results_summary()
    assert len(rows) == 5
    expected_keys = {"key", "label", "survey", "period", "total_days",
                      "weekly_holiday_days", "remaining_leave_days", "total_payment"}
    assert expected_keys <= rows[0].keys()
    print("OK: test_results_summary_has_five_rows_with_expected_keys")


def test_evidence_names_matches_results_count():
    state = _calculated_state()
    names = state.evidence_names()
    assert len(names) == 5
    assert {"key", "label"} <= names[0].keys()
    print("OK: test_evidence_names_matches_results_count")


def test_evidence_for_returns_none_for_unknown_key():
    state = _calculated_state()
    assert state.evidence_for("존재하지않음::19000101") is None
    print("OK: test_evidence_for_returns_none_for_unknown_key")


def test_evidence_for_known_person_has_all_sections():
    state = _calculated_state()
    key = state.evidence_names()[0]["key"]
    data = state.evidence_for(key)
    assert set(data.keys()) == {
        "raw_rows", "weekly", "late_out", "late_out_total_minutes",
        "meal", "leave", "leave_final",
    }
    assert isinstance(data["raw_rows"], list)
    assert "remaining_leave_days" in data["leave_final"]
    print("OK: test_evidence_for_known_person_has_all_sections")


if __name__ == "__main__":
    test_results_summary_has_five_rows_with_expected_keys()
    test_evidence_names_matches_results_count()
    test_evidence_for_returns_none_for_unknown_key()
    test_evidence_for_known_person_has_all_sections()
    print("ALL OK")
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python wage_calculator/tests/test_webapp_state_results_evidence.py`
Expected: `AttributeError: 'AppState' object has no attribute 'results_summary'`

- [ ] **Step 3: 구현**

`wage_calculator/webapp/state.py` 상단 import 블록에 추가(파일 맨 위, 기존 import들 뒤):

```python
from core import leave_engine
from core.leave_engine import leave_usage_minutes
from core.parser import person_key
```

`run_calculation` 메서드 뒤에 추가:

```python
    def results_summary(self):
        all_names = [r.name for r in self.results]
        out = []
        for r in self.results:
            out.append({
                "key": person_key(r.name, r.birth),
                "label": display_label(r.name, r.birth, all_names),
                "survey": r.survey_name,
                "period": f"{r.period_start.isoformat()}~{r.period_end.isoformat()}",
                "total_days": r.total_days,
                "weekly_holiday_days": r.weekly_holiday_days,
                "remaining_leave_days": round(r.remaining_leave_days, 2),
                "total_payment": r.total_payment,
            })
        return out

    def evidence_names(self):
        all_names = [r.name for r in self.results]
        return [
            {"key": person_key(r.name, r.birth), "label": display_label(r.name, r.birth, all_names)}
            for r in self.results
        ]

    def _result_by_key(self, key):
        for r in self.results:
            if person_key(r.name, r.birth) == key:
                return r
        return None

    def evidence_for(self, key):
        result = self._result_by_key(key)
        if result is None:
            return None

        raw_rows = []
        for row in self.giganje_rows:
            if row["성명"] != result.name:
                continue
            if str(row.get("생년월일") or "").strip() != result.birth:
                continue
            raw_rows.append({
                "category": row.get("종별") or "",
                "period": row.get("사용기간(날짜)") or "",
                "time": row.get("사용시간(시분)") or "",
                "reason": row.get("사유") or "",
                "note": row.get("비고") or "",
            })

        weekly = [{
            "index": w.index,
            "start": w.start.isoformat(),
            "effective_end": w.effective_end.isoformat(),
            "workdays": w.workdays,
            "absence_days": w.absence_days,
            "public_leave_days": w.public_leave_days,
            "sick_full_days": w.sick_full_days,
            "granted": w.granted,
            "reason": w.reason,
        } for w in result.weekly_windows]

        late_out = [{
            "date": e.d.isoformat(),
            "category": e.raw_category,
            "start": e.time_start.strftime("%H:%M"),
            "end": e.time_end.strftime("%H:%M"),
            "lunch_included": "포함" if (e.time_start < date_utils.LUNCH_START and e.time_end > date_utils.LUNCH_END) else "미포함",
            "minutes": e.minutes,
        } for e in result.late_out_events]

        total_days = (result.period_end - result.period_start).days + 1
        meal = {
            "period_start": result.period_start.isoformat(),
            "period_end": result.period_end.isoformat(),
            "total_days": total_days,
            "absence_days": result.absence_days,
            "meal_eligible_days": result.meal_eligible_days,
        }

        leave_rows = []
        for w in result.monthly_windows:
            if w.start > result.period_end:
                continue
            usage_text = ", ".join(
                f"{e.d.strftime('%m-%d')}:{leave_usage_minutes(e)}" for e in w.usage_events
            )
            concluded = w.effective_end <= result.period_end
            status = ("만근" if w.full_attendance else ("기간중 종료" if w.truncated else "미만근")) if concluded else "진행중"
            as_of = min(w.effective_end, result.period_end)
            balance_at_row = leave_engine.leave_balance_minutes_as_of(result.monthly_windows, as_of)
            leave_rows.append({
                "index": w.index,
                "start": w.start.isoformat(),
                "effective_end": w.effective_end.isoformat(),
                "status": status,
                "accrued": (1 if w.accrued else 0) if concluded else 0,
                "usage": usage_text,
                "balance_minutes": balance_at_row,
            })
        leave_final = {
            "remaining_leave_days": round(result.remaining_leave_days, 4),
            "remaining_leave_minutes": round(result.remaining_leave_days * 480),
        }

        return {
            "raw_rows": raw_rows,
            "weekly": weekly,
            "late_out": late_out,
            "late_out_total_minutes": result.late_out_minutes,
            "meal": meal,
            "leave": leave_rows,
            "leave_final": leave_final,
        }
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python wage_calculator/tests/test_webapp_state_results_evidence.py`
Expected: `ALL OK`

- [ ] **Step 5: 커밋**

```bash
git add wage_calculator/webapp/state.py wage_calculator/tests/test_webapp_state_results_evidence.py
git commit -m "feat: AppState 결과 목록/산정근거 데이터 이관"
```

---

### Task 8: 엑셀 다운로드

**Files:**
- Modify: `wage_calculator/webapp/state.py`
- Test: `wage_calculator/tests/test_webapp_state_download.py`

**Interfaces:**
- Consumes: `core.paths.downloads_dir`, `output.build.{build_workbook, build_departed_workbook, output_filename, departed_output_filename}`
- Produces: `AppState.download() -> list[str]`(저장된 파일 절대경로 목록)

- [ ] **Step 1: 실패하는 테스트 작성**

`wage_calculator/tests/test_webapp_state_download.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import Config
import webapp.state as state_module
from webapp.state import AppState

FIXTURE_DIR = Path(__file__).resolve().parent.parent.parent / "demo_assets"
A_FILE = FIXTURE_DIR / "개인정보_예시(A).xlsx"
B_FILE = FIXTURE_DIR / "근무상황_예시(B).xlsx"


def _config_with_survey():
    return Config({
        "surveys": [{"name": "8월 정기조사", "start": "2026-08-01", "end": "2026-08-31"}],
        "rates": {"2026": {"daily_wage": 78560, "meal_allowance": 160000}},
        "holidays": ["2026-08-15"],
    })


def _calculated_state():
    state = AppState()
    state.config_obj = _config_with_survey()
    state.load_files(str(A_FILE), str(B_FILE))
    state.confirm_special_leave(["유급특별휴가"])
    keys = list(state.people.keys())
    state.batch_assign(keys, "8월 정기조사")
    state.prepare_calculation(2026, 8)
    state.run_calculation()
    return state


def test_download_saves_workbook_to_configured_downloads_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(state_module, "downloads_dir", lambda: str(tmp_path))
    state = _calculated_state()

    saved = state.download()

    assert len(saved) == 1
    assert Path(saved[0]).exists()
    assert Path(saved[0]).parent == tmp_path
    print("OK: test_download_saves_workbook_to_configured_downloads_dir")


if __name__ == "__main__":
    print("이 테스트는 monkeypatch/tmp_path 픽스처가 필요해 pytest로만 실행합니다: pytest tests/test_webapp_state_download.py -v")
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest wage_calculator/tests/test_webapp_state_download.py -v`
Expected: `AttributeError: 'AppState' object has no attribute 'download'`

- [ ] **Step 3: 구현**

`wage_calculator/webapp/state.py` 상단 import 블록에 추가:

```python
from pathlib import Path

from core.paths import downloads_dir
from output.build import (
    build_departed_workbook,
    build_workbook,
    departed_output_filename,
    output_filename,
)
```

`evidence_for` 메서드(및 `_result_by_key`) 뒤에 추가:

```python
    def download(self):
        wb = build_workbook(
            self.results, self.config_obj,
            giganje_rows=self.giganje_rows,
            retro_adjustments=self.retro_adjustments,
            retro_details=self.retro_details,
        )
        filename = output_filename(self.work_year, self.work_month)
        path = Path(downloads_dir()) / filename
        wb.save(path)
        saved = [str(path)]

        if self.departed_results:
            departed_wb = build_departed_workbook(self.departed_results)
            departed_path = Path(downloads_dir()) / departed_output_filename(self.work_year, self.work_month)
            departed_wb.save(departed_path)
            saved.append(str(departed_path))
        return saved
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest wage_calculator/tests/test_webapp_state_download.py -v`
Expected: `1 passed`

- [ ] **Step 5: 커밋**

```bash
git add wage_calculator/webapp/state.py wage_calculator/tests/test_webapp_state_download.py
git commit -m "feat: AppState 엑셀 다운로드 이관"
```

---

### Task 9: 특별휴가 유급/무급 참고표 JSON 데이터

**Files:**
- Create: `wage_calculator/webapp/static/reference/leave_category_guide.json`
- Test: `wage_calculator/tests/test_webapp_reference_guide.py`

**Interfaces:**
- Produces: `leave_category_guide.json` — 최상위가 리스트인 JSON, 각 원소는 `{"category": str, "subtype": str, "detail": str, "description": str, "deduction": str, "time_entry": str, "note": str}` (해당 없는 필드는 빈 문자열)

**참고**: 원본 내용은 [`docs/superpowers/specs/reference/근무상황_종별_안내_전사.md`](../specs/reference/근무상황_종별_안내_전사.md)에 사용자가 검토·확인을 마친 상태다. 이 태스크는 그 내용을 기계가 읽을 수 있는 JSON으로 옮기는 작업이다.

- [ ] **Step 1: 실패하는 테스트 작성**

`wage_calculator/tests/test_webapp_reference_guide.py`:

```python
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

GUIDE_PATH = Path(__file__).resolve().parent.parent / "webapp" / "static" / "reference" / "leave_category_guide.json"


def test_guide_file_is_valid_json_list():
    data = json.loads(GUIDE_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert len(data) >= 40
    print("OK: test_guide_file_is_valid_json_list")


def test_guide_entries_have_required_keys():
    data = json.loads(GUIDE_PATH.read_text(encoding="utf-8"))
    required = {"category", "subtype", "detail", "description", "deduction", "time_entry", "note"}
    for entry in data:
        assert required <= entry.keys(), entry
    print("OK: test_guide_entries_have_required_keys")


def test_guide_includes_family_care_leave_note():
    data = json.loads(GUIDE_PATH.read_text(encoding="utf-8"))
    family_care = [e for e in data if e["subtype"] == "가족돌봄휴가"]
    assert len(family_care) == 1
    assert "유급" in family_care[0]["note"]
    print("OK: test_guide_includes_family_care_leave_note")


def test_guide_includes_special_leave_marking_context():
    data = json.loads(GUIDE_PATH.read_text(encoding="utf-8"))
    categories = {e["category"] for e in data}
    assert {"연가", "지각", "외출", "조퇴", "병가", "공가", "경조사휴가", "특별휴가", "결근", "기타"} <= categories
    print("OK: test_guide_includes_special_leave_marking_context")


if __name__ == "__main__":
    test_guide_file_is_valid_json_list()
    test_guide_entries_have_required_keys()
    test_guide_includes_family_care_leave_note()
    test_guide_includes_special_leave_marking_context()
    print("ALL OK")
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python wage_calculator/tests/test_webapp_reference_guide.py`
Expected: `FileNotFoundError`

- [ ] **Step 3: JSON 데이터 작성**

`wage_calculator/webapp/static/reference/leave_category_guide.json`:

```json
[
  {"category": "연가", "subtype": "", "detail": "", "description": "연가 사용일수 한도 안에서 신청할 수 있음", "deduction": "공제", "time_entry": "불가능", "note": ""},
  {"category": "연가", "subtype": "반일연가", "detail": "오전", "description": "오전 연가로 사용시간이 09:00~14:00로 고정되어 있음", "deduction": "공제", "time_entry": "불가능", "note": ""},
  {"category": "연가", "subtype": "반일연가", "detail": "오후", "description": "오후 연가로 사용시간이 14:00~18:00로 고정되어 있음", "deduction": "공제", "time_entry": "불가능", "note": ""},
  {"category": "지각", "subtype": "연가처리", "detail": "", "description": "근무장소에 근무시작 시간 이후에 출근하는 것", "deduction": "공제", "time_entry": "가능", "note": ""},
  {"category": "지각", "subtype": "일반병가,진단서미첨부", "detail": "", "description": "누계시간으로 계산하여 누계 8시간을 병가 1일로 처리", "deduction": "미공제", "time_entry": "가능", "note": ""},
  {"category": "지각", "subtype": "일반병가,진단서첨부", "detail": "", "description": "누계시간으로 계산하여 누계 8시간을 병가 1일로 처리", "deduction": "미공제", "time_entry": "가능", "note": ""},
  {"category": "지각", "subtype": "공무상병가", "detail": "", "description": "누계시간으로 계산하여 누계 8시간을 병가 1일로 처리", "deduction": "미공제", "time_entry": "가능", "note": ""},
  {"category": "외출", "subtype": "연가처리", "detail": "", "description": "근무시간 중 개인용무를 위하여 청사 외부로 나간 후, 근무종료 시간 이전에 돌아오는 것", "deduction": "공제", "time_entry": "가능", "note": ""},
  {"category": "외출", "subtype": "일반병가,진단서미첨부", "detail": "", "description": "누계시간으로 계산하여 누계 8시간을 병가 1일로 처리", "deduction": "미공제", "time_entry": "가능", "note": ""},
  {"category": "외출", "subtype": "일반병가,진단서첨부", "detail": "", "description": "누계시간으로 계산하여 누계 8시간을 병가 1일로 처리", "deduction": "미공제", "time_entry": "가능", "note": ""},
  {"category": "외출", "subtype": "공무상병가", "detail": "", "description": "누계시간으로 계산하여 누계 8시간을 병가 1일로 처리", "deduction": "미공제", "time_entry": "가능", "note": ""},
  {"category": "조퇴", "subtype": "연가처리", "detail": "", "description": "근무종료 시간 이전에 퇴근하는 것", "deduction": "공제", "time_entry": "가능", "note": ""},
  {"category": "조퇴", "subtype": "일반병가,진단서미첨부", "detail": "", "description": "누계시간으로 계산하여 누계 8시간을 병가 1일로 처리", "deduction": "미공제", "time_entry": "가능", "note": ""},
  {"category": "조퇴", "subtype": "일반병가,진단서첨부", "detail": "", "description": "누계시간으로 계산하여 누계 8시간을 병가 1일로 처리", "deduction": "미공제", "time_entry": "가능", "note": ""},
  {"category": "조퇴", "subtype": "공무상병가", "detail": "", "description": "누계시간으로 계산하여 누계 8시간을 병가 1일로 처리", "deduction": "미공제", "time_entry": "가능", "note": ""},
  {"category": "병가", "subtype": "일반병가(진단서미첨부)", "detail": "", "description": "연 60일의 범위 안에서 허가하며 병가일수가 연간 6일을 초과하는 경우 7일 이후의 병가는 연가를 활용하여야 함", "deduction": "6일 초과할 경우 공제", "time_entry": "불가능", "note": ""},
  {"category": "병가", "subtype": "일반병가(진단서첨부)", "detail": "", "description": "연 60일의 범위 안에서 허가하며 병가일수가 연간 6일을 초과하여도 연가일수에서 공제하지 않음", "deduction": "미공제", "time_entry": "불가능", "note": ""},
  {"category": "병가", "subtype": "공무상병가", "detail": "", "description": "공무상 질병 또는 부상으로 직무를 수행할 수 없거나 요양을 요할 경우에는 연간 180일의 범위 안에서 공무상 요양승인을 받아 허가", "deduction": "미공제", "time_entry": "불가능", "note": ""},
  {"category": "공가", "subtype": "", "detail": "", "description": "1.병역판정검사·소집·검열점호 등 응하거나 훈련 참가 2.국회·법원·검찰·경찰 등 국가기관에 소환 3.투표 참가 4.승진시험·전직시험 응시 5.원격지간 전보 시 이사 등 최소 일수 6.소속기관 이전으로 거주지 변경 7.건강진단·건강검진·결핵검진 8.헌혈 참가 9.외국어능력시험 응시 10.올림픽·전국체전 등 국가행사 참가 11.천재지변·교통차단 등으로 출근 불가능 12.공무원노동조합 교섭위원·대의원회 참석 13.공무국외출장 전 검역감염병 예방접종 14.제1급감염병 예방접종/검사 * 직접 필요한 시간만큼 신청", "deduction": "미공제", "time_entry": "가능", "note": ""},
  {"category": "경조사휴가", "subtype": "결혼", "detail": "본인", "description": "5일의 범위안에서 허가", "deduction": "미공제", "time_entry": "불가능", "note": ""},
  {"category": "경조사휴가", "subtype": "결혼", "detail": "자녀", "description": "1일의 범위안에서 허가", "deduction": "미공제", "time_entry": "불가능", "note": ""},
  {"category": "경조사휴가", "subtype": "배우자출산", "detail": "", "description": "20일의 범위안에서 허가(한번에 둘 이상의 자녀를 출산한 경우 25일)", "deduction": "미공제", "time_entry": "불가능", "note": ""},
  {"category": "경조사휴가", "subtype": "사망", "detail": "배우자, 본인 및 배우자의 부모", "description": "5일의 범위안에서 허가", "deduction": "미공제", "time_entry": "불가능", "note": ""},
  {"category": "경조사휴가", "subtype": "사망", "detail": "본인 및 배우자의 조부모·외조부모", "description": "3일의 범위안에서 허가", "deduction": "미공제", "time_entry": "불가능", "note": ""},
  {"category": "경조사휴가", "subtype": "사망", "detail": "자녀와 그 자녀의 배우자", "description": "3일의 범위안에서 허가", "deduction": "미공제", "time_entry": "불가능", "note": ""},
  {"category": "경조사휴가", "subtype": "사망", "detail": "본인 및 배우자의 형제·자매", "description": "3일의 범위안에서 허가", "deduction": "미공제", "time_entry": "불가능", "note": ""},
  {"category": "경조사휴가", "subtype": "입양", "detail": "", "description": "20일의 범위안에서 허가", "deduction": "미공제", "time_entry": "불가능", "note": ""},
  {"category": "특별휴가", "subtype": "출산휴가(본인출산)", "detail": "", "description": "1.임신 중 여자공무원은 출산 전후 90일(다태아 120일, 미숙아 출산 1일 이내 신생아중환자실 입원 시 100일). 2.출산 후 휴가기간이 45일(다태아 60일) 이상이어야 함. 예외적 사유 시 출산 전 최장 44일(다태아 59일) 범위에서 나누어 사용 가능", "deduction": "미공제", "time_entry": "불가능", "note": ""},
  {"category": "특별휴가", "subtype": "유·사산휴가", "detail": "", "description": "1.임신 15주 이내 유산·사산: 10일까지 2.16~21주: 30일까지 3.22~27주: 60일까지 4.28주 이상: 90일까지 5.배우자 유산·사산 시 상기 기간 내 3일", "deduction": "미공제", "time_entry": "불가능", "note": ""},
  {"category": "특별휴가", "subtype": "포상휴가", "detail": "", "description": "국가 또는 해당 기관의 주요 업무를 성공적으로 수행하여 탁월한 성과와 공로가 인정되는 경우, 10일 이내", "deduction": "미공제", "time_entry": "불가능", "note": ""},
  {"category": "특별휴가", "subtype": "가족돌봄휴가", "detail": "", "description": "[자녀,손자녀] 어린이집/유치원/학교 휴업·휴원·휴교 등으로 돌봄 필요, 공식행사·상담 참여, 진료 동행 등. [그 외 가족] 질병·사고·노령 등. [사용일수] 유급 포함 연간 10일 범위, 무급 원칙, 자녀 돌봄 시 자녀 수+1일 범위에서 유급 가능(장애인/한부모 연 1일 가산)", "deduction": "미공제", "time_entry": "", "note": "원본 표기: * 유급: 가능 / * 무급: 불가능 (다른 항목과 달리 이 행만 사용시간입력란 자리에 유급/무급 표기가 들어감)"},
  {"category": "특별휴가", "subtype": "임신검진휴가", "detail": "", "description": "임신한 여성공무원의 경우 검진을 위하여 임신기간 중 최대 10일의 유급휴가를 사용할 수 있음", "deduction": "미공제", "time_entry": "불가능", "note": ""},
  {"category": "특별휴가", "subtype": "임신검진 동행휴가", "detail": "", "description": "남성공무원은 배우자의 임신기간 중 검진에 동행하기 위해 최대 10일의 유급휴가를 사용할 수 있음", "deduction": "미공제", "time_entry": "불가능", "note": ""},
  {"category": "특별휴가", "subtype": "심리안정휴가", "detail": "", "description": "위험직무 수행 중 인명피해가 발생한 사건·사고로 심리적 안정과 정신적 회복 필요 시, 4일 이내", "deduction": "미공제", "time_entry": "가능", "note": ""},
  {"category": "특별휴가", "subtype": "장기재직휴가", "detail": "", "description": "재직기간 10년 이상 공무원: 1.5년이상10년미만 3일 2.10년이상20년미만 5일 3.20년이상 7일", "deduction": "미공제", "time_entry": "불가능", "note": ""},
  {"category": "특별휴가", "subtype": "대체휴무", "detail": "", "description": "복무규정 제11조 제1항에 따라 시간외근무 및 토요일 또는 공휴일에 근무를 한 공무원에 대하여 그 다음 정상근무일을 휴무하게 할 수 있음. 연가일수 공제·연가보상비 계산에 반영하지 않음", "deduction": "미공제", "time_entry": "불가능", "note": ""},
  {"category": "특별휴가", "subtype": "당직휴무", "detail": "", "description": "당직근무자에 대하여 그 근무종료시각이 속하는 날의 일정 시간(전부 휴무 포함)을 정하여 휴무하게 할 수 있음", "deduction": "미공제", "time_entry": "가능", "note": ""},
  {"category": "특별휴가", "subtype": "선거휴무", "detail": "", "description": "선거 관련 사무를 수행한 공무원에 대하여 해당 선거일(사전투표일 포함) 다음 정상근무일을 휴무하게 해야 하며, 선거일이 토요일 또는 공휴일인 경우 1일을 더하여 부여", "deduction": "미공제", "time_entry": "불가능", "note": ""},
  {"category": "특별휴가", "subtype": "난임치료시술", "detail": "", "description": "여성공무원: 인공수정 총2일 / 동결배아 이식 총3일 / 난자채취 후 체외수정 총4일. 남성공무원: 정자채취일 1일", "deduction": "미공제", "time_entry": "불가능", "note": ""},
  {"category": "특별휴가", "subtype": "여성보건휴가", "detail": "무급", "description": "여성공무원의 경우 생리로 인한 보건휴가를 사용할 경우 무급임('06.1.1.부터 시행)", "deduction": "미공제", "time_entry": "불가능", "note": ""},
  {"category": "특별휴가", "subtype": "모성보호시간", "detail": "", "description": "임신 중인 여성공무원은 4시간을 초과하여 근무하는 날에 1일 2시간의 범위에서 휴식이나 병원 진료 등을 위해 사용 가능(임신 12주 이내 또는 32주 이후 신청 시 승인)", "deduction": "미공제", "time_entry": "가능", "note": ""},
  {"category": "특별휴가", "subtype": "육아시간", "detail": "", "description": "만 8세 이하 또는 초등학교 2학년 이하 자녀에 대해 36개월 범위에서 1일 2시간 사용 가능. 유효기간 종료일자 지정 및 재학증명서 첨부 필요", "deduction": "미공제", "time_entry": "불가능", "note": ""},
  {"category": "특별휴가", "subtype": "수업휴가", "detail": "", "description": "한국방송통신대학교 재학 공무원이 출석 수업 참석을 위하여 연가일수를 초과하는 출석 수업기간에 대해 사용", "deduction": "미공제", "time_entry": "불가능", "note": ""},
  {"category": "특별휴가", "subtype": "재해구호휴가", "detail": "", "description": "재난 또는 피해를 입은 공무원과 재난발생지역 자원봉사 공무원은 5일(대규모 재난으로 장기 피해수습 필요 인정 시 10일) 이내", "deduction": "미공제", "time_entry": "가능", "note": ""},
  {"category": "결근", "subtype": "", "detail": "", "description": "출장, 휴가 등의 정당한 사유 없이 근무종료 시간까지 출근하지 아니하는 것", "deduction": "공제", "time_entry": "불가능", "note": ""},
  {"category": "기타", "subtype": "관외여행", "detail": "", "description": "관외여행을 신청하는 경우", "deduction": "미공제", "time_entry": "가능", "note": ""},
  {"category": "기타", "subtype": "기타", "detail": "", "description": "해당하는 근무상황 명칭이 없는 경우 사용", "deduction": "미공제", "time_entry": "가능", "note": ""}
]
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python wage_calculator/tests/test_webapp_reference_guide.py`
Expected: `ALL OK`

- [ ] **Step 5: 커밋**

```bash
git add wage_calculator/webapp/static/reference/leave_category_guide.json wage_calculator/tests/test_webapp_reference_guide.py
git commit -m "feat: 특별휴가 참고표 JSON 데이터 추가"
```

---

### Task 10: FastAPI `create_app()` — 업로드/특별휴가/대상자 라우트

**Files:**
- Create: `wage_calculator/webapp/server.py`
- Test: `wage_calculator/tests/test_webapp_server_upload_flow.py`

**Interfaces:**
- Consumes: `webapp.state.AppState`
- Produces: `create_app(state: AppState | None = None) -> fastapi.FastAPI`. 라우트: `POST /api/upload`, `GET /api/special-leave`, `POST /api/special-leave/confirm`, `GET /api/targets`, `POST /api/targets/batch-assign`, `POST /api/targets/contract-edit`, `POST /api/targets/proceed`. 에러는 `HTTPException(400, detail=str(e))` → 응답 바디 `{"detail": "..."}`.

- [ ] **Step 1: 실패하는 테스트 작성**

`wage_calculator/tests/test_webapp_server_upload_flow.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from core.config import Config
from webapp.server import create_app
from webapp.state import AppState

FIXTURE_DIR = Path(__file__).resolve().parent.parent.parent / "demo_assets"
A_FILE = FIXTURE_DIR / "개인정보_예시(A).xlsx"
B_FILE = FIXTURE_DIR / "근무상황_예시(B).xlsx"


def _client():
    state = AppState()
    state.config_obj = Config({
        "surveys": [{"name": "8월 정기조사", "start": "2026-08-01", "end": "2026-08-31"}],
        "rates": {"2026": {"daily_wage": 78560, "meal_allowance": 160000}},
        "holidays": ["2026-08-15"],
    })
    app = create_app(state)
    return TestClient(app), state


def test_upload_route_returns_pending_special_leave_flag():
    client, _ = _client()
    resp = client.post("/api/upload", json={"a_path": str(A_FILE), "b_path": str(B_FILE)})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ambiguous_names"] == []
    assert body["has_pending_special_leave"] is True
    print("OK: test_upload_route_returns_pending_special_leave_flag")


def test_upload_route_returns_400_on_missing_file():
    client, _ = _client()
    resp = client.post("/api/upload", json={"a_path": "존재하지않는파일.xlsx", "b_path": str(B_FILE)})
    assert resp.status_code == 400
    print("OK: test_upload_route_returns_400_on_missing_file")


def test_special_leave_flow_then_targets_flow():
    client, _ = _client()
    client.post("/api/upload", json={"a_path": str(A_FILE), "b_path": str(B_FILE)})

    groups_resp = client.get("/api/special-leave")
    assert groups_resp.status_code == 200
    groups = groups_resp.json()["groups"]
    assert len(groups) == 1

    confirm_resp = client.post("/api/special-leave/confirm", json={"statuses": ["유급특별휴가"]})
    assert confirm_resp.status_code == 200, confirm_resp.text

    targets_resp = client.get("/api/targets")
    assert targets_resp.status_code == 200
    targets_body = targets_resp.json()
    assert len(targets_body["targets"]) == 5
    assert targets_body["survey_names"] == ["8월 정기조사"]

    keys = [t["key"] for t in targets_body["targets"]]
    assign_resp = client.post("/api/targets/batch-assign", json={"keys": keys, "survey_name": "8월 정기조사"})
    assert assign_resp.status_code == 200, assign_resp.text
    assert all(t["survey_name"] == "8월 정기조사" for t in assign_resp.json()["targets"])

    edit_resp = client.post("/api/targets/contract-edit", json={"key": keys[0], "start": "2026-08-02", "end": "2026-08-25"})
    assert edit_resp.status_code == 200, edit_resp.text

    proceed_resp = client.post("/api/targets/proceed", json={"year": 2026, "month": 8})
    assert proceed_resp.status_code == 200, proceed_resp.text
    assert proceed_resp.json()["unassigned_names"] == []
    print("OK: test_special_leave_flow_then_targets_flow")


if __name__ == "__main__":
    test_upload_route_returns_pending_special_leave_flag()
    test_upload_route_returns_400_on_missing_file()
    test_special_leave_flow_then_targets_flow()
    print("ALL OK")
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python wage_calculator/tests/test_webapp_server_upload_flow.py`
Expected: `ModuleNotFoundError: No module named 'webapp.server'`

- [ ] **Step 3: `server.py` 구현**

`wage_calculator/webapp/server.py`:

```python
"""AppState를 감싸는 JSON API. 화면(프론트엔드)은 다음 계획에서 이 라우트를 호출한다."""
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .state import AppState


class UploadRequest(BaseModel):
    a_path: str
    b_path: str
    prev_path: Optional[str] = None


class SpecialLeaveConfirmRequest(BaseModel):
    statuses: List[str]


class BatchAssignRequest(BaseModel):
    keys: List[str]
    survey_name: str


class ContractEditRequest(BaseModel):
    key: str
    start: str
    end: str


class ProceedRequest(BaseModel):
    year: int
    month: int


def create_app(state: Optional[AppState] = None) -> FastAPI:
    if state is None:
        state = AppState()

    app = FastAPI()

    @app.post("/api/upload")
    def upload(req: UploadRequest):
        try:
            return state.load_files(req.a_path, req.b_path, req.prev_path)
        except (ValueError, FileNotFoundError, OSError) as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.get("/api/special-leave")
    def get_special_leave():
        return {"groups": state.special_leave_groups()}

    @app.post("/api/special-leave/confirm")
    def confirm_special_leave(req: SpecialLeaveConfirmRequest):
        try:
            state.confirm_special_leave(req.statuses)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return {"ok": True}

    @app.get("/api/targets")
    def get_targets():
        return {"targets": state.targets(), "survey_names": state.survey_names()}

    @app.post("/api/targets/batch-assign")
    def batch_assign(req: BatchAssignRequest):
        try:
            state.batch_assign(req.keys, req.survey_name)
        except (ValueError, KeyError) as e:
            raise HTTPException(status_code=400, detail=str(e))
        return {"targets": state.targets()}

    @app.post("/api/targets/contract-edit")
    def contract_edit(req: ContractEditRequest):
        try:
            state.edit_contract(req.key, req.start, req.end)
        except (ValueError, KeyError) as e:
            raise HTTPException(status_code=400, detail=str(e))
        return {"targets": state.targets()}

    @app.post("/api/targets/proceed")
    def proceed(req: ProceedRequest):
        try:
            unassigned = state.prepare_calculation(req.year, req.month)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return {"unassigned_names": unassigned}

    return app
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python wage_calculator/tests/test_webapp_server_upload_flow.py`
Expected: `ALL OK`

- [ ] **Step 5: 커밋**

```bash
git add wage_calculator/webapp/server.py wage_calculator/tests/test_webapp_server_upload_flow.py
git commit -m "feat: FastAPI 업로드/특별휴가/대상자 라우트 추가"
```

---

### Task 11: FastAPI — 계산 실행/결과/다운로드/산정근거 라우트

**Files:**
- Modify: `wage_calculator/webapp/server.py`
- Test: `wage_calculator/tests/test_webapp_server_calculate_flow.py`

**Interfaces:**
- Produces 라우트: `GET /api/confirm-info`, `POST /api/calculate`, `GET /api/results`, `POST /api/download`, `GET /api/evidence?key=`

- [ ] **Step 1: 실패하는 테스트 작성**

`wage_calculator/tests/test_webapp_server_calculate_flow.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from core.config import Config
import webapp.state as state_module
from webapp.server import create_app
from webapp.state import AppState

FIXTURE_DIR = Path(__file__).resolve().parent.parent.parent / "demo_assets"
A_FILE = FIXTURE_DIR / "개인정보_예시(A).xlsx"
B_FILE = FIXTURE_DIR / "근무상황_예시(B).xlsx"


def _ready_client(tmp_path, monkeypatch):
    monkeypatch.setattr(state_module, "downloads_dir", lambda: str(tmp_path))
    state = AppState()
    state.config_obj = Config({
        "surveys": [{"name": "8월 정기조사", "start": "2026-08-01", "end": "2026-08-31"}],
        "rates": {"2026": {"daily_wage": 78560, "meal_allowance": 160000}},
        "holidays": ["2026-08-15"],
    })
    app = create_app(state)
    client = TestClient(app)

    client.post("/api/upload", json={"a_path": str(A_FILE), "b_path": str(B_FILE)})
    client.post("/api/special-leave/confirm", json={"statuses": ["유급특별휴가"]})
    keys = [t["key"] for t in client.get("/api/targets").json()["targets"]]
    client.post("/api/targets/batch-assign", json={"keys": keys, "survey_name": "8월 정기조사"})
    client.post("/api/targets/proceed", json={"year": 2026, "month": 8})
    return client


def test_confirm_info_then_calculate_then_results(tmp_path, monkeypatch):
    client = _ready_client(tmp_path, monkeypatch)

    info_resp = client.get("/api/confirm-info")
    assert info_resp.status_code == 200
    assert info_resp.json()["holidays"] == ["2026-08-15"]

    calc_resp = client.post("/api/calculate")
    assert calc_resp.status_code == 200, calc_resp.text
    assert calc_resp.json()["errors"] == []

    results_resp = client.get("/api/results")
    assert results_resp.status_code == 200
    assert len(results_resp.json()["results"]) == 5
    print("OK: test_confirm_info_then_calculate_then_results")


def test_download_returns_saved_paths(tmp_path, monkeypatch):
    client = _ready_client(tmp_path, monkeypatch)
    client.post("/api/calculate")

    download_resp = client.post("/api/download")
    assert download_resp.status_code == 200, download_resp.text
    saved = download_resp.json()["saved_paths"]
    assert len(saved) == 1
    assert Path(saved[0]).exists()
    print("OK: test_download_returns_saved_paths")


def test_evidence_route_returns_sections_for_first_result(tmp_path, monkeypatch):
    client = _ready_client(tmp_path, monkeypatch)
    client.post("/api/calculate")
    results = client.get("/api/results").json()["results"]
    key = results[0]["key"]

    evidence_resp = client.get(f"/api/evidence?key={key}")
    assert evidence_resp.status_code == 200, evidence_resp.text
    body = evidence_resp.json()
    assert "weekly" in body and "leave" in body
    print("OK: test_evidence_route_returns_sections_for_first_result")


def test_evidence_route_returns_404_for_unknown_key(tmp_path, monkeypatch):
    client = _ready_client(tmp_path, monkeypatch)
    client.post("/api/calculate")

    resp = client.get("/api/evidence?key=없음::19000101")
    assert resp.status_code == 404
    print("OK: test_evidence_route_returns_404_for_unknown_key")
```

이 파일은 `tmp_path`/`monkeypatch` 픽스처가 필요해 pytest 전용이다(`if __name__ == "__main__":` 블록 없음).

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest wage_calculator/tests/test_webapp_server_calculate_flow.py -v`
Expected: `404 Not Found`(라우트가 없어 전부 실패)

- [ ] **Step 3: 라우트 추가**

`wage_calculator/webapp/server.py`의 `return app` 바로 앞에 추가:

```python
    @app.get("/api/confirm-info")
    def confirm_info():
        try:
            return state.confirm_info()
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/api/calculate")
    def calculate():
        errors = state.run_calculation()
        return {"errors": errors}

    @app.get("/api/results")
    def get_results():
        return {"results": state.results_summary()}

    @app.post("/api/download")
    def download():
        try:
            saved = state.download()
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return {"saved_paths": saved}

    @app.get("/api/evidence")
    def get_evidence(key: str):
        data = state.evidence_for(key)
        if data is None:
            raise HTTPException(status_code=404, detail="해당 대상자의 결과를 찾을 수 없습니다.")
        return {"names": state.evidence_names(), **data}
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest wage_calculator/tests/test_webapp_server_calculate_flow.py -v`
Expected: `4 passed`

- [ ] **Step 5: 커밋**

```bash
git add wage_calculator/webapp/server.py wage_calculator/tests/test_webapp_server_calculate_flow.py
git commit -m "feat: FastAPI 계산실행/결과/다운로드/산정근거 라우트 추가"
```

---

### Task 12: FastAPI — 설정(조사종류/요율/공휴일) 라우트 + 참고표 라우트

**Files:**
- Modify: `wage_calculator/webapp/server.py`
- Test: `wage_calculator/tests/test_webapp_server_settings_reference.py`

**Interfaces:**
- Produces 라우트: `GET /api/settings`, `POST /api/settings/survey`, `DELETE /api/settings/survey/{name}`, `POST /api/settings/rate`, `DELETE /api/settings/rate/{year}`, `POST /api/settings/holiday`, `DELETE /api/settings/holiday/{date}`, `GET /api/reference/leave-guide`

- [ ] **Step 1: 실패하는 테스트 작성**

`wage_calculator/tests/test_webapp_server_settings_reference.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from core.config import Config
from webapp.server import create_app
from webapp.state import AppState


def _client():
    state = AppState()
    state.config_obj = Config({"surveys": [], "rates": {}, "holidays": []})
    app = create_app(state)
    return TestClient(app), state


def test_settings_survey_crud():
    client, state = _client()
    add_resp = client.post("/api/settings/survey", json={"name": "9월 조사", "start": "2026-09-01", "end": "2026-09-30"})
    assert add_resp.status_code == 200, add_resp.text
    assert state.config_obj.survey_names() == ["9월 조사"]

    del_resp = client.delete("/api/settings/survey/9월 조사")
    assert del_resp.status_code == 200, del_resp.text
    assert state.config_obj.survey_names() == []
    print("OK: test_settings_survey_crud")


def test_settings_rate_crud():
    client, state = _client()
    add_resp = client.post("/api/settings/rate", json={"year": 2026, "daily_wage": 78560, "meal_allowance": 160000})
    assert add_resp.status_code == 200, add_resp.text
    assert state.config_obj.daily_wage_for(2026) == 78560

    del_resp = client.delete("/api/settings/rate/2026")
    assert del_resp.status_code == 200, del_resp.text
    assert state.config_obj.rate_years() == []
    print("OK: test_settings_rate_crud")


def test_settings_holiday_crud():
    client, state = _client()
    add_resp = client.post("/api/settings/holiday", json={"date": "2026-08-15"})
    assert add_resp.status_code == 200, add_resp.text
    assert state.config_obj.holidays == ["2026-08-15"]

    del_resp = client.delete("/api/settings/holiday/2026-08-15")
    assert del_resp.status_code == 200, del_resp.text
    assert state.config_obj.holidays == []
    print("OK: test_settings_holiday_crud")


def test_get_settings_returns_all_three_lists():
    client, state = _client()
    client.post("/api/settings/survey", json={"name": "9월 조사", "start": "2026-09-01", "end": "2026-09-30"})
    client.post("/api/settings/rate", json={"year": 2026, "daily_wage": 78560, "meal_allowance": 160000})
    client.post("/api/settings/holiday", json={"date": "2026-08-15"})

    resp = client.get("/api/settings")
    assert resp.status_code == 200
    body = resp.json()
    assert body["surveys"] == [{"name": "9월 조사", "start": "2026-09-01", "end": "2026-09-30"}]
    assert body["rates"] == {"2026": {"daily_wage": 78560, "meal_allowance": 160000}}
    assert body["holidays"] == ["2026-08-15"]
    print("OK: test_get_settings_returns_all_three_lists")


def test_reference_leave_guide_route_returns_full_list():
    client, _ = _client()
    resp = client.get("/api/reference/leave-guide")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["entries"]) >= 40
    print("OK: test_reference_leave_guide_route_returns_full_list")


if __name__ == "__main__":
    test_settings_survey_crud()
    test_settings_rate_crud()
    test_settings_holiday_crud()
    test_get_settings_returns_all_three_lists()
    test_reference_leave_guide_route_returns_full_list()
    print("ALL OK")
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python wage_calculator/tests/test_webapp_server_settings_reference.py`
Expected: `404 Not Found`

- [ ] **Step 3: 라우트 추가**

`wage_calculator/webapp/server.py` 상단에 추가:

```python
import json
from pathlib import Path
```

새 요청 모델 3개를 기존 pydantic 모델들 뒤에 추가:

```python
class SurveyRequest(BaseModel):
    name: str
    start: str
    end: str


class RateRequest(BaseModel):
    year: int
    daily_wage: int
    meal_allowance: int


class HolidayRequest(BaseModel):
    date: str
```

`create_app()` 함수 안, `return app` 바로 앞에 추가:

```python
    @app.get("/api/settings")
    def get_settings():
        return state.config_obj.to_dict()

    @app.post("/api/settings/survey")
    def add_survey(req: SurveyRequest):
        state.config_obj.add_or_update_survey(req.name, req.start, req.end)
        state.config_obj.save()
        return state.config_obj.to_dict()

    @app.delete("/api/settings/survey/{name}")
    def delete_survey(name: str):
        state.config_obj.delete_survey(name)
        state.config_obj.save()
        return state.config_obj.to_dict()

    @app.post("/api/settings/rate")
    def add_rate(req: RateRequest):
        state.config_obj.set_year_rates(req.year, req.daily_wage, req.meal_allowance)
        state.config_obj.save()
        return state.config_obj.to_dict()

    @app.delete("/api/settings/rate/{year}")
    def delete_rate(year: int):
        state.config_obj.delete_year_rates(year)
        state.config_obj.save()
        return state.config_obj.to_dict()

    @app.post("/api/settings/holiday")
    def add_holiday(req: HolidayRequest):
        try:
            state.config_obj.add_holiday(req.date)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        state.config_obj.save()
        return state.config_obj.to_dict()

    @app.delete("/api/settings/holiday/{date}")
    def delete_holiday(date: str):
        state.config_obj.remove_holiday(date)
        state.config_obj.save()
        return state.config_obj.to_dict()

    @app.get("/api/reference/leave-guide")
    def get_leave_guide():
        guide_path = Path(__file__).resolve().parent / "static" / "reference" / "leave_category_guide.json"
        entries = json.loads(guide_path.read_text(encoding="utf-8"))
        return {"entries": entries}
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python wage_calculator/tests/test_webapp_server_settings_reference.py`
Expected: `ALL OK`

- [ ] **Step 5: 커밋**

```bash
git add wage_calculator/webapp/server.py wage_calculator/tests/test_webapp_server_settings_reference.py
git commit -m "feat: FastAPI 설정 CRUD/참고표 라우트 추가"
```

---

## 완료 후 전체 회귀 확인

- [ ] **Step 1: 기존 core/output 테스트가 전부 그대로 통과하는지 확인**

Run: `python -m pytest wage_calculator/tests/ -v`
Expected: 새로 추가한 테스트 포함 전부 `passed`(기존 `test_payroll_*.py`, `test_build_workbook_integration.py` 등은 이번 작업으로 코드가 바뀌지 않았으므로 그대로 통과해야 함)

- [ ] **Step 2: 커밋**

이 단계는 코드 변경이 없으므로 커밋하지 않는다. 회귀 실패가 있으면 원인이 된 태스크로 돌아가 수정하고 해당 태스크 커밋을 새로 만든다.
