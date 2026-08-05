# 소급계산 + 지급내역 수식 근거 시트 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 전월 임금내역 파일을 함께 업로드받아 전월분을 재계산하고, 실제 지급된 금액과 비교한 차액(환수/추가지급)을 당월 급여에 반영한다. 아울러 지급내역(금액) 계산 과정을 실제 엑셀 수식으로 재현하는 검증용 시트를 추가한다.

**Architecture:** `core/config.py`를 연도별 요율 구조로 바꾸고, 신규 `core/retroactive.py`가 당월 로스터·전월 파일·당월 B파일 원본을 조합해 소급조정액을 계산한다. 출력 계층(`output/`)에 값 그대로 쓰는 기존 "임금내역" 시트는 유지하고, 수식으로 같은 계산을 재현하는 "산정근거(수식)" 시트와 완전퇴사자 전용 워크북을 새로 추가한다. GUI는 업로드 화면에 3번째 파일 입력을 추가하고 결과화면 다운로드가 파일을 1~2개 저장하도록 확장한다.

**Tech Stack:** Python 3, tkinter, openpyxl. 테스트는 pytest 없이 순수 `assert` + `if __name__ == "__main__"` 스크립트(`python tests/test_x.py`로 개별 실행) — 이 저장소의 기존 관례를 그대로 따른다.

## Global Constraints

- 설계 문서: [`docs/superpowers/specs/2026-08-05-matching-navigation-retroactive-design.md`](../specs/2026-08-05-matching-navigation-retroactive-design.md) §5~§6
- 절삭(내림) 로직은 4곳(조퇴외출공제/기본급/정액급식비/지급총액, 모두 10원 단위) 그대로 유지한다. 이 플랜에서 `payroll.py`의 계산식 자체는 바꾸지 않는다(요율 조회 방식만 연도별로 바뀜).
- 이 플랜은 [`2026-08-05-matching-navigation-contract-confirm.md`](2026-08-05-matching-navigation-contract-confirm.md) Task 1(직급 필터 제거) 완료를 전제로 한다 — Task 7(완전퇴사자 매칭)이 그 결과(직급 필터 없는 `giganje_rows`)를 사용한다. 먼저 그 플랜을 완료할 것.
- 기존 테스트(`tests/test_end_to_end_v3.py`, `tests/test_payroll_special_leave.py`, `tests/test_wage_sheet_special_leave.py`)는 `Config({"common": {...}})` 형태로 설정을 만드는데, 이 플랜 Task 1에서 스키마가 바뀌므로 함께 수정한다.

---

### Task 1: `config.py` 연도별 요율 구조로 변경 + 기존 테스트 fixture 갱신

**Files:**
- Modify: `wage_calculator/core/config.py`
- Modify: `wage_calculator/tests/test_end_to_end_v3.py:50`
- Modify: `wage_calculator/tests/test_payroll_special_leave.py:14`
- Modify: `wage_calculator/tests/test_wage_sheet_special_leave.py:31`
- Modify: `wage_calculator/tests/manual_check.py:32-33`
- Test: `wage_calculator/tests/test_config_yearly_rates.py` (create)

**Interfaces:**
- Produces: `Config.hourly_wage_for(year:int)->int`, `Config.meal_allowance_for(year:int)->int`, `Config.set_year_rates(year:int, hourly_wage:int, meal_allowance:int)`, `Config.delete_year_rates(year:int)`, `Config.rate_years()->list[int]`. 기존 `Config.hourly_wage`/`Config.meal_allowance` 프로퍼티는 삭제됨(연도 없이는 조회 불가).

- [ ] **Step 1: 실패하는 테스트 작성**

`wage_calculator/tests/test_config_yearly_rates.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import Config


def test_set_and_get_year_rates():
    config = Config({"surveys": [], "rates": {}, "holidays": []})
    config.set_year_rates(2025, 9860, 150000)
    config.set_year_rates(2026, 9820, 160000)
    assert config.hourly_wage_for(2025) == 9860
    assert config.meal_allowance_for(2025) == 150000
    assert config.hourly_wage_for(2026) == 9820
    assert config.meal_allowance_for(2026) == 160000
    assert config.rate_years() == [2025, 2026]
    print("OK: test_set_and_get_year_rates")


def test_missing_year_raises_clear_error():
    config = Config({"surveys": [], "rates": {"2026": {"hourly_wage": 9820, "meal_allowance": 160000}}, "holidays": []})
    try:
        config.hourly_wage_for(2027)
        raise AssertionError("2027년 요율이 없는데 예외가 안 남")
    except ValueError as e:
        assert "2027" in str(e), str(e)
        print("OK: test_missing_year_raises_clear_error")


def test_legacy_common_migrates_to_current_year():
    from datetime import date
    config = Config({"surveys": [], "common": {"hourly_wage": 9820, "meal_allowance": 160000}, "holidays": []})
    this_year = date.today().year
    assert config.hourly_wage_for(this_year) == 9820
    assert config.meal_allowance_for(this_year) == 160000
    print("OK: test_legacy_common_migrates_to_current_year")


def test_delete_year_rates():
    config = Config({"surveys": [], "rates": {"2026": {"hourly_wage": 9820, "meal_allowance": 160000}}, "holidays": []})
    config.delete_year_rates(2026)
    assert config.rate_years() == []
    print("OK: test_delete_year_rates")


def test_to_dict_round_trip():
    config = Config({"surveys": [], "rates": {}, "holidays": []})
    config.set_year_rates(2026, 9820, 160000)
    data = config.to_dict()
    assert data["rates"] == {"2026": {"hourly_wage": 9820, "meal_allowance": 160000}}
    assert "common" not in data
    reloaded = Config(data)
    assert reloaded.hourly_wage_for(2026) == 9820
    print("OK: test_to_dict_round_trip")


if __name__ == "__main__":
    test_set_and_get_year_rates()
    test_missing_year_raises_clear_error()
    test_legacy_common_migrates_to_current_year()
    test_delete_year_rates()
    test_to_dict_round_trip()
    print("ALL OK")
```

- [ ] **Step 2: 테스트 실행해 실패 확인**

Run: `python wage_calculator/tests/test_config_yearly_rates.py`
Expected: `AttributeError: 'Config' object has no attribute 'set_year_rates'`

- [ ] **Step 3: `config.py` 전체 교체**

[`wage_calculator/core/config.py`](../../../wage_calculator/core/config.py) 전체를 아래로 교체:

```python
import json
from dataclasses import dataclass, field, asdict
from datetime import date

from .paths import config_path

DEFAULT_CONFIG = {
    "surveys": [],       # [{"name": str, "start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}]
    "rates": {},          # {"2026": {"hourly_wage": 9820, "meal_allowance": 160000}, ...}
    "holidays": []        # ["YYYY-MM-DD", ...]
}


def _iso(d):
    if isinstance(d, date):
        return d.isoformat()
    return d


class Config:
    def __init__(self, data: dict):
        self.surveys = data.get("surveys", [])
        self.rates = dict(data.get("rates", {}))
        if not self.rates and "common" in data:
            # 레거시 config.json(단일 공통입력값) 마이그레이션: 현재 연도로 1회 이전.
            legacy = data["common"]
            self.rates[str(date.today().year)] = {
                "hourly_wage": legacy.get("hourly_wage", 0),
                "meal_allowance": legacy.get("meal_allowance", 0),
            }
        self.holidays = sorted(set(data.get("holidays", [])))

    # ---- 조사종류 ----
    def add_or_update_survey(self, name: str, start: str, end: str):
        start, end = _iso(start), _iso(end)
        for s in self.surveys:
            if s["name"] == name:
                s["start"], s["end"] = start, end
                return
        self.surveys.append({"name": name, "start": start, "end": end})

    def delete_survey(self, name: str):
        self.surveys = [s for s in self.surveys if s["name"] != name]

    def get_survey(self, name: str):
        for s in self.surveys:
            if s["name"] == name:
                return s
        return None

    def survey_names(self):
        return [s["name"] for s in self.surveys]

    # ---- 공휴일 ----
    def add_holiday(self, d: str):
        d = _iso(d)
        if d not in self.holidays:
            self.holidays.append(d)
            self.holidays.sort()

    def remove_holiday(self, d: str):
        d = _iso(d)
        self.holidays = [h for h in self.holidays if h != d]

    def holidays_in_range(self, start: str, end: str):
        start, end = _iso(start), _iso(end)
        return [h for h in self.holidays if start <= h <= end]

    # ---- 연도별 요율 ----
    def set_year_rates(self, year: int, hourly_wage: int, meal_allowance: int):
        self.rates[str(year)] = {"hourly_wage": hourly_wage, "meal_allowance": meal_allowance}

    def delete_year_rates(self, year: int):
        self.rates.pop(str(year), None)

    def rate_years(self):
        return sorted(int(y) for y in self.rates.keys())

    def hourly_wage_for(self, year: int) -> int:
        y = str(year)
        if y not in self.rates:
            raise ValueError(f"{year}년 시급/식대 요율이 설정되지 않았습니다. 설정 화면에서 추가하세요.")
        return self.rates[y]["hourly_wage"]

    def meal_allowance_for(self, year: int) -> int:
        y = str(year)
        if y not in self.rates:
            raise ValueError(f"{year}년 시급/식대 요율이 설정되지 않았습니다. 설정 화면에서 추가하세요.")
        return self.rates[y]["meal_allowance"]

    # ---- 저장/불러오기 ----
    def to_dict(self):
        return {"surveys": self.surveys, "rates": self.rates, "holidays": self.holidays}

    def save(self):
        path = config_path()
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls):
        path = config_path()
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                data = dict(DEFAULT_CONFIG)
        else:
            data = dict(DEFAULT_CONFIG)
        return cls(data)
```

- [ ] **Step 4: 테스트 실행해 통과 확인**

Run: `python wage_calculator/tests/test_config_yearly_rates.py`
Expected: `ALL OK`

- [ ] **Step 5: 기존 테스트 fixture를 새 스키마로 갱신**

[`wage_calculator/tests/test_end_to_end_v3.py:50`](../../../wage_calculator/tests/test_end_to_end_v3.py):
```python
    config = Config({"surveys": [], "common": {"hourly_wage": 9820, "meal_allowance": 160000}, "holidays": []})
```
을:
```python
    config = Config({"surveys": [], "rates": {"2026": {"hourly_wage": 9820, "meal_allowance": 160000}}, "holidays": []})
```
로 교체.

[`wage_calculator/tests/test_payroll_special_leave.py:14`](../../../wage_calculator/tests/test_payroll_special_leave.py)와 [`wage_calculator/tests/test_wage_sheet_special_leave.py:31`](../../../wage_calculator/tests/test_wage_sheet_special_leave.py)도 동일하게 `"common": {...}` → `"rates": {"2026": {...}}`로 교체(두 파일 모두 2026년 데이터를 쓰고 있음, 파일을 열어 실제 연도를 확인 후 맞춰 교체).

[`wage_calculator/tests/manual_check.py:32-33`](../../../wage_calculator/tests/manual_check.py):
```python
    config.hourly_wage = 9820
    config.meal_allowance = 160000
```
을:
```python
    config.set_year_rates(2026, 9820, 160000)
```
로 교체.

- [ ] **Step 6: 회귀 테스트 실행**

```bash
python wage_calculator/tests/test_end_to_end_v3.py
python wage_calculator/tests/test_payroll_special_leave.py
python wage_calculator/tests/test_wage_sheet_special_leave.py
```
Expected: 이 시점에는 `payroll.py`가 아직 `config.hourly_wage`(삭제된 프로퍼티)를 참조하므로 **AttributeError로 실패하는 것이 정상**이다(Task 2에서 고침). 여기서는 config.py 자체와 fixture 문법 오류가 없는지만 확인한다 — `AttributeError: 'Config' object has no attribute 'hourly_wage'`가 나오면 정상.

- [ ] **Step 7: 커밋**

```bash
git add wage_calculator/core/config.py wage_calculator/tests/test_config_yearly_rates.py wage_calculator/tests/test_end_to_end_v3.py wage_calculator/tests/test_payroll_special_leave.py wage_calculator/tests/test_wage_sheet_special_leave.py wage_calculator/tests/manual_check.py
git commit -m "feat: 시급/식대 요율을 연도별로 관리하도록 Config 스키마 변경"
```

---

### Task 2: `payroll.py`·`confirm_dialog.py`가 연도별 요율 조회를 쓰도록 변경

**Files:**
- Modify: `wage_calculator/core/payroll.py`
- Modify: `wage_calculator/gui/confirm_dialog.py:30`
- Test: `wage_calculator/tests/test_payroll_yearly_rates.py` (create)

**Interfaces:**
- Consumes: Task 1의 `Config.hourly_wage_for(year)`/`meal_allowance_for(year)`
- Produces: `calc_payroll(person, config, year, month)` 시그니처는 그대로, 내부적으로 `year`에 맞는 요율을 자동으로 골라 씀. `daily_meal_allowance(config, year, meal_eligible_days, calendar_month_days)` — 시그니처에 `year` 추가(기존 호출부는 `payroll.py` 내부 1곳뿐, 외부 참조 없음)

- [ ] **Step 1: 실패하는 테스트 작성**

`wage_calculator/tests/test_payroll_yearly_rates.py`:

```python
import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import Config
from core.models import TargetPerson
from core.payroll import calc_payroll


def _person(contract_start, contract_end):
    return TargetPerson(
        name="김철수", birth="19900101", ssn="900101-1234567", bank="", account="",
        survey_name="테스트조사", contract_start=contract_start, contract_end=contract_end,
        events=[],
    )


def test_calc_payroll_uses_rate_for_requested_year():
    config = Config({"surveys": [], "rates": {
        "2025": {"hourly_wage": 9860, "meal_allowance": 150000},
        "2026": {"hourly_wage": 9820, "meal_allowance": 160000},
    }, "holidays": []})

    person_2025 = _person(date(2025, 12, 1), date(2025, 12, 31))
    result_2025 = calc_payroll(person_2025, config, 2025, 12)
    assert result_2025.daily_wage == 9860 * 8, result_2025.daily_wage

    person_2026 = _person(date(2026, 1, 1), date(2026, 1, 31))
    result_2026 = calc_payroll(person_2026, config, 2026, 1)
    assert result_2026.daily_wage == 9820 * 8, result_2026.daily_wage

    print("OK: test_calc_payroll_uses_rate_for_requested_year")


def test_calc_payroll_raises_when_year_rate_missing():
    config = Config({"surveys": [], "rates": {"2026": {"hourly_wage": 9820, "meal_allowance": 160000}}, "holidays": []})
    person = _person(date(2025, 12, 1), date(2025, 12, 31))
    try:
        calc_payroll(person, config, 2025, 12)
        raise AssertionError("2025년 요율이 없는데 예외가 안 남")
    except ValueError as e:
        assert "2025" in str(e), str(e)
        print("OK: test_calc_payroll_raises_when_year_rate_missing")


if __name__ == "__main__":
    test_calc_payroll_uses_rate_for_requested_year()
    test_calc_payroll_raises_when_year_rate_missing()
    print("ALL OK")
```

- [ ] **Step 2: 테스트 실행해 실패 확인**

Run: `python wage_calculator/tests/test_payroll_yearly_rates.py`
Expected: `AttributeError: 'Config' object has no attribute 'hourly_wage'`

- [ ] **Step 3: `payroll.py` 요율 조회 부분 교체**

[`wage_calculator/core/payroll.py:64-65`](../../../wage_calculator/core/payroll.py):
```python
    daily_wage = round_down(config.hourly_wage * 8, 1)
    daily_meal = round_down(config.meal_allowance / 209 * 8, 1)
```
을:
```python
    daily_wage = round_down(config.hourly_wage_for(year) * 8, 1)
    daily_meal = round_down(config.meal_allowance_for(year) / 209 * 8, 1)
```
로 교체.

[`wage_calculator/core/payroll.py:101`](../../../wage_calculator/core/payroll.py):
```python
    late_out_deduction = round_down((config.hourly_wage / 60) * late_out_minutes, 10)
```
을:
```python
    late_out_deduction = round_down((config.hourly_wage_for(year) / 60) * late_out_minutes, 10)
```
로 교체.

[`wage_calculator/core/payroll.py:104`](../../../wage_calculator/core/payroll.py):
```python
    meal_allowance = round_down(daily_meal_allowance(config, meal_eligible_days, calendar_month_days), 10)
```
을:
```python
    meal_allowance = round_down(daily_meal_allowance(config, year, meal_eligible_days, calendar_month_days), 10)
```
로 교체.

파일 맨 끝 [`wage_calculator/core/payroll.py:165-166`](../../../wage_calculator/core/payroll.py):
```python
def daily_meal_allowance(config, meal_eligible_days, calendar_month_days):
    return config.meal_allowance * meal_eligible_days / calendar_month_days
```
을:
```python
def daily_meal_allowance(config, year, meal_eligible_days, calendar_month_days):
    return config.meal_allowance_for(year) * meal_eligible_days / calendar_month_days
```
로 교체.

- [ ] **Step 4: 테스트 실행해 통과 확인**

Run: `python wage_calculator/tests/test_payroll_yearly_rates.py`
Expected: `ALL OK`

- [ ] **Step 5: `confirm_dialog.py`도 연도별 조회로 교체**

[`wage_calculator/gui/confirm_dialog.py:30`](../../../wage_calculator/gui/confirm_dialog.py):
```python
        text.insert("end", f"[현재 적용 공통 입력값]\n시급: {app.config_obj.hourly_wage:,}원 / 월 식대: {app.config_obj.meal_allowance:,}원\n\n")
```
을:
```python
        text.insert("end", f"[현재 적용 요율({year}년)]\n시급: {app.config_obj.hourly_wage_for(year):,}원 / 월 식대: {app.config_obj.meal_allowance_for(year):,}원\n\n")
```
로 교체(이 파일 위쪽에서 이미 `year, month = app.work_year, app.work_month`로 `year`가 정의돼 있음).

- [ ] **Step 6: 이전 태스크에서 보류했던 회귀 테스트 재실행**

```bash
python wage_calculator/tests/test_end_to_end_v3.py
python wage_calculator/tests/test_payroll_special_leave.py
python wage_calculator/tests/test_wage_sheet_special_leave.py
```
Expected: 전부 `ALL OK`

- [ ] **Step 7: 커밋**

```bash
git add wage_calculator/core/payroll.py wage_calculator/gui/confirm_dialog.py wage_calculator/tests/test_payroll_yearly_rates.py
git commit -m "feat: calc_payroll과 확인창이 연도별 요율을 조회하도록 변경"
```

---

### Task 3: 설정화면에 연도별 요율 관리 탭

**Files:**
- Modify: `wage_calculator/gui/settings_dialog.py`

**Interfaces:**
- Consumes: Task 1의 `Config.rate_years()`, `set_year_rates()`, `delete_year_rates()`, `hourly_wage_for()`, `meal_allowance_for()`

- [ ] **Step 1: "공통 입력값" 탭을 연도별 요율 탭으로 교체**

[`wage_calculator/gui/settings_dialog.py`](../../../wage_calculator/gui/settings_dialog.py)의 `_build_common_tab`/`_save_common` 메서드 전체(현재 102~123행)를 아래로 교체:

```python
    # ---------------- 연도별 요율 관리 ----------------
    def _build_common_tab(self):
        frame = self.common_tab
        self.rate_list = ttk.Treeview(frame, columns=("year", "hourly", "meal"), show="headings", height=10)
        for c, label in [("year", "연도"), ("hourly", "시급환산(원)"), ("meal", "월 식대(원)")]:
            self.rate_list.heading(c, text=label)
            self.rate_list.column(c, width=140)
        self.rate_list.pack(fill="both", expand=True, padx=8, pady=8)
        self._reload_rates()

        form = ttk.Frame(frame)
        form.pack(fill="x", padx=8)
        ttk.Label(form, text="연도").grid(row=0, column=0)
        ttk.Label(form, text="시급환산(원)").grid(row=0, column=1)
        ttk.Label(form, text="월 식대(원)").grid(row=0, column=2)
        self.rate_year_var = tk.StringVar()
        self.rate_hourly_var = tk.StringVar()
        self.rate_meal_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.rate_year_var, width=10).grid(row=1, column=0, padx=2)
        ttk.Entry(form, textvariable=self.rate_hourly_var, width=14).grid(row=1, column=1, padx=2)
        ttk.Entry(form, textvariable=self.rate_meal_var, width=14).grid(row=1, column=2, padx=2)

        btns = ttk.Frame(frame)
        btns.pack(fill="x", padx=8, pady=6)
        ttk.Button(btns, text="추가/수정", command=self._add_or_update_rate).pack(side="left")
        ttk.Button(btns, text="선택 삭제", command=self._delete_rate).pack(side="left", padx=6)
        self.rate_list.bind("<<TreeviewSelect>>", self._on_rate_select)

    def _reload_rates(self):
        for i in self.rate_list.get_children():
            self.rate_list.delete(i)
        for year in self.config_obj.rate_years():
            self.rate_list.insert("", "end", values=(
                year, self.config_obj.hourly_wage_for(year), self.config_obj.meal_allowance_for(year),
            ))

    def _on_rate_select(self, _evt=None):
        sel = self.rate_list.selection()
        if not sel:
            return
        year, hourly, meal = self.rate_list.item(sel[0], "values")
        self.rate_year_var.set(year)
        self.rate_hourly_var.set(hourly)
        self.rate_meal_var.set(meal)

    def _add_or_update_rate(self):
        try:
            year = int(self.rate_year_var.get())
            hourly = int(self.rate_hourly_var.get())
            meal = int(self.rate_meal_var.get())
        except ValueError:
            messagebox.showerror("형식 오류", "연도/시급/식대는 모두 숫자로 입력하세요.")
            return
        self.config_obj.set_year_rates(year, hourly, meal)
        self.config_obj.save()
        self._reload_rates()

    def _delete_rate(self):
        sel = self.rate_list.selection()
        if not sel:
            return
        year = int(self.rate_list.item(sel[0], "values")[0])
        self.config_obj.delete_year_rates(year)
        self.config_obj.save()
        self._reload_rates()
```

- [ ] **Step 2: 수동 확인**

```bash
python wage_calculator/main.py
```
1. 메뉴 > 설정 > "공통 입력값" 탭(이제 연도별 요율 목록으로 보임).
2. 연도 2026, 시급 9820, 식대 160000 입력 후 "추가/수정" → 목록에 나타나는지 확인.
3. 같은 연도로 다시 입력해 값을 바꾸면 덮어써지는지(행이 늘어나지 않고 값만 바뀌는지) 확인.
4. 목록에서 행 선택 후 "선택 삭제" → 사라지는지 확인.
5. 설정 창을 닫았다가 다시 열어도 값이 유지되는지(`config.json` 저장 확인).

- [ ] **Step 3: 커밋**

```bash
git add wage_calculator/gui/settings_dialog.py
git commit -m "feat: 설정화면 공통입력값 탭을 연도별 요율 관리로 변경"
```

---

### Task 4: `date_utils.py`에 `birth_from_ssn`, `previous_month` 추가

**Files:**
- Modify: `wage_calculator/core/date_utils.py`
- Test: `wage_calculator/tests/test_date_utils_birth_and_month.py` (create)

**Interfaces:**
- Produces: `date_utils.birth_from_ssn(ssn: str) -> str`("YYYY-MM-DD" 반환, 형식이 이상하면 `ValueError`), `date_utils.previous_month(year: int, month: int) -> tuple[int, int]`

- [ ] **Step 1: 실패하는 테스트 작성**

`wage_calculator/tests/test_date_utils_birth_and_month.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import date_utils


def test_birth_from_ssn_1900s():
    assert date_utils.birth_from_ssn("980213-2752553") == "1998-02-13"
    print("OK: test_birth_from_ssn_1900s")


def test_birth_from_ssn_2000s():
    assert date_utils.birth_from_ssn("030101-4123456") == "2003-01-01"
    print("OK: test_birth_from_ssn_2000s")


def test_birth_from_ssn_no_hyphen():
    assert date_utils.birth_from_ssn("9802132752553") == "1998-02-13"
    print("OK: test_birth_from_ssn_no_hyphen")


def test_birth_from_ssn_invalid_raises():
    try:
        date_utils.birth_from_ssn("abc")
        raise AssertionError("짧은 문자열인데 예외가 안 남")
    except ValueError:
        print("OK: test_birth_from_ssn_invalid_raises")


def test_previous_month_normal():
    assert date_utils.previous_month(2026, 7) == (2026, 6)
    print("OK: test_previous_month_normal")


def test_previous_month_year_boundary():
    assert date_utils.previous_month(2026, 1) == (2025, 12)
    print("OK: test_previous_month_year_boundary")


if __name__ == "__main__":
    test_birth_from_ssn_1900s()
    test_birth_from_ssn_2000s()
    test_birth_from_ssn_no_hyphen()
    test_birth_from_ssn_invalid_raises()
    test_previous_month_normal()
    test_previous_month_year_boundary()
    print("ALL OK")
```

- [ ] **Step 2: 테스트 실행해 실패 확인**

Run: `python wage_calculator/tests/test_date_utils_birth_and_month.py`
Expected: `AttributeError: module 'core.date_utils' has no attribute 'birth_from_ssn'`

- [ ] **Step 3: 함수 구현**

[`wage_calculator/core/date_utils.py`](../../../wage_calculator/core/date_utils.py) 파일 맨 끝에 추가:

```python
_CENTURY_BY_GENDER_DIGIT = {
    "1": 1900, "2": 1900, "5": 1900, "6": 1900,
    "3": 2000, "4": 2000, "7": 2000, "8": 2000,
    "9": 1800, "0": 1800,
}


def birth_from_ssn(ssn: str) -> str:
    """주민등록번호 앞 7자리로 생년월일(YYYY-MM-DD)을 역산한다.

    B파일(근무상황)에는 생년월일만 있고 주민번호가 없어, 전월 임금내역
    파일(주민번호만 있음)의 사람을 당월 B파일과 매칭할 때(소급계산의
    완전퇴사자 처리) 사용한다."""
    digits = str(ssn).replace("-", "").strip()
    if len(digits) < 7 or not digits[:7].isdigit():
        raise ValueError(f"주민번호 형식이 올바르지 않습니다: {ssn!r}")
    yy, mm, dd, gender_digit = digits[0:2], digits[2:4], digits[4:6], digits[6]
    century = _CENTURY_BY_GENDER_DIGIT.get(gender_digit)
    if century is None:
        raise ValueError(f"주민번호 성별 구분 숫자가 올바르지 않습니다: {ssn!r}")
    year = century + int(yy)
    return f"{year:04d}-{mm}-{dd}"


def previous_month(year: int, month: int) -> tuple:
    """(year, month)의 바로 전 달을 (year, month) 튜플로 반환. 1월의 전월은
    전년도 12월(연도 경계 처리)."""
    if month == 1:
        return year - 1, 12
    return year, month - 1
```

- [ ] **Step 4: 테스트 실행해 통과 확인**

Run: `python wage_calculator/tests/test_date_utils_birth_and_month.py`
Expected: `ALL OK`

- [ ] **Step 5: 커밋**

```bash
git add wage_calculator/core/date_utils.py wage_calculator/tests/test_date_utils_birth_and_month.py
git commit -m "feat: date_utils에 주민번호->생년월일 역산, 전월 계산 유틸 추가"
```

---

### Task 5: `parser.py`에 `load_previous_payroll` 추가

**Files:**
- Modify: `wage_calculator/core/parser.py`
- Test: `wage_calculator/tests/test_parser_previous_payroll.py` (create)

**Interfaces:**
- Consumes: `output/wage_sheet.py`의 `COL`, `SHEET_NAME`, `DATA_START_ROW`(기존 상수, Task 8 이후에도 그대로 유지되는 이름들 — Task 8은 열을 "추가"만 하고 기존 열 위치/이름은 바꾸지 않음)
- Produces: `load_previous_payroll(path) -> dict[str, dict]` — 키는 주민번호 문자열, 값은 `{ssn, name, contract_start, contract_end, total_payment, bank, account}`

- [ ] **Step 1: 실패하는 테스트 작성**

`wage_calculator/tests/test_parser_previous_payroll.py`:

```python
import sys
from pathlib import Path
from datetime import date
import tempfile
import os

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import openpyxl
from core.parser import load_previous_payroll
from core.payroll import PayrollResult
from output.wage_sheet import build_wage_sheet


def _make_result(name, ssn, total_payment):
    return PayrollResult(
        name=name, birth="19900101", ssn=ssn, bank="하나은행", account="1234567890",
        survey_name="테스트조사",
        period_start=date(2026, 6, 1), period_end=date(2026, 6, 30),
        contract_start=date(2026, 6, 1), contract_end=date(2026, 6, 30),
        daily_wage=78560, actual_workdays=20, public_leave_days=0, paid_holiday_days=0,
        absence_days=0, total_days=20, late_out_minutes=0, weekly_holiday_days=4,
        calendar_month_days=30, meal_eligible_days=30, remaining_leave_days=0.0,
        is_final_month=False, gross_pay=1571200, late_out_deduction=0, base_pay=1571200,
        weekly_holiday_pay=314240, meal_allowance=160000, leave_compensation=0,
        total_payment=total_payment,
    )


def test_load_previous_payroll_reads_by_fixed_columns():
    fd, path = tempfile.mkstemp(suffix=".xlsx")
    os.close(fd)
    try:
        wb = openpyxl.Workbook()
        wb.remove(wb.active)
        result = _make_result("김철수", "900101-1234567", 2045440)
        build_wage_sheet(wb, [result])
        wb.save(path)

        previous = load_previous_payroll(path)
        assert "900101-1234567" in previous, previous.keys()
        entry = previous["900101-1234567"]
        assert entry["name"] == "김철수", entry
        assert entry["total_payment"] == 2045440, entry
        assert entry["contract_start"] == date(2026, 6, 1), entry
        assert entry["contract_end"] == date(2026, 6, 30), entry
        assert entry["bank"] == "하나은행", entry
        assert entry["account"] == "1234567890", entry
        print("OK: test_load_previous_payroll_reads_by_fixed_columns")
    finally:
        os.remove(path)


if __name__ == "__main__":
    test_load_previous_payroll_reads_by_fixed_columns()
    print("ALL OK")
```

- [ ] **Step 2: 테스트 실행해 실패 확인**

Run: `python wage_calculator/tests/test_parser_previous_payroll.py`
Expected: `ImportError: cannot import name 'load_previous_payroll'`

- [ ] **Step 3: 함수 구현**

[`wage_calculator/core/parser.py`](../../../wage_calculator/core/parser.py) 파일 상단 임포트에 추가:

```python
from output.wage_sheet import COL, SHEET_NAME, DATA_START_ROW
```

파일 끝(또는 `load_giganje_rows` 바로 아래)에 추가:

```python
def load_previous_payroll(path) -> dict:
    """이 프로그램이 직전에 생성한 임금내역(월중) 엑셀을 다시 읽어, 소급계산에
    필요한 전월 정보를 주민번호를 키로 돌려준다. 이 파일은 프로그램이 직접
    만든 것이라 헤더 텍스트가 아니라 output/wage_sheet.py의 COL과 동일한
    고정 열 위치로 읽는다(헤더가 병합 셀이라 텍스트 파싱이 불안정함)."""
    wb = openpyxl.load_workbook(path, data_only=True)
    if SHEET_NAME not in wb.sheetnames:
        raise ValueError(f"전월 임금내역 파일에 '{SHEET_NAME}' 시트가 없습니다.")
    ws = wb[SHEET_NAME]

    result = {}
    for r in range(DATA_START_ROW, ws.max_row + 1):
        name = ws.cell(row=r, column=COL["name"]).value
        ssn = ws.cell(row=r, column=COL["ssn"]).value
        if name is None or str(name).strip() == "" or ssn is None or str(ssn).strip() == "":
            continue
        ssn = str(ssn).strip()
        contract_start = ws.cell(row=r, column=COL["contract_start"]).value
        contract_end = ws.cell(row=r, column=COL["contract_end"]).value
        result[ssn] = {
            "ssn": ssn,
            "name": str(name).strip(),
            "contract_start": date_utils.parse_date(contract_start) if contract_start else None,
            "contract_end": date_utils.parse_date(contract_end) if contract_end else None,
            "total_payment": ws.cell(row=r, column=COL["total_payment"]).value or 0,
            "bank": ws.cell(row=r, column=COL["bank"]).value or "",
            "account": ws.cell(row=r, column=COL["account"]).value or "",
        }
    return result
```

- [ ] **Step 4: 테스트 실행해 통과 확인**

Run: `python wage_calculator/tests/test_parser_previous_payroll.py`
Expected: `ALL OK`

- [ ] **Step 5: 커밋**

```bash
git add wage_calculator/core/parser.py wage_calculator/tests/test_parser_previous_payroll.py
git commit -m "feat: 전월 임금내역 엑셀을 다시 읽어 소급계산용 데이터로 파싱하는 load_previous_payroll 추가"
```

---

### Task 6: 당월 대상자 소급조정액 계산 (`core/retroactive.py` 1부)

**Files:**
- Modify: `wage_calculator/core/parser.py` (행→이벤트 변환 로직 추출)
- Create: `wage_calculator/core/retroactive.py`
- Test: `wage_calculator/tests/test_retroactive_current_month.py` (create)

**Interfaces:**
- Produces: `parser.events_from_row(row: dict) -> list[LeaveEvent]`(신규, `build_target_people`가 이미 하던 걸 그대로 추출), `retroactive.current_month_adjustments(people, previous_payroll, config, prev_year, prev_month) -> dict[str, int]`(person_key -> 소급조정액)

- [ ] **Step 1: `parser.py`에서 행→이벤트 변환 로직 추출 (리팩터링, 동작 변화 없음)**

[`wage_calculator/core/parser.py`](../../../wage_calculator/core/parser.py)의 `build_target_people` 안에서 아래 블록:

```python
        raw_category = row.get("종별")
        date_field = row.get("사용기간(날짜)")
        if raw_category is None or str(raw_category).strip() == "" or date_field is None:
            continue  # 사용 내역 없음(만근) 행
        raw_category = str(raw_category).strip()

        time_field = row.get("사용시간(시분)")
        time_range = date_utils.parse_time_range(time_field)
        start_d, end_d = date_utils.parse_date_range(date_field)

        if time_range is not None:
            # 시간 기재분: 단일 날짜에만 적용(사양상 다일+시간 조합은 발생하지 않음)
            t_start, t_end = time_range
            minutes = date_utils.deduct_minutes(t_start, t_end)
            person.events.append(
                build_event(raw_category, start_d, t_start, t_end, minutes)
            )
        else:
            # 종일 항목의 다일(多日) 사용기간은 근무일(월~금)만 하루로 집계.
            # 토/일이 기간 중간에 끼어도 원래 근무의무가 없던 날이라 공가/결근 등으로
            # 잡히면 실출근(NETWORKDAYS 기준) 계산과 불일치가 생기므로 주말은 제외.
            # source_range=(start_d, end_d): 원본 행 전체 기간을 넘겨서, 같은 행에서
            # 펼쳐진 이벤트들이 나중에(특별휴가 마킹 화면 등에서) 한 그룹으로 묶이게 함.
            for d in date_utils.daterange(start_d, end_d):
                if d.weekday() < 5:
                    person.events.append(build_event(raw_category, d, source_range=(start_d, end_d)))

    return people, missing_names, ambiguous_names
```

를 아래로 교체(로직은 동일, `person.events.append(...)`를 새 함수 `events_from_row(row)` 호출 + `extend`로 바꾼 것뿐):

```python
        person.events.extend(events_from_row(row))

    return people, missing_names, ambiguous_names


def events_from_row(row) -> list:
    """B파일 원본 행 1개(dict)를 LeaveEvent 리스트로 변환. 사용 내역이 없는
    (만근) 행이면 빈 리스트. build_target_people()의 매칭 로직과 분리해 두면,
    소급계산(완전퇴사자)처럼 로스터 밖의 임시 인물에게도 같은 파싱 규칙을
    재사용할 수 있다."""
    raw_category = row.get("종별")
    date_field = row.get("사용기간(날짜)")
    if raw_category is None or str(raw_category).strip() == "" or date_field is None:
        return []
    raw_category = str(raw_category).strip()

    time_field = row.get("사용시간(시분)")
    time_range = date_utils.parse_time_range(time_field)
    start_d, end_d = date_utils.parse_date_range(date_field)

    events = []
    if time_range is not None:
        t_start, t_end = time_range
        minutes = date_utils.deduct_minutes(t_start, t_end)
        events.append(build_event(raw_category, start_d, t_start, t_end, minutes))
    else:
        for d in date_utils.daterange(start_d, end_d):
            if d.weekday() < 5:
                events.append(build_event(raw_category, d, source_range=(start_d, end_d)))
    return events
```

- [ ] **Step 2: 리팩터링 회귀 확인(동작이 바뀌지 않았는지)**

```bash
python wage_calculator/tests/test_end_to_end_v3.py
python wage_calculator/tests/test_parser_source_range.py
python wage_calculator/tests/test_source_range.py
python wage_calculator/tests/test_special_leave_grouping.py
```
Expected: 전부 `ALL OK`(리팩터링만 했으므로 기존 테스트가 그대로 통과해야 함)

- [ ] **Step 3: 리팩터링 커밋**

```bash
git add wage_calculator/core/parser.py
git commit -m "refactor: B파일 행->이벤트 변환 로직을 events_from_row로 추출(동작 변화 없음)"
```

- [ ] **Step 4: `retroactive.py` 실패하는 테스트 작성**

`wage_calculator/tests/test_retroactive_current_month.py`:

```python
import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import Config
from core.models import TargetPerson
from core.parser import person_key
from core.retroactive import current_month_adjustments


def _config():
    return Config({"surveys": [], "rates": {
        "2026": {"hourly_wage": 9820, "meal_allowance": 160000},
    }, "holidays": []})


def test_adjustment_is_recalculated_minus_previously_paid():
    person = TargetPerson(
        name="김철수", birth="19900101", ssn="900101-1234567", bank="", account="",
        survey_name="테스트조사", contract_start=date(2026, 6, 1), contract_end=date(2026, 6, 30),
        events=[],
    )
    people = {person_key("김철수", "19900101"): person}
    previous_payroll = {
        "900101-1234567": {
            "ssn": "900101-1234567", "name": "김철수",
            "contract_start": date(2026, 6, 1), "contract_end": date(2026, 6, 30),
            "total_payment": 1000000,  # 전월에 실제로 지급된(더 적었던) 금액
            "bank": "", "account": "",
        },
    }
    adjustments = current_month_adjustments(people, previous_payroll, _config(), 2026, 6)
    key = person_key("김철수", "19900101")
    assert key in adjustments
    assert adjustments[key] > 0, "재계산액이 더 크므로 추가지급(양수)이어야 함: " + str(adjustments[key])
    print("OK: test_adjustment_is_recalculated_minus_previously_paid")


def test_no_previous_entry_means_zero_adjustment():
    person = TargetPerson(
        name="박신입", birth="19950505", ssn="950505-1234567", bank="", account="",
        survey_name="테스트조사", contract_start=date(2026, 6, 1), contract_end=date(2026, 6, 30),
        events=[],
    )
    people = {person_key("박신입", "19950505"): person}
    adjustments = current_month_adjustments(people, {}, _config(), 2026, 6)
    assert adjustments[person_key("박신입", "19950505")] == 0
    print("OK: test_no_previous_entry_means_zero_adjustment")


if __name__ == "__main__":
    test_adjustment_is_recalculated_minus_previously_paid()
    test_no_previous_entry_means_zero_adjustment()
    print("ALL OK")
```

- [ ] **Step 5: 테스트 실행해 실패 확인**

Run: `python wage_calculator/tests/test_retroactive_current_month.py`
Expected: `ModuleNotFoundError: No module named 'core.retroactive'`

- [ ] **Step 6: `retroactive.py` 생성(당월 대상자 부분만)**

`wage_calculator/core/retroactive.py`:

```python
"""5장(소급계산): 전월 임금내역 파일 + 당월 B파일을 이용해 전월분을 다시
계산하고, 실제 지급됐던 금액과 비교한 차액(소급조정액)을 구한다."""
from dataclasses import dataclass

from . import date_utils
from .models import TargetPerson
from .payroll import calc_payroll


@dataclass
class DepartedRetro:
    name: str
    ssn: str
    bank: str
    account: str
    prev_recalculated: int   # 전월 재계산 지급총액
    prev_paid: int           # 전월 실지급액(전월 파일에 기록된 값)
    adjustment: int          # prev_recalculated - prev_paid


def current_month_adjustments(people, previous_payroll, config, prev_year, prev_month):
    """당월 로스터(people) 각자에 대해, 전월 파일에도 같은 주민번호가 있으면
    전월분을 다시 계산해 소급조정액(재계산액-전월실지급액)을 구한다. 전월
    파일에 없으면(신규입사자 등) 소급 없음(0)."""
    adjustments = {}
    for key, person in people.items():
        prev = previous_payroll.get(person.ssn)
        if prev is None:
            adjustments[key] = 0
            continue
        recalculated = calc_payroll(person, config, prev_year, prev_month)
        adjustments[key] = recalculated.total_payment - prev["total_payment"]
    return adjustments
```

- [ ] **Step 7: 테스트 실행해 통과 확인**

Run: `python wage_calculator/tests/test_retroactive_current_month.py`
Expected: `ALL OK`

- [ ] **Step 8: 커밋**

```bash
git add wage_calculator/core/retroactive.py wage_calculator/tests/test_retroactive_current_month.py
git commit -m "feat: 당월 대상자의 전월분 재계산 기반 소급조정액 계산 추가"
```

---

### Task 7: 완전퇴사자 소급 처리 (`core/retroactive.py` 2부)

**Files:**
- Modify: `wage_calculator/core/retroactive.py`
- Test: `wage_calculator/tests/test_retroactive_departed.py` (create)

**Interfaces:**
- Consumes: Task 4의 `date_utils.birth_from_ssn`, Task 6의 `parser.events_from_row`
- Produces: `retroactive.departed_retroactive(people, previous_payroll, giganje_rows, config, prev_year, prev_month) -> list[DepartedRetro]`, `retroactive.compute_retroactive(people, previous_payroll, giganje_rows, config, prev_year, prev_month) -> (dict, list[DepartedRetro])`(당월 대상자 조정액 + 완전퇴사자 목록을 한번에)

- [ ] **Step 1: 실패하는 테스트 작성**

`wage_calculator/tests/test_retroactive_departed.py`:

```python
import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import Config
from core.retroactive import departed_retroactive, compute_retroactive


def _config():
    return Config({"surveys": [], "rates": {
        "2026": {"hourly_wage": 9820, "meal_allowance": 160000},
    }, "holidays": []})


def test_departed_person_with_leftover_rows_is_recalculated():
    # 최도영: 전월(6월)파일엔 있지만 당월(7월) A파일엔 없음(완전퇴사).
    # 당월 B파일에는 6월 말 결근 잔여행이 남아있음(export가 날짜범위로만 걸리므로).
    previous_payroll = {
        "980126-2641395": {
            "ssn": "980126-2641395", "name": "최도영",
            "contract_start": date(2026, 6, 1), "contract_end": date(2026, 6, 30),
            "total_payment": 2000000,
            "bank": "하나은행", "account": "111",
        },
    }
    giganje_rows = [
        {
            "소속": "부산지방고용노동청", "직급": "기간제근로자", "성명": "최도영",
            "생년월일": "1998-01-26", "종별": "결근",
            "사용기간(날짜)": "2026-06-29", "사용시간(시분)": None,
        },
    ]
    departed = departed_retroactive({}, previous_payroll, giganje_rows, _config(), 2026, 6)
    assert len(departed) == 1, departed
    d = departed[0]
    assert d.name == "최도영"
    assert d.prev_paid == 2000000
    assert d.adjustment == d.prev_recalculated - 2000000
    print("OK: test_departed_person_with_leftover_rows_is_recalculated")


def test_departed_person_with_no_leftover_rows_is_skipped():
    previous_payroll = {
        "980126-2641395": {
            "ssn": "980126-2641395", "name": "최도영",
            "contract_start": date(2026, 6, 1), "contract_end": date(2026, 6, 30),
            "total_payment": 2000000,
            "bank": "하나은행", "account": "111",
        },
    }
    departed = departed_retroactive({}, previous_payroll, [], _config(), 2026, 6)
    assert departed == [], "당월 B파일에 잔여 행이 없으면 출력 대상에서 빠져야 함"
    print("OK: test_departed_person_with_no_leftover_rows_is_skipped")


def test_departed_person_name_collision_with_different_birth_is_ignored():
    # B파일에 동명이인이 있고 생년월일이 다르면 매칭하지 않는다(잘못된 소급 방지).
    previous_payroll = {
        "980126-2641395": {  # -> 1998-01-26
            "ssn": "980126-2641395", "name": "최도영",
            "contract_start": date(2026, 6, 1), "contract_end": date(2026, 6, 30),
            "total_payment": 2000000, "bank": "", "account": "",
        },
    }
    giganje_rows = [
        {
            "소속": "부산지방고용노동청", "직급": "기간제근로자", "성명": "최도영",
            "생년월일": "1985-03-03",  # 전월파일 사람과 다른 생년월일 -> 동명이인
            "종별": "결근", "사용기간(날짜)": "2026-06-29", "사용시간(시분)": None,
        },
    ]
    departed = departed_retroactive({}, previous_payroll, giganje_rows, _config(), 2026, 6)
    assert departed == [], "생년월일이 다른 동명이인의 행을 매칭하면 안 됨"
    print("OK: test_departed_person_name_collision_with_different_birth_is_ignored")


def test_compute_retroactive_combines_both():
    result = compute_retroactive({}, {}, [], _config(), 2026, 6)
    assert result == ({}, [])
    print("OK: test_compute_retroactive_combines_both")


if __name__ == "__main__":
    test_departed_person_with_leftover_rows_is_recalculated()
    test_departed_person_with_no_leftover_rows_is_skipped()
    test_departed_person_name_collision_with_different_birth_is_ignored()
    test_compute_retroactive_combines_both()
    print("ALL OK")
```

- [ ] **Step 2: 테스트 실행해 실패 확인**

Run: `python wage_calculator/tests/test_retroactive_departed.py`
Expected: `ImportError: cannot import name 'departed_retroactive'`

- [ ] **Step 3: `retroactive.py`에 완전퇴사자 처리 + 통합 함수 추가**

[`wage_calculator/core/retroactive.py`](../../../wage_calculator/core/retroactive.py) 상단 임포트를:

```python
from . import date_utils
from .models import TargetPerson
from .payroll import calc_payroll
```

에서 아래로 교체:

```python
from . import date_utils
from .models import TargetPerson
from .parser import events_from_row
from .payroll import calc_payroll
```

파일 끝에 추가:

```python
def departed_retroactive(people, previous_payroll, giganje_rows, config, prev_year, prev_month):
    """당월 로스터(people)에 없는 전월파일 인원(완전퇴사) 중, 당월 B파일에
    이름+생년월일이 일치하는 잔여 근무상황 행이 남아있는 사람만 전월분을
    재계산한다. 일치하는 행이 없으면 재계산할 새 정보가 없다는 뜻이므로
    건너뛴다(소급조정액 0, 출력도 안 함). B파일에는 주민번호가 없고
    생년월일만 있으므로, 전월파일의 주민번호로부터 생년월일을 역산해
    비교한다(동명이인이 있어도 정확히 구분하기 위함)."""
    current_ssns = {p.ssn for p in people.values() if p.ssn}
    results = []
    for ssn, prev in previous_payroll.items():
        if ssn in current_ssns:
            continue
        try:
            expected_birth = date_utils.birth_from_ssn(ssn)
        except ValueError:
            continue  # 주민번호 형식이 이상하면 안전하게 건너뜀(잘못된 매칭 방지)

        matched_rows = [
            row for row in giganje_rows
            if str(row.get("성명") or "").strip() == prev["name"]
            and str(row.get("생년월일") or "").strip() == expected_birth
        ]
        if not matched_rows:
            continue

        temp_person = TargetPerson(
            name=prev["name"], birth=expected_birth, ssn=ssn,
            bank=prev["bank"], account=prev["account"],
            contract_start=prev["contract_start"], contract_end=prev["contract_end"],
        )
        for row in matched_rows:
            temp_person.events.extend(events_from_row(row))

        recalculated = calc_payroll(temp_person, config, prev_year, prev_month)
        results.append(DepartedRetro(
            name=prev["name"], ssn=ssn, bank=prev["bank"], account=prev["account"],
            prev_recalculated=recalculated.total_payment,
            prev_paid=prev["total_payment"],
            adjustment=recalculated.total_payment - prev["total_payment"],
        ))
    return results


def compute_retroactive(people, previous_payroll, giganje_rows, config, prev_year, prev_month):
    """당월 대상자 소급조정액 + 완전퇴사자 소급 내역을 한 번에 계산한다.
    반환: (adjustments: dict[person_key, int], departed: list[DepartedRetro])"""
    adjustments = current_month_adjustments(people, previous_payroll, config, prev_year, prev_month)
    departed = departed_retroactive(people, previous_payroll, giganje_rows, config, prev_year, prev_month)
    return adjustments, departed
```

- [ ] **Step 4: 테스트 실행해 통과 확인**

Run: `python wage_calculator/tests/test_retroactive_departed.py`
Expected: `ALL OK`

- [ ] **Step 5: 커밋**

```bash
git add wage_calculator/core/retroactive.py wage_calculator/tests/test_retroactive_departed.py
git commit -m "feat: 완전퇴사자의 당월 B파일 잔여행 기반 소급계산 + compute_retroactive 통합 함수 추가"
```

---

### Task 8: `wage_sheet.py`에 소급조정액/최종지급액 열 추가

**Files:**
- Modify: `wage_calculator/output/wage_sheet.py`
- Test: `wage_calculator/tests/test_wage_sheet_retro_columns.py` (create)

**Interfaces:**
- Produces: `build_wage_sheet(wb, results, seq_start=1, retro_adjustments=None)` — `retro_adjustments`는 `dict[person_key, int]`(기본값 없으면 전원 0)

- [ ] **Step 1: 실패하는 테스트 작성**

`wage_calculator/tests/test_wage_sheet_retro_columns.py`:

```python
import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import openpyxl
from core.parser import person_key
from core.payroll import PayrollResult
from output.wage_sheet import build_wage_sheet


def _result(name, birth, total_payment):
    return PayrollResult(
        name=name, birth=birth, ssn="", bank="", account="", survey_name="테스트조사",
        period_start=date(2026, 7, 1), period_end=date(2026, 7, 31),
        contract_start=date(2026, 7, 1), contract_end=date(2026, 7, 31),
        daily_wage=78560, actual_workdays=23, public_leave_days=0, paid_holiday_days=0,
        absence_days=0, total_days=23, late_out_minutes=0, weekly_holiday_days=4,
        calendar_month_days=31, meal_eligible_days=31, remaining_leave_days=0.0,
        is_final_month=False, gross_pay=1806880, late_out_deduction=0, base_pay=1806880,
        weekly_holiday_pay=314240, meal_allowance=160000, leave_compensation=0,
        total_payment=total_payment,
    )


def test_retro_columns_written_and_summed():
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    result = _result("김철수", "19900101", 2281120)
    key = person_key("김철수", "19900101")
    ws = build_wage_sheet(wb, [result], retro_adjustments={key: -10000})

    assert ws.cell(row=4, column=30).value == -10000, "소급조정액(AD열)"
    assert ws.cell(row=4, column=31).value == 2271120, "최종지급액(AE열) = 지급총액+소급조정액"
    print("OK: test_retro_columns_written_and_summed")


def test_no_retro_adjustment_defaults_to_zero():
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    result = _result("박신입", "19950505", 1500000)
    ws = build_wage_sheet(wb, [result])

    assert ws.cell(row=4, column=30).value == 0
    assert ws.cell(row=4, column=31).value == 1500000
    print("OK: test_no_retro_adjustment_defaults_to_zero")


if __name__ == "__main__":
    test_retro_columns_written_and_summed()
    test_no_retro_adjustment_defaults_to_zero()
    print("ALL OK")
```

- [ ] **Step 2: 테스트 실행해 실패 확인**

Run: `python wage_calculator/tests/test_wage_sheet_retro_columns.py`
Expected: `AssertionError: 소급조정액(AD열)` (열이 없어 `None`)

- [ ] **Step 3: `wage_sheet.py` 수정**

[`wage_calculator/output/wage_sheet.py`](../../../wage_calculator/output/wage_sheet.py)의 `COL` 딕셔너리:

```python
COL = {
    "seq": 1, "name": 2, "survey": 3, "period_start": 4, "period_end": 5,
    "daily_wage": 6, "actual_workdays": 7, "public_leave": 8, "paid_holiday": 9,
    "absence": 10, "total_days": 11, "late_out": 12, "weekly_holiday": 13,
    "calendar_days": 14, "meal_eligible": 15, "remaining_leave": 16,
    "gross_pay": 17, "late_out_deduction": 18, "base_pay": 19, "weekly_holiday_pay": 20,
    "meal_allowance": 21, "leave_compensation": 22, "total_payment": 23,
    "ssn": 24, "contract_start": 25, "contract_end": 26, "bank": 27, "account": 28,
    "note": 29,
}
```

를:

```python
COL = {
    "seq": 1, "name": 2, "survey": 3, "period_start": 4, "period_end": 5,
    "daily_wage": 6, "actual_workdays": 7, "public_leave": 8, "paid_holiday": 9,
    "absence": 10, "total_days": 11, "late_out": 12, "weekly_holiday": 13,
    "calendar_days": 14, "meal_eligible": 15, "remaining_leave": 16,
    "gross_pay": 17, "late_out_deduction": 18, "base_pay": 19, "weekly_holiday_pay": 20,
    "meal_allowance": 21, "leave_compensation": 22, "total_payment": 23,
    "ssn": 24, "contract_start": 25, "contract_end": 26, "bank": 27, "account": 28,
    "note": 29, "retro_adjustment": 30, "final_payment": 31,
}
```

`_write_headers` 함수 안, `_set(ws, "AC1", "비고", "AC1:AC3")` 바로 아래에 추가:

```python
    _set(ws, "AD1", "소급\n조정액", "AD1:AD3")
    _set(ws, "AE1", "최종\n지급액", "AE1:AE3")
```

`_write_headers` 함수 안 열 너비 지정 루프:

```python
    for col in range(1, 30):
        from openpyxl.utils import get_column_letter
        ws.column_dimensions[get_column_letter(col)].width = 10
```

를:

```python
    for col in range(1, 32):
        from openpyxl.utils import get_column_letter
        ws.column_dimensions[get_column_letter(col)].width = 10
```

로 교체.

`build_wage_sheet` 함수 시그니처와 본문:

```python
def build_wage_sheet(wb, results, seq_start=1):
    ws = wb.create_sheet(SHEET_NAME)
    _write_headers(ws)

    row = DATA_START_ROW
    for i, r in enumerate(results, start=seq_start):
        ws.cell(row=row, column=COL["seq"], value=i)
        ...
        ws.cell(row=row, column=COL["note"], value=r.special_leave_note)
        row += 1
```

를:

```python
def build_wage_sheet(wb, results, seq_start=1, retro_adjustments=None):
    from core.parser import person_key

    retro_adjustments = retro_adjustments or {}
    ws = wb.create_sheet(SHEET_NAME)
    _write_headers(ws)

    row = DATA_START_ROW
    for i, r in enumerate(results, start=seq_start):
        ws.cell(row=row, column=COL["seq"], value=i)
        ...
        ws.cell(row=row, column=COL["note"], value=r.special_leave_note)
        adjustment = retro_adjustments.get(person_key(r.name, r.birth), 0)
        ws.cell(row=row, column=COL["retro_adjustment"], value=adjustment)
        ws.cell(row=row, column=COL["final_payment"], value=r.total_payment + adjustment)
        row += 1
```

(`...`로 표시한 부분은 기존 셀 쓰기 코드 그대로 유지 — `name`부터 `note`까지 기존 22줄은 손대지 않는다.)

- [ ] **Step 4: 테스트 실행해 통과 확인**

Run: `python wage_calculator/tests/test_wage_sheet_retro_columns.py`
Expected: `ALL OK`

- [ ] **Step 5: 기존 wage_sheet 테스트 회귀 확인**

```bash
python wage_calculator/tests/test_wage_sheet_special_leave.py
python wage_calculator/tests/test_end_to_end_v3.py
```
Expected: 전부 `ALL OK`

- [ ] **Step 6: 커밋**

```bash
git add wage_calculator/output/wage_sheet.py wage_calculator/tests/test_wage_sheet_retro_columns.py
git commit -m "feat: 임금내역 시트에 소급조정액/최종지급액 열 추가"
```

---

### Task 9: 지급내역 수식 근거 시트 (`output/evidence_sheet.py`)

**Files:**
- Create: `wage_calculator/output/evidence_sheet.py`
- Test: `wage_calculator/tests/test_evidence_sheet.py` (create)

**Interfaces:**
- Produces: `build_evidence_sheet(wb, results, config, retro_adjustments=None) -> Worksheet`

- [ ] **Step 1: 실패하는 테스트 작성**

`wage_calculator/tests/test_evidence_sheet.py`:

```python
import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import openpyxl
from core.config import Config
from core.parser import person_key
from core.payroll import PayrollResult
from output.evidence_sheet import build_evidence_sheet, COL


def _config():
    return Config({"surveys": [], "rates": {"2026": {"hourly_wage": 9820, "meal_allowance": 160000}}, "holidays": []})


def _result():
    return PayrollResult(
        name="김철수", birth="19900101", ssn="", bank="", account="", survey_name="테스트조사",
        period_start=date(2026, 7, 1), period_end=date(2026, 7, 31),
        contract_start=date(2026, 7, 1), contract_end=date(2026, 7, 31),
        daily_wage=78560, actual_workdays=23, public_leave_days=0, paid_holiday_days=0,
        absence_days=0, total_days=23, late_out_minutes=120, weekly_holiday_days=4,
        calendar_month_days=31, meal_eligible_days=31, remaining_leave_days=1.5,
        is_final_month=True, gross_pay=1806880, late_out_deduction=19630, base_pay=1787250,
        weekly_holiday_pay=314240, meal_allowance=160000, leave_compensation=137310,
        total_payment=2398800,
    )


def test_formula_cells_reference_same_row_inputs():
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    result = _result()
    key = person_key(result.name, result.birth)
    ws = build_evidence_sheet(wb, [result], _config(), retro_adjustments={key: -10000})

    row = 2  # DATA_START_ROW
    assert ws.cell(row=row, column=COL["hourly_wage"]).value == 9820
    assert ws.cell(row=row, column=COL["daily_wage"]).value == "=ROUNDDOWN(C2*8,0)"
    assert ws.cell(row=row, column=COL["gross_pay"]).value == "=L2*D2"
    assert ws.cell(row=row, column=COL["late_out_deduction"]).value == "=ROUNDDOWN(C2/60*E2,-1)"
    assert ws.cell(row=row, column=COL["base_pay"]).value == "=ROUNDDOWN(N2-O2,-1)"
    assert ws.cell(row=row, column=COL["total_payment"]).value == "=ROUNDDOWN(P2+Q2+R2+S2,-1)"
    assert ws.cell(row=row, column=COL["retro_adjustment"]).value == -10000
    assert ws.cell(row=row, column=COL["final_payment"]).value == "=T2+U2"
    print("OK: test_formula_cells_reference_same_row_inputs")


if __name__ == "__main__":
    test_formula_cells_reference_same_row_inputs()
    print("ALL OK")
```

(열 문자는 `COL` 딕셔너리 순서에서 계산됨: `hourly_wage=3`(C), `total_days=4`(D), `late_out_minutes=5`(E), `daily_wage=12`(L), `late_out_deduction=15`(O), `base_pay=16`(P), `weekly_holiday_pay=17`(Q), `meal_allowance=18`(R), `leave_compensation=19`(S), `total_payment=20`(T), `retro_adjustment=21`(U) — Step 3의 COL 정의와 정확히 일치해야 함.)

- [ ] **Step 2: 테스트 실행해 실패 확인**

Run: `python wage_calculator/tests/test_evidence_sheet.py`
Expected: `ModuleNotFoundError: No module named 'output.evidence_sheet'`

- [ ] **Step 3: `evidence_sheet.py` 생성**

`wage_calculator/output/evidence_sheet.py`:

```python
"""6장(지급내역 수식 근거): 지급내역(금액) 계산 과정을 실제 엑셀 수식으로
재현하는 시트. 절삭 지점(4곳: 조퇴외출공제/기본급/정액급식비/지급총액,
모두 10원 단위 - core/payroll.py 참고)은 바꾸지 않고, 이미 계산된 값을
사람이 엑셀에서 셀 단위로 추적 검증할 수 있게 하는 것이 목적이다.
실출근일수·주휴·연차 발생 여부 같은 판정 로직(core/leave_engine.py)은
분기가 많아 수식으로 옮기지 않고 입력값 그대로 보여준다."""
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

SHEET_NAME = "산정근거(수식)"
HEADER_ROW = 1
DATA_START_ROW = 2

COL = {
    "seq": 1, "name": 2,
    "hourly_wage": 3, "total_days": 4, "late_out_minutes": 5, "weekly_holiday_days": 6,
    "meal_allowance_rate": 7, "calendar_month_days": 8, "meal_eligible_days": 9,
    "remaining_leave_days": 10, "is_final_month": 11,
    "daily_wage": 12, "daily_meal": 13, "gross_pay": 14, "late_out_deduction": 15,
    "base_pay": 16, "weekly_holiday_pay": 17, "meal_allowance": 18, "leave_compensation": 19,
    "total_payment": 20, "retro_adjustment": 21, "final_payment": 22,
}

HEADERS = {
    "seq": "순번", "name": "성명", "hourly_wage": "시급", "total_days": "계(일)",
    "late_out_minutes": "조퇴외출(분)", "weekly_holiday_days": "주휴(일)",
    "meal_allowance_rate": "월식대", "calendar_month_days": "월력상",
    "meal_eligible_days": "식대해당일", "remaining_leave_days": "잔여연가(일)",
    "is_final_month": "최종월여부", "daily_wage": "일급", "daily_meal": "일급식대",
    "gross_pay": "급여액", "late_out_deduction": "조퇴외출공제", "base_pay": "기본급",
    "weekly_holiday_pay": "주휴수당", "meal_allowance": "정액급식비",
    "leave_compensation": "연가보상비", "total_payment": "지급총액",
    "retro_adjustment": "소급조정액", "final_payment": "최종지급액",
}


def _addr(row, key):
    return f"{get_column_letter(COL[key])}{row}"


def _write_headers(ws):
    for key, col in COL.items():
        cell = ws.cell(row=HEADER_ROW, column=col, value=HEADERS[key])
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(col)].width = 12


def build_evidence_sheet(wb, results, config, retro_adjustments=None):
    """results: list[PayrollResult]. retro_adjustments: dict[person_key, int]."""
    from core.parser import person_key

    retro_adjustments = retro_adjustments or {}
    ws = wb.create_sheet(SHEET_NAME)
    _write_headers(ws)

    row = DATA_START_ROW
    for i, r in enumerate(results, start=1):
        ws.cell(row=row, column=COL["seq"], value=i)
        ws.cell(row=row, column=COL["name"], value=r.name)

        # 입력값(고정값): 이미 파이썬에서 계산된 값을 그대로 적어 넣는다.
        ws.cell(row=row, column=COL["hourly_wage"], value=config.hourly_wage_for(r.period_start.year))
        ws.cell(row=row, column=COL["total_days"], value=r.total_days)
        ws.cell(row=row, column=COL["late_out_minutes"], value=r.late_out_minutes)
        ws.cell(row=row, column=COL["weekly_holiday_days"], value=r.weekly_holiday_days)
        ws.cell(row=row, column=COL["meal_allowance_rate"], value=config.meal_allowance_for(r.period_start.year))
        ws.cell(row=row, column=COL["calendar_month_days"], value=r.calendar_month_days)
        ws.cell(row=row, column=COL["meal_eligible_days"], value=r.meal_eligible_days)
        ws.cell(row=row, column=COL["remaining_leave_days"], value=r.remaining_leave_days)
        ws.cell(row=row, column=COL["is_final_month"], value=1 if r.is_final_month else 0)

        # 수식 셀: 같은 행의 입력값 셀을 참조하는 실제 엑셀 ROUNDDOWN 수식.
        ws.cell(row=row, column=COL["daily_wage"],
                value=f"=ROUNDDOWN({_addr(row,'hourly_wage')}*8,0)")
        ws.cell(row=row, column=COL["daily_meal"],
                value=f"=ROUNDDOWN({_addr(row,'meal_allowance_rate')}/209*8,0)")
        ws.cell(row=row, column=COL["gross_pay"],
                value=f"={_addr(row,'daily_wage')}*{_addr(row,'total_days')}")
        ws.cell(row=row, column=COL["late_out_deduction"],
                value=f"=ROUNDDOWN({_addr(row,'hourly_wage')}/60*{_addr(row,'late_out_minutes')},-1)")
        ws.cell(row=row, column=COL["base_pay"],
                value=f"=ROUNDDOWN({_addr(row,'gross_pay')}-{_addr(row,'late_out_deduction')},-1)")
        ws.cell(row=row, column=COL["weekly_holiday_pay"],
                value=f"={_addr(row,'daily_wage')}*{_addr(row,'weekly_holiday_days')}")
        ws.cell(row=row, column=COL["meal_allowance"],
                value=f"=ROUNDDOWN({_addr(row,'meal_allowance_rate')}/{_addr(row,'calendar_month_days')}*{_addr(row,'meal_eligible_days')},-1)")
        ws.cell(row=row, column=COL["leave_compensation"],
                value=(
                    f"=IF({_addr(row,'is_final_month')}=1,"
                    f"ROUNDDOWN(({_addr(row,'daily_wage')}+{_addr(row,'daily_meal')})*{_addr(row,'remaining_leave_days')},0),0)"
                ))
        ws.cell(row=row, column=COL["total_payment"],
                value=(
                    f"=ROUNDDOWN({_addr(row,'base_pay')}+{_addr(row,'weekly_holiday_pay')}"
                    f"+{_addr(row,'meal_allowance')}+{_addr(row,'leave_compensation')},-1)"
                ))

        adjustment = retro_adjustments.get(person_key(r.name, r.birth), 0)
        ws.cell(row=row, column=COL["retro_adjustment"], value=adjustment)
        ws.cell(row=row, column=COL["final_payment"],
                value=f"={_addr(row,'total_payment')}+{_addr(row,'retro_adjustment')}")

        row += 1
    return ws
```

- [ ] **Step 4: 테스트 실행해 통과 확인**

Run: `python wage_calculator/tests/test_evidence_sheet.py`
Expected: `ALL OK`

- [ ] **Step 5: 커밋**

```bash
git add wage_calculator/output/evidence_sheet.py wage_calculator/tests/test_evidence_sheet.py
git commit -m "feat: 지급내역 계산 과정을 실제 엑셀 수식으로 재현하는 산정근거 시트 추가"
```

---

### Task 10: 완전퇴사자(소급전용) 별도 워크북 (`output/departed_sheet.py`)

**Files:**
- Create: `wage_calculator/output/departed_sheet.py`
- Test: `wage_calculator/tests/test_departed_sheet.py` (create)

**Interfaces:**
- Consumes: Task 7의 `core.retroactive.DepartedRetro`
- Produces: `build_departed_sheet(wb, departed_results) -> Worksheet`, `build_departed_evidence_sheet(wb, departed_results) -> Worksheet`

- [ ] **Step 1: 실패하는 테스트 작성**

`wage_calculator/tests/test_departed_sheet.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import openpyxl
from core.retroactive import DepartedRetro
from output.departed_sheet import build_departed_sheet, build_departed_evidence_sheet, COL


def test_departed_sheet_values():
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    d = DepartedRetro(name="최도영", ssn="980126-2641395", bank="하나은행", account="111",
                       prev_recalculated=1950000, prev_paid=2000000, adjustment=-50000)
    ws = build_departed_sheet(wb, [d])

    assert ws.cell(row=2, column=COL["name"]).value == "최도영"
    assert ws.cell(row=2, column=COL["ssn"]).value == "980126-2641395"
    assert ws.cell(row=2, column=COL["prev_recalculated"]).value == 1950000
    assert ws.cell(row=2, column=COL["prev_paid"]).value == 2000000
    assert ws.cell(row=2, column=COL["adjustment"]).value == -50000
    print("OK: test_departed_sheet_values")


def test_departed_evidence_sheet_formula():
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    d = DepartedRetro(name="최도영", ssn="980126-2641395", bank="하나은행", account="111",
                       prev_recalculated=1950000, prev_paid=2000000, adjustment=-50000)
    ws = build_departed_evidence_sheet(wb, [d])

    assert ws.cell(row=2, column=3).value == 1950000  # 전월재계산액
    assert ws.cell(row=2, column=4).value == 2000000  # 전월실지급액
    assert ws.cell(row=2, column=5).value == "=C2-D2"
    print("OK: test_departed_evidence_sheet_formula")


if __name__ == "__main__":
    test_departed_sheet_values()
    test_departed_evidence_sheet_formula()
    print("ALL OK")
```

- [ ] **Step 2: 테스트 실행해 실패 확인**

Run: `python wage_calculator/tests/test_departed_sheet.py`
Expected: `ModuleNotFoundError: No module named 'output.departed_sheet'`

- [ ] **Step 3: `departed_sheet.py` 생성**

`wage_calculator/output/departed_sheet.py`:

```python
"""5.7절: 당월 A파일에는 없지만(완전퇴사) 소급조정이 발생한 사람의 내역을
당월 계산 결과와 별도 워크북으로 출력하는 시트 2종."""
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

SHEET_NAME = "소급대상자 내역"
EVIDENCE_SHEET_NAME = "산정근거(수식)"
DATA_START_ROW = 2

COL = {
    "seq": 1, "name": 2, "ssn": 3, "bank": 4, "account": 5,
    "prev_recalculated": 6, "prev_paid": 7, "adjustment": 8,
}

HEADERS = {
    "seq": "순번", "name": "성명", "ssn": "주민번호", "bank": "거래은행", "account": "계좌번호",
    "prev_recalculated": "전월재계산액", "prev_paid": "전월실지급액",
    "adjustment": "소급조정액(최종지급액)",
}

EVIDENCE_COL = {"seq": 1, "name": 2, "prev_recalculated": 3, "prev_paid": 4, "adjustment": 5}
EVIDENCE_HEADERS = {
    "seq": "순번", "name": "성명", "prev_recalculated": "전월재계산액",
    "prev_paid": "전월실지급액", "adjustment": "소급조정액(=전월재계산액-전월실지급액)",
}


def build_departed_sheet(wb, departed_results):
    """departed_results: list[core.retroactive.DepartedRetro]"""
    ws = wb.create_sheet(SHEET_NAME)
    for key, col in COL.items():
        cell = ws.cell(row=1, column=col, value=HEADERS[key])
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(col)].width = 16

    row = DATA_START_ROW
    for i, d in enumerate(departed_results, start=1):
        ws.cell(row=row, column=COL["seq"], value=i)
        ws.cell(row=row, column=COL["name"], value=d.name)
        ws.cell(row=row, column=COL["ssn"], value=d.ssn)
        ws.cell(row=row, column=COL["bank"], value=d.bank)
        ws.cell(row=row, column=COL["account"], value=d.account)
        ws.cell(row=row, column=COL["prev_recalculated"], value=d.prev_recalculated)
        ws.cell(row=row, column=COL["prev_paid"], value=d.prev_paid)
        ws.cell(row=row, column=COL["adjustment"], value=d.adjustment)
        row += 1
    return ws


def build_departed_evidence_sheet(wb, departed_results):
    """§6.3: 소급조정액=최종지급액이므로 지급총액 관련 행은 생략하고
    소급조정액 수식(=전월재계산액-전월실지급액)만 표시하는 산정근거 시트."""
    ws = wb.create_sheet(EVIDENCE_SHEET_NAME)
    for key, col in EVIDENCE_COL.items():
        cell = ws.cell(row=1, column=col, value=EVIDENCE_HEADERS[key])
        cell.font = Font(bold=True)
        ws.column_dimensions[get_column_letter(col)].width = 16

    row = DATA_START_ROW
    for i, d in enumerate(departed_results, start=1):
        ws.cell(row=row, column=EVIDENCE_COL["seq"], value=i)
        ws.cell(row=row, column=EVIDENCE_COL["name"], value=d.name)
        ws.cell(row=row, column=EVIDENCE_COL["prev_recalculated"], value=d.prev_recalculated)
        ws.cell(row=row, column=EVIDENCE_COL["prev_paid"], value=d.prev_paid)
        recalc_addr = f"{get_column_letter(EVIDENCE_COL['prev_recalculated'])}{row}"
        paid_addr = f"{get_column_letter(EVIDENCE_COL['prev_paid'])}{row}"
        ws.cell(row=row, column=EVIDENCE_COL["adjustment"], value=f"={recalc_addr}-{paid_addr}")
        row += 1
    return ws
```

- [ ] **Step 4: 테스트 실행해 통과 확인**

Run: `python wage_calculator/tests/test_departed_sheet.py`
Expected: `ALL OK`

- [ ] **Step 5: 커밋**

```bash
git add wage_calculator/output/departed_sheet.py wage_calculator/tests/test_departed_sheet.py
git commit -m "feat: 완전퇴사 소급대상자 전용 출력 시트(값+수식근거) 추가"
```

---

### Task 11: `output/build.py` 통합

**Files:**
- Modify: `wage_calculator/output/build.py`
- Test: `wage_calculator/tests/test_build_workbook_integration.py` (create)

**Interfaces:**
- Produces: `build_workbook(results, config, giganje_rows=None, retro_adjustments=None) -> Workbook`(시그니처 변경 — `config`가 새 필수 2번째 인자), `build_departed_workbook(departed_results) -> Workbook`(신규), `departed_output_filename(year, month) -> str`(신규)

- [ ] **Step 1: 실패하는 테스트 작성**

`wage_calculator/tests/test_build_workbook_integration.py`:

```python
import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import Config
from core.payroll import PayrollResult
from core.retroactive import DepartedRetro
from output.build import build_workbook, build_departed_workbook, departed_output_filename


def _config():
    return Config({"surveys": [], "rates": {"2026": {"hourly_wage": 9820, "meal_allowance": 160000}}, "holidays": []})


def _result():
    return PayrollResult(
        name="김철수", birth="19900101", ssn="", bank="", account="", survey_name="테스트조사",
        period_start=date(2026, 7, 1), period_end=date(2026, 7, 31),
        contract_start=date(2026, 7, 1), contract_end=date(2026, 7, 31),
        daily_wage=78560, actual_workdays=23, public_leave_days=0, paid_holiday_days=0,
        absence_days=0, total_days=23, late_out_minutes=0, weekly_holiday_days=4,
        calendar_month_days=31, meal_eligible_days=31, remaining_leave_days=0.0,
        is_final_month=False, gross_pay=1806880, late_out_deduction=0, base_pay=1806880,
        weekly_holiday_pay=314240, meal_allowance=160000, leave_compensation=0,
        total_payment=2281120,
    )


def test_build_workbook_includes_wage_and_evidence_sheets():
    wb = build_workbook([_result()], _config())
    assert "임금내역(월중)" in wb.sheetnames, wb.sheetnames
    assert "산정근거(수식)" in wb.sheetnames, wb.sheetnames
    print("OK: test_build_workbook_includes_wage_and_evidence_sheets")


def test_build_departed_workbook_includes_both_sheets():
    d = DepartedRetro(name="최도영", ssn="980126-2641395", bank="", account="",
                       prev_recalculated=1950000, prev_paid=2000000, adjustment=-50000)
    wb = build_departed_workbook([d])
    assert "소급대상자 내역" in wb.sheetnames
    assert "산정근거(수식)" in wb.sheetnames
    print("OK: test_build_departed_workbook_includes_both_sheets")


def test_departed_output_filename():
    assert departed_output_filename(2026, 7) == "'26년 7월 소급대상자 내역.xlsx"
    print("OK: test_departed_output_filename")


if __name__ == "__main__":
    test_build_workbook_includes_wage_and_evidence_sheets()
    test_build_departed_workbook_includes_both_sheets()
    test_departed_output_filename()
    print("ALL OK")
```

- [ ] **Step 2: 테스트 실행해 실패 확인**

Run: `python wage_calculator/tests/test_build_workbook_integration.py`
Expected: `TypeError: build_workbook() missing 1 required positional argument: 'config'`

- [ ] **Step 3: `build.py` 전체 교체**

[`wage_calculator/output/build.py`](../../../wage_calculator/output/build.py) 전체를 아래로 교체:

```python
import openpyxl

from .wage_sheet import build_wage_sheet
from .raw_sheet import build_raw_status_sheet
from .evidence_sheet import build_evidence_sheet
from .departed_sheet import build_departed_sheet, build_departed_evidence_sheet


def output_filename(year: int, month: int) -> str:
    yy = year % 100
    return f"'{yy}년 {month}월 고용노동통계조사관 임금 내역.xlsx"


def departed_output_filename(year: int, month: int) -> str:
    yy = year % 100
    return f"'{yy}년 {month}월 소급대상자 내역.xlsx"


def build_workbook(results, config, giganje_rows=None, retro_adjustments=None):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    build_wage_sheet(wb, results, retro_adjustments=retro_adjustments)
    build_evidence_sheet(wb, results, config, retro_adjustments=retro_adjustments)
    if giganje_rows is not None:
        build_raw_status_sheet(wb, giganje_rows)
    return wb


def build_departed_workbook(departed_results):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    build_departed_sheet(wb, departed_results)
    build_departed_evidence_sheet(wb, departed_results)
    return wb
```

- [ ] **Step 4: 테스트 실행해 통과 확인**

Run: `python wage_calculator/tests/test_build_workbook_integration.py`
Expected: `ALL OK`

- [ ] **Step 5: 커밋**

```bash
git add wage_calculator/output/build.py wage_calculator/tests/test_build_workbook_integration.py
git commit -m "feat: 워크북 빌드에 산정근거 시트 통합, 소급전용 워크북 빌더 추가"
```

(이 시점에서 `wage_calculator/gui/result_screen.py`의 `_download()`는 아직 옛 시그니처(`build_workbook(results, giganje_rows)`)로 호출 중이라 깨져 있다 — Task 14에서 고친다. GUI를 이 사이에 실행하지 않는다.)

---

### Task 12: 업로드 화면에 전월 임금내역 파일(선택) 입력 추가

**Files:**
- Modify: `wage_calculator/gui/upload_screen.py`

**Interfaces:**
- Produces: `App.load_files(a_path, b_path, prev_payroll_path=None)` 호출 시 3번째 인자를 넘김(Task 13에서 `load_files` 시그니처를 맞춤)

- [ ] **Step 1: 3번째 파일 입력 행 추가**

[`wage_calculator/gui/upload_screen.py`](../../../wage_calculator/gui/upload_screen.py) 전체를 아래로 교체:

```python
"""6장-1: 파일 업로드 화면."""
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


class UploadScreen(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.a_path = tk.StringVar()
        self.b_path = tk.StringVar()
        self.prev_path = tk.StringVar()

        ttk.Label(self, text="통계조사관 임금계산", font=("", 16, "bold")).pack(pady=(30, 20))

        row1 = ttk.Frame(self)
        row1.pack(fill="x", padx=40, pady=8)
        ttk.Label(row1, text="개인정보 파일 (A)", width=18).pack(side="left")
        ttk.Entry(row1, textvariable=self.a_path, width=50).pack(side="left", padx=6)
        ttk.Button(row1, text="찾아보기", command=self._pick_a).pack(side="left")

        row2 = ttk.Frame(self)
        row2.pack(fill="x", padx=40, pady=8)
        ttk.Label(row2, text="근무상황 파일 (B)", width=18).pack(side="left")
        ttk.Entry(row2, textvariable=self.b_path, width=50).pack(side="left", padx=6)
        ttk.Button(row2, text="찾아보기", command=self._pick_b).pack(side="left")

        row3 = ttk.Frame(self)
        row3.pack(fill="x", padx=40, pady=8)
        ttk.Label(row3, text="전월 임금내역 (선택)", width=18).pack(side="left")
        ttk.Entry(row3, textvariable=self.prev_path, width=50).pack(side="left", padx=6)
        ttk.Button(row3, text="찾아보기", command=self._pick_prev).pack(side="left")
        ttk.Label(self, text="※ 비워두면 소급계산을 하지 않습니다.", foreground="gray").pack()

        ttk.Button(self, text="다음", command=self._next).pack(pady=30)

    def _pick_a(self):
        path = filedialog.askopenfilename(title="개인정보 파일 선택", filetypes=[("Excel", "*.xlsx")])
        if path:
            self.a_path.set(path)

    def _pick_b(self):
        path = filedialog.askopenfilename(title="근무상황 파일 선택", filetypes=[("Excel", "*.xlsx")])
        if path:
            self.b_path.set(path)

    def _pick_prev(self):
        path = filedialog.askopenfilename(title="전월 임금내역 파일 선택", filetypes=[("Excel", "*.xlsx")])
        if path:
            self.prev_path.set(path)

    def _next(self):
        if not self.a_path.get() or not self.b_path.get():
            messagebox.showwarning("파일 필요", "개인정보(A), 근무상황(B) 파일을 모두 선택하세요.")
            return
        try:
            self.app.load_files(self.a_path.get(), self.b_path.get(), self.prev_path.get() or None)
        except Exception as e:
            messagebox.showerror("파일 로드 오류", str(e))
            return
        self.app.after_upload()
```

- [ ] **Step 2: 커밋**

```bash
git add wage_calculator/gui/upload_screen.py
git commit -m "feat: 업로드 화면에 전월 임금내역 파일(선택, 소급계산용) 입력 추가"
```

(이 태스크만으로는 앱이 완전히 동작하지 않는다 — `App.load_files`가 아직 옛 시그니처라 Task 13에서 맞춘다. GUI를 이 사이에 실행하지 않는다.)

---

### Task 13: `app.py` 소급계산 플로우 연동

**Files:**
- Modify: `wage_calculator/gui/app.py`

**Interfaces:**
- Consumes: Task 5의 `parser.load_previous_payroll`, Task 7의 `retroactive.compute_retroactive`, Task 4의 `date_utils.previous_month`
- Produces: `App.previous_payroll: dict`, `App.retro_adjustments: dict`, `App.departed_results: list` (모두 `__init__`/`reset()`에서 초기화, `run_calculation()`에서 채워짐)

- [ ] **Step 1: 임포트 추가**

[`wage_calculator/gui/app.py`](../../../wage_calculator/gui/app.py) 상단 임포트:

```python
from core.config import Config
from core.parser import build_target_people, load_employees, load_giganje_rows
from core.payroll import calc_payroll
from gui.confirm_dialog import ConfirmRunDialog, ContractPeriodCheckDialog
from gui.evidence_screen import EvidenceScreen
from gui.result_screen import ResultScreen
from gui.settings_dialog import SettingsDialog
from gui.special_leave_screen import SpecialLeaveScreen, collect_pending_groups
from gui.target_screen import TargetScreen
from gui.upload_screen import UploadScreen
```

를 아래로 교체:

```python
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
```

- [ ] **Step 2: `__init__`/`reset()`에 새 상태 필드 추가**

`__init__`의:
```python
        self.config_obj = Config.load()
        self.employees = {}
        self.giganje_rows = []
        self.people = {}
        self.missing_names = []
        self.ambiguous_names = []
        self.work_year = None
        self.work_month = None
        self.results = []
```

를:

```python
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
```

`reset()`도 동일하게 세 줄 추가(기존 `reset()` 본문 끝, `self.show_upload_screen()` 호출 전):

```python
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
```

- [ ] **Step 3: `load_files` 시그니처 확장**

```python
    def load_files(self, a_path, b_path):
        self.employees = load_employees(a_path)
        self.giganje_rows = load_giganje_rows(b_path)
        self.people, self.missing_names, self.ambiguous_names = build_target_people(
            self.giganje_rows, self.employees
        )
```

를:

```python
    def load_files(self, a_path, b_path, prev_payroll_path=None):
        self.employees = load_employees(a_path)
        self.giganje_rows = load_giganje_rows(b_path)
        self.people, self.missing_names, self.ambiguous_names = build_target_people(
            self.giganje_rows, self.employees
        )
        self.previous_payroll = load_previous_payroll(prev_payroll_path) if prev_payroll_path else {}
```

- [ ] **Step 4: `run_calculation`에 소급계산 연동**

```python
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
```

를:

```python
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
```

- [ ] **Step 5: 회귀 테스트 실행**

```bash
python wage_calculator/tests/test_end_to_end_v3.py
```
Expected: `ALL OK`(이 테스트는 `App`을 안 쓰고 core 함수만 직접 호출하므로 이 변경으로 깨질 이유는 없음 — 문법 오류만 없는지 확인하는 용도)

- [ ] **Step 6: 커밋**

```bash
git add wage_calculator/gui/app.py
git commit -m "feat: 앱 상태/계산 플로우에 소급계산(전월 재계산+완전퇴사자 처리) 연동"
```

---

### Task 14: 결과화면 다운로드가 파일 1~2개 자동 저장

**Files:**
- Modify: `wage_calculator/gui/result_screen.py`

**Interfaces:**
- Consumes: Task 11의 `build_workbook(results, config, giganje_rows=None, retro_adjustments=None)`, `build_departed_workbook(departed_results)`, `departed_output_filename(year, month)`

- [ ] **Step 1: `_download` 교체**

[`wage_calculator/gui/result_screen.py`](../../../wage_calculator/gui/result_screen.py) 상단 임포트:

```python
from output.build import build_workbook, output_filename
```

를:

```python
from output.build import build_workbook, build_departed_workbook, output_filename, departed_output_filename
```

로 교체.

`_download` 메서드:

```python
    def _download(self):
        wb = build_workbook(self.app.results, self.app.giganje_rows)
        filename = output_filename(self.app.work_year, self.app.work_month)
        path = Path(downloads_dir()) / filename
        wb.save(path)
        messagebox.showinfo("저장 완료", f"저장되었습니다:\n{path}")
```

를:

```python
    def _download(self):
        wb = build_workbook(
            self.app.results, self.app.config_obj,
            giganje_rows=self.app.giganje_rows,
            retro_adjustments=self.app.retro_adjustments,
        )
        filename = output_filename(self.app.work_year, self.app.work_month)
        path = Path(downloads_dir()) / filename
        wb.save(path)
        saved = [str(path)]

        if self.app.departed_results:
            departed_wb = build_departed_workbook(self.app.departed_results)
            departed_path = Path(downloads_dir()) / departed_output_filename(self.app.work_year, self.app.work_month)
            departed_wb.save(departed_path)
            saved.append(str(departed_path))

        messagebox.showinfo("저장 완료", "저장되었습니다:\n" + "\n".join(saved))
```

- [ ] **Step 2: 수동 확인 (소급 없이)**

```bash
python wage_calculator/main.py
```
1. 전월 임금내역 파일란을 비운 채 A/B파일만 업로드 → 끝까지 계산 → 엑셀 다운로드.
2. 저장 완료 메시지에 파일 1개 경로만 뜨는지 확인.
3. 저장된 파일을 열어 "임금내역(월중)" 시트에 소급조정액(0)/최종지급액(=지급총액) 열이 있는지, "산정근거(수식)" 시트가 있고 셀을 클릭하면 수식이 보이는지 확인.

- [ ] **Step 3: 수동 확인 (소급 있음, 완전퇴사자 포함)**

1. Task 14-Step2에서 저장된 파일을 "전월 임금내역" 파일로 다시 업로드(같은 사람 기준 임의로 A/B파일 재구성 후 재계산)해, 소급조정액이 0이 아닌 사람이 최소 1명 생기도록 시나리오를 구성.
2. B파일에는 있지만 A파일에는 없는 이름(완전퇴사 시나리오)을 하나 만들어 재현.
3. 엑셀 다운로드 → 저장 완료 메시지에 파일 2개 경로가 뜨는지, 두 번째 파일("...소급대상자 내역.xlsx")에 "소급대상자 내역"/"산정근거(수식)" 두 시트가 있는지 확인.

- [ ] **Step 4: 커밋**

```bash
git add wage_calculator/gui/result_screen.py
git commit -m "feat: 엑셀 다운로드 시 소급 전용 대상자가 있으면 별도 파일도 함께 저장"
```

---

## 완료 후 전체 회귀 테스트

모든 태스크가 끝나면 아래를 전부 실행해 `ALL OK`인지 최종 확인한다:

```bash
python wage_calculator/tests/test_end_to_end_v3.py
python wage_calculator/tests/test_leave_engine_weekly.py
python wage_calculator/tests/test_mapping_special_leave.py
python wage_calculator/tests/test_parser_source_range.py
python wage_calculator/tests/test_parser_rank_filter_removed.py
python wage_calculator/tests/test_payroll_special_leave.py
python wage_calculator/tests/test_source_range.py
python wage_calculator/tests/test_special_leave_grouping.py
python wage_calculator/tests/test_wage_sheet_special_leave.py
python wage_calculator/tests/test_config_yearly_rates.py
python wage_calculator/tests/test_payroll_yearly_rates.py
python wage_calculator/tests/test_date_utils_birth_and_month.py
python wage_calculator/tests/test_parser_previous_payroll.py
python wage_calculator/tests/test_retroactive_current_month.py
python wage_calculator/tests/test_retroactive_departed.py
python wage_calculator/tests/test_wage_sheet_retro_columns.py
python wage_calculator/tests/test_evidence_sheet.py
python wage_calculator/tests/test_departed_sheet.py
python wage_calculator/tests/test_build_workbook_integration.py
```
