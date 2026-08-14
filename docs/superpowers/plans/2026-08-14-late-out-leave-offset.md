# 조퇴/외출/지각 연가 상계 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 조퇴/외출/지각(시간 기재 "기타") 시간을 그 사건 날짜 시점의 가용 연가 한도 내에서 연가로 상계하여, 급여 공제 대신 잔여연가(→마지막 달 연가보상비)를 줄이고, 연가 부족 시 초과분만 급여 공제하며 계산 시 팝업으로 경고한다.

**Architecture:** `leave_engine`에 계약 전체 이벤트를 날짜순으로 걷는 "연가 소진 시뮬레이터"를 추가해 각 조퇴/외출/지각 이벤트의 연가 상계분(covered)을 산출한다. `payroll.calc_payroll`은 이 상계 결과를 받아 (1) 급여 공제는 미상계분만, (2) 연가보상비는 상계분이 반영된 잔량으로 계산하고, 부족(초과) 여부를 결과에 실어 webapp이 계산 시 팝업으로 안내한다.

**Tech Stack:** Python 3(dataclass, datetime), FastAPI(webapp), pytest, 순수 JS(프론트).

## Global Constraints

- 대상 이벤트: `event.is_time_based and event.classified == "기타"` (조퇴/외출/지각). 시간 기재 병가 등 다른 time_based 이벤트는 **상계 대상 아님**(종전대로 전액 급여 공제).
- as-of 규칙: 상계는 그 사건 **날짜 시점의 양(+)의 가용 잔량** 한도 내에서만. 발생 전 사건은 상계 0.
- 부족분 처리: 연가로 못 덮은 초과분만 분단위 급여 공제.
- 소진 우선순위(같은 날짜): 발생(+480) 먼저 반영 → 명시적 연가/반일연가 → 조퇴/외출/지각.
- 명시적 연가/반일연가의 기존 동작(잔량 부족해도 그대로 차감, 음수 허용)은 유지.
- 불변: 주휴(5-1)/만근(5-3) 판정(`_worked_minutes_by_day`)은 변경 금지. 종별 매핑(`mapping.py`) 변경 금지.
- 하위호환: `leave_usage_minutes`/`build_leave_ledger`/`leave_balance_minutes_as_of`에 offset_map을 넘기지 않으면 종전과 완전히 동일하게 동작(조퇴/외출/지각 소진 0)해야 한다.
- 회귀: 기존 124개 테스트가 그대로 통과해야 한다. 조퇴/외출/지각이 없거나 가용 연가가 없는 계산은 결과가 완전히 동일해야 한다.
- 요율/설정 예시: 테스트는 `Config({"surveys": [], "rates": {"2026": {"daily_wage": 78560, "meal_allowance": 160000}}, "holidays": []})` 패턴 사용.

---

### Task 1: `leave_engine`에 상계 대상 판별 + offset 인지 usage 계산 도입

**목적:** 조퇴/외출/지각을 "연가 소진 후보"로 포함시키고, `leave_usage_minutes`가 offset_map을 통해 조퇴/외출/지각의 상계분을 사용분으로 보고할 수 있게 한다. 이 단계는 map을 넘기지 않는 한 동작 불변.

**Files:**
- Modify: `wage_calculator/core/leave_engine.py`
- Test: `wage_calculator/tests/test_leave_engine_offset_usage.py` (create)

**Interfaces:**
- Produces:
  - `_consumes_leave_candidate(event) -> bool` — 연가/반일연가 또는 (is_time_based and classified=="기타")
  - `leave_usage_minutes(event, offset_map=None) -> int` — 연가/반일연가는 종전대로, 조퇴/외출/지각은 `offset_map`이 주어졌을 때만 `offset_map.get(id(event), 0)` 반환, 아니면 0
  - `compute_monthly_leave_windows(...)`의 각 window `.usage_events`가 이제 조퇴/외출/지각도 포함

- [ ] **Step 1: Write the failing test**

`wage_calculator/tests/test_leave_engine_offset_usage.py`:

```python
import sys
from pathlib import Path
from datetime import date, time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import leave_engine
from core.models import build_event

CONTRACT_START = date(2026, 7, 1)
CONTRACT_END = date(2026, 9, 30)


def test_usage_events_now_include_late_out():
    """조퇴/외출/지각(시간 기재 '기타')도 window.usage_events에 포함되어야 한다."""
    e = build_event("지각", date(2026, 7, 6), time(9, 0), time(11, 0), 120)
    windows = leave_engine.compute_monthly_leave_windows(CONTRACT_START, CONTRACT_END, [e])
    assert e in windows[0].usage_events


def test_leave_usage_minutes_late_out_zero_without_map():
    """offset_map 없이는 조퇴/외출/지각의 사용분이 0(하위호환)."""
    e = build_event("조퇴", date(2026, 7, 6), time(17, 0), time(18, 0), 60)
    assert leave_engine.leave_usage_minutes(e) == 0


def test_leave_usage_minutes_late_out_uses_offset_map():
    """offset_map이 주어지면 그 상계분을 사용분으로 반환."""
    e = build_event("조퇴", date(2026, 7, 6), time(14, 0), time(18, 0), 240)
    assert leave_engine.leave_usage_minutes(e, {id(e): 240}) == 240


def test_leave_usage_minutes_explicit_leave_unchanged():
    """명시적 연가는 offset_map과 무관하게 종전 동작."""
    full = build_event("연가", date(2026, 7, 6))
    half = build_event("반일연가(오전)", date(2026, 7, 7))
    assert leave_engine.leave_usage_minutes(full) == 480
    assert leave_engine.leave_usage_minutes(half, {}) == 240


if __name__ == "__main__":
    test_usage_events_now_include_late_out()
    test_leave_usage_minutes_late_out_zero_without_map()
    test_leave_usage_minutes_late_out_uses_offset_map()
    test_leave_usage_minutes_explicit_leave_unchanged()
    print("ALL OK")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_leave_engine_offset_usage.py -q`
Expected: FAIL (usage_events에 조퇴 미포함 / offset_map 인자 미지원)

- [ ] **Step 3: Implement**

`leave_engine.py`에서 `leave_usage_minutes`를 교체하고 후보 판별 헬퍼를 추가:

```python
def _consumes_leave_candidate(event) -> bool:
    """연가 잔량을 소진하는 후보: 명시적 연가/반일연가 + 조퇴/외출/지각(시간 기재 '기타')."""
    if event.classified in ("연가", "반일연가"):
        return True
    return event.is_time_based and event.classified == "기타"


def leave_usage_minutes(event, offset_map=None) -> int:
    """연가(월차) 잔량에서 차감되는 분(分).
    - 연가: 시간 기재면 그 분, 아니면 480(종일)
    - 반일연가: 240
    - 조퇴/외출/지각(시간 기재 '기타'): offset_map이 주어졌을 때만 그 사건의
      연가 상계분(covered)을 반환(=연가로 덮은 만큼만 연가를 소진). offset_map이
      없으면 0(하위호환).
    """
    if event.classified == "연가":
        return event.minutes if event.is_time_based else 480
    if event.classified == "반일연가":
        return 240
    if offset_map is not None and event.is_time_based and event.classified == "기타":
        return offset_map.get(id(event), 0)
    return 0
```

그리고 `compute_monthly_leave_windows` 안의 usage 필터를 후보 기준으로 교체:

```python
        usage = [e for e in window_events if _consumes_leave_candidate(e)]
```

(기존 라인 `usage = [e for e in window_events if leave_usage_minutes(e) > 0]` 대체)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_leave_engine_offset_usage.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Run regression**

Run: `python -m pytest tests/ -q`
Expected: 128 passed (기존 124 + 신규 4)

- [ ] **Step 6: Commit**

```bash
git add wage_calculator/core/leave_engine.py wage_calculator/tests/test_leave_engine_offset_usage.py
git commit -m "feat: 연가 소진 후보에 조퇴/외출/지각 포함 + offset 인지 usage 계산"
```

---

### Task 2: `simulate_leave_consumption` (시간순 상계 시뮬레이터)

**목적:** 계약 전체 이벤트를 날짜순으로 걸으며 각 조퇴/외출/지각의 연가 상계분(covered)을 산출한다.

**Files:**
- Modify: `wage_calculator/core/leave_engine.py`
- Test: `wage_calculator/tests/test_leave_engine_simulate.py` (create)

**Interfaces:**
- Consumes: `compute_monthly_leave_windows`가 만든 windows(각 `.accrued`, `.effective_end`), `_consumes_leave_candidate`, `leave_usage_minutes`(명시적 연가용).
- Produces:
  - `simulate_leave_consumption(windows, events) -> LeaveConsumption`
  - `LeaveConsumption` dataclass: `offset_by_id: dict[int, int]`(id(event)->covered 분), `total_offset_minutes: int`

- [ ] **Step 1: Write the failing test**

`wage_calculator/tests/test_leave_engine_simulate.py`:

```python
import sys
from pathlib import Path
from datetime import date, time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import leave_engine
from core.models import build_event

# 7/1~9/30 계약: 7월 만근 -> 8/1 연가 1일(480분) 발생, 8월 만근 -> 9/1 발생
CS = date(2026, 7, 1)
CE = date(2026, 9, 30)


def _sim(events):
    windows = leave_engine.compute_monthly_leave_windows(CS, CE, events)
    return windows, leave_engine.simulate_leave_consumption(windows, events)


def test_late_out_before_accrual_not_offset():
    """발생(8/1) 전인 7/10 조퇴 4h는 가용 연가가 없어 상계 0."""
    e = build_event("조퇴", date(2026, 7, 10), time(14, 0), time(18, 0), 240)
    _, sim = _sim([e])
    assert sim.offset_by_id.get(id(e), 0) == 0
    assert sim.total_offset_minutes == 0


def test_late_out_after_accrual_offset_up_to_balance():
    """7월 만근 -> 8/1 연가 480분 발생. 8/10 조퇴 4h(240분)는 전액 상계."""
    e = build_event("지각", date(2026, 8, 10), time(9, 0), time(13, 0), 240)
    _, sim = _sim([e])
    assert sim.offset_by_id[id(e)] == 240
    assert sim.total_offset_minutes == 240


def test_late_out_shortfall_partial_offset():
    """가용 480분인데 조퇴/외출/지각 합계 600분 -> 480 상계 + 120 미상계."""
    e1 = build_event("조퇴", date(2026, 8, 10), time(13, 0), time(18, 0), 300)
    e2 = build_event("지각", date(2026, 8, 11), time(9, 0), time(14, 0), 300)
    _, sim = _sim([e1, e2])
    # 날짜순: e1(300) 먼저 480 중 300 상계, e2는 남은 180만 상계
    assert sim.offset_by_id[id(e1)] == 300
    assert sim.offset_by_id[id(e2)] == 180
    assert sim.total_offset_minutes == 480


def test_explicit_leave_consumes_before_late_out_same_pool():
    """8/1 발생 480분을, 8/5 명시적 연가(480)가 먼저 소진 -> 8/10 조퇴는 상계 0."""
    leave = build_event("연가", date(2026, 8, 5))
    late = build_event("조퇴", date(2026, 8, 10), time(14, 0), time(18, 0), 240)
    _, sim = _sim([leave, late])
    assert sim.offset_by_id.get(id(late), 0) == 0


if __name__ == "__main__":
    test_late_out_before_accrual_not_offset()
    test_late_out_after_accrual_offset_up_to_balance()
    test_late_out_shortfall_partial_offset()
    test_explicit_leave_consumes_before_late_out_same_pool()
    print("ALL OK")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_leave_engine_simulate.py -q`
Expected: FAIL (`simulate_leave_consumption` 미정의)

- [ ] **Step 3: Implement**

`leave_engine.py` 상단 import에 `timedelta`가 이미 있음. 파일에 추가:

```python
@dataclass
class LeaveConsumption:
    offset_by_id: dict = field(default_factory=dict)  # id(event) -> 연가로 상계된 분
    total_offset_minutes: int = 0


def simulate_leave_consumption(windows, events) -> LeaveConsumption:
    """계약 전체 이벤트를 날짜순으로 걸으며 조퇴/외출/지각(시간 기재 '기타')의
    연가 상계분을 산출한다.

    타임라인 항목의 정렬 키 (날짜, 종류):
      종류 0 = 발생(+480, available_from = 구간종료+1일)
      종류 1 = 명시적 연가/반일연가 소진(그대로 차감, 음수 허용)
      종류 2 = 조퇴/외출/지각 상계(그 시점 양의 잔량 한도 내에서만)
    같은 날짜면 발생 -> 명시적 연가 -> 조퇴/외출/지각 순으로 처리한다.
    """
    entries = []  # (date, kind, minutes, event_or_None)
    for w in windows:
        if w.accrued:
            entries.append((w.effective_end + timedelta(days=1), 0, 480, None))
    for e in events:
        if e.classified in ("연가", "반일연가"):
            entries.append((e.d, 1, leave_usage_minutes(e), e))
        elif e.is_time_based and e.classified == "기타":
            entries.append((e.d, 2, e.minutes, e))
    entries.sort(key=lambda x: (x[0], x[1]))

    balance = 0
    result = LeaveConsumption()
    for d, kind, minutes, e in entries:
        if kind == 0:
            balance += minutes
        elif kind == 1:
            balance -= minutes  # 명시적 연가: 잔량 부족해도 차감(기존 정책, 음수 허용)
        else:
            covered = min(minutes, max(balance, 0))
            result.offset_by_id[id(e)] = covered
            result.total_offset_minutes += covered
            balance -= covered
    return result
```

(`field`는 파일 상단 `from dataclasses import dataclass, field`로 이미 import됨)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_leave_engine_simulate.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add wage_calculator/core/leave_engine.py wage_calculator/tests/test_leave_engine_simulate.py
git commit -m "feat: 시간순 연가 상계 시뮬레이터 simulate_leave_consumption 추가"
```

---

### Task 3: 원장/스냅샷 잔량에 offset_map 반영

**목적:** `build_leave_ledger`와 `leave_balance_minutes_as_of`가 offset_map을 받아 조퇴/외출/지각 상계분도 사용분으로 차감하게 한다(map 미지정 시 종전과 동일).

**Files:**
- Modify: `wage_calculator/core/leave_engine.py`
- Test: `wage_calculator/tests/test_leave_engine_balance_offset.py` (create)

**Interfaces:**
- Consumes: `simulate_leave_consumption(...).offset_by_id`
- Produces:
  - `build_leave_ledger(windows, offset_map=None) -> None`
  - `leave_balance_minutes_as_of(windows, as_of, offset_map=None) -> int`

- [ ] **Step 1: Write the failing test**

`wage_calculator/tests/test_leave_engine_balance_offset.py`:

```python
import sys
from pathlib import Path
from datetime import date, time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import leave_engine
from core.models import build_event

CS = date(2026, 7, 1)
CE = date(2026, 9, 30)


def test_balance_reflects_late_out_offset():
    """7월 만근 -> 8/1 480분 발생. 8/10 조퇴 4h(240) 상계 시, 8/31 시점 잔량은
    480-240=240분이어야 한다(offset_map 반영)."""
    e = build_event("조퇴", date(2026, 8, 10), time(14, 0), time(18, 0), 240)
    windows = leave_engine.compute_monthly_leave_windows(CS, CE, [e])
    sim = leave_engine.simulate_leave_consumption(windows, [e])
    balance = leave_engine.leave_balance_minutes_as_of(windows, date(2026, 8, 31), sim.offset_by_id)
    assert balance == 240


def test_balance_without_map_ignores_late_out():
    """offset_map 없이는 조퇴/외출/지각이 잔량에 영향을 주지 않아 480 그대로(하위호환)."""
    e = build_event("조퇴", date(2026, 8, 10), time(14, 0), time(18, 0), 240)
    windows = leave_engine.compute_monthly_leave_windows(CS, CE, [e])
    balance = leave_engine.leave_balance_minutes_as_of(windows, date(2026, 8, 31))
    assert balance == 480


if __name__ == "__main__":
    test_balance_reflects_late_out_offset()
    test_balance_without_map_ignores_late_out()
    print("ALL OK")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_leave_engine_balance_offset.py -q`
Expected: FAIL (offset_map 인자 미지원 / 조퇴가 잔량에서 안 빠짐)

- [ ] **Step 3: Implement**

`build_leave_ledger`와 `leave_balance_minutes_as_of`에 `offset_map=None`을 추가하고, 내부의 `leave_usage_minutes(e)` 호출을 `leave_usage_minutes(e, offset_map)`으로 바꾼다:

```python
def build_leave_ledger(windows, offset_map=None) -> None:
    accrued_minutes = 0
    used_minutes = 0
    for w in windows:
        if w.accrued:
            accrued_minutes += 480
        for e in w.usage_events:
            used_minutes += leave_usage_minutes(e, offset_map)
        w.cum_balance_minutes = accrued_minutes - used_minutes


def leave_balance_minutes_as_of(windows, as_of, offset_map=None) -> int:
    accrued_minutes = 0
    used_minutes = 0
    for w in windows:
        available_from = w.effective_end + timedelta(days=1)
        if w.accrued and available_from <= as_of:
            accrued_minutes += 480
        for e in w.usage_events:
            if e.d <= as_of:
                used_minutes += leave_usage_minutes(e, offset_map)
        if w.start > as_of:
            break
    return accrued_minutes - used_minutes
```

(docstring은 기존 것을 유지)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_leave_engine_balance_offset.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Run regression**

Run: `python -m pytest tests/ -q`
Expected: 이전 합계 + 2 passed (조퇴/연가 없는 기존 계산 불변)

- [ ] **Step 6: Commit**

```bash
git add wage_calculator/core/leave_engine.py wage_calculator/tests/test_leave_engine_balance_offset.py
git commit -m "feat: 원장/잔량 계산에 조퇴/외출/지각 상계(offset_map) 반영"
```

---

### Task 4: `payroll.calc_payroll` 통합 (급여 미공제 + 보상비 감소 + 부족 플래그)

**목적:** 상계를 실제 급여/보상비에 반영하고, 부족 정보를 결과에 담는다.

**Files:**
- Modify: `wage_calculator/core/payroll.py`
- Test: `wage_calculator/tests/test_payroll_leave_offset.py` (create)

**Interfaces:**
- Consumes: `leave_engine.simulate_leave_consumption`, offset_map 인지 `build_leave_ledger`/`leave_balance_minutes_as_of`.
- Produces: `PayrollResult`에 신규 필드
  - `leave_offset_minutes: int = 0` — 급여기간 내 조퇴/외출/지각 중 연가로 상계된 분
  - `leave_shortfall_minutes: int = 0` — 연가 부족으로 급여 공제된 조퇴/외출/지각 분
  - `leave_shortfall: bool = False`
  - `leave_offset_map: dict = field(default_factory=dict)` — id(event)->covered (증거자료 표시용, 직렬화 안 함)
  - 기존 `late_out_minutes`의 의미가 "급여 공제(=미상계) 분"으로 바뀜(조퇴외출 공제 컬럼/공제액 근거). 상계된 분은 여기서 제외된다.

- [ ] **Step 1: Write the failing test**

`wage_calculator/tests/test_payroll_leave_offset.py`:

```python
import sys
from pathlib import Path
from datetime import date, time
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import Config
from core.payroll import calc_payroll
from core.models import build_event


def _config():
    return Config({"surveys": [], "rates": {"2026": {"daily_wage": 78560, "meal_allowance": 160000}}, "holidays": []})


def _person(events, start=date(2026, 7, 1), end=date(2026, 9, 30)):
    return SimpleNamespace(
        contract_start=start, contract_end=end, events=events,
        name="테스트", birth="", ssn="", bank="", account="", survey_name="테스트조사",
    )


def _all_workdays_full_attendance(start, end, extra=None):
    """start~end 사이 평일에 대해 별도 이벤트가 없으면 만근으로 인정되므로 events는
    extra만 넣으면 된다(결근/종일공제가 없으면 그 달은 자동 만근)."""
    return list(extra or [])


def test_late_out_within_balance_not_deducted_from_salary():
    """7월 만근 -> 8/1 연가 발생. 8/10 지각 4h(240분)는 연가로 상계되어 급여 공제 0."""
    late = build_event("지각", date(2026, 8, 10), time(9, 0), time(13, 0), 240)
    r = calc_payroll(_person([late]), _config(), 2026, 8)
    assert r.leave_offset_minutes == 240
    assert r.late_out_minutes == 0          # 급여 공제분 없음
    assert r.late_out_deduction == 0
    assert r.leave_shortfall is False


def test_offset_reduces_final_month_leave_compensation():
    """마지막 달(9월) 연가보상비는 상계분(0.5일)이 빠진 잔량으로 계산된다.
    발생 2일(8/1,9/1) - 지각 0.5일 = 1.5일."""
    late = build_event("지각", date(2026, 8, 10), time(9, 0), time(13, 0), 240)
    r = calc_payroll(_person([late]), _config(), 2026, 9)
    assert abs(r.remaining_leave_days - 1.5) < 1e-9
    assert r.is_final_month
    assert r.leave_compensation > 0


def test_shortfall_deducts_excess_and_flags():
    """가용 480분인데 8월 조퇴/외출/지각 합계 600분 -> 480 상계 + 120 급여 공제 + 경고."""
    e1 = build_event("조퇴", date(2026, 8, 10), time(13, 0), time(18, 0), 300)
    e2 = build_event("지각", date(2026, 8, 11), time(9, 0), time(14, 0), 300)
    r = calc_payroll(_person([e1, e2]), _config(), 2026, 8)
    assert r.leave_offset_minutes == 480
    assert r.late_out_minutes == 120
    assert r.leave_shortfall is True
    assert r.leave_shortfall_minutes == 120
    assert r.late_out_deduction > 0


def test_no_leave_available_behaves_as_before():
    """계약 첫 달(7월), 발생 전 7/10 조퇴 4h -> 상계 0, 종전대로 전액 급여 공제."""
    late = build_event("조퇴", date(2026, 7, 10), time(14, 0), time(18, 0), 240)
    r = calc_payroll(_person([late]), _config(), 2026, 7)
    assert r.leave_offset_minutes == 0
    assert r.late_out_minutes == 240
    assert r.leave_shortfall is True
    assert r.late_out_deduction > 0


if __name__ == "__main__":
    test_late_out_within_balance_not_deducted_from_salary()
    test_offset_reduces_final_month_leave_compensation()
    test_shortfall_deducts_excess_and_flags()
    test_no_leave_available_behaves_as_before()
    print("ALL OK")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_payroll_leave_offset.py -q`
Expected: FAIL (신규 필드/상계 미구현)

- [ ] **Step 3: Implement**

`payroll.py`의 `PayrollResult`에 신규 필드 추가(기존 `special_leave_note` 아래, 기본값 필드이므로 뒤쪽에 배치). `field`가 필요하므로 상단 import 확인(`from dataclasses import dataclass, field` — 이미 있음):

```python
    leave_offset_minutes: int = 0
    leave_shortfall_minutes: int = 0
    leave_shortfall: bool = False
    leave_offset_map: dict = field(default_factory=dict)
```

`calc_payroll`의 연가/공제 계산 블록을 교체. 기존:

```python
    late_out_events = [e for e in period_events if e.is_time_based]
    late_out_minutes = sum(e.minutes for e in late_out_events)

    weekly_windows = leave_engine.compute_weekly_holiday_windows(contract_start, contract_end, person.events)
    ...
    monthly_windows = leave_engine.compute_monthly_leave_windows(contract_start, contract_end, person.events)
    leave_engine.build_leave_ledger(monthly_windows)
    balance_minutes = leave_engine.leave_balance_minutes_as_of(monthly_windows, period_end)
    remaining_leave_days = balance_minutes / 480
```

교체 후:

```python
    monthly_windows = leave_engine.compute_monthly_leave_windows(contract_start, contract_end, person.events)
    consumption = leave_engine.simulate_leave_consumption(monthly_windows, person.events)
    offset_map = consumption.offset_by_id
    leave_engine.build_leave_ledger(monthly_windows, offset_map)
    balance_minutes = leave_engine.leave_balance_minutes_as_of(monthly_windows, period_end, offset_map)
    remaining_leave_days = balance_minutes / 480

    late_out_events = [e for e in period_events if e.is_time_based]
    # 급여 공제분 = 전체 시간공제분 - 연가로 상계된 조퇴/외출/지각 분
    gita_covered = sum(
        offset_map.get(id(e), 0)
        for e in late_out_events if e.classified == "기타"
    )
    late_out_minutes = sum(e.minutes for e in late_out_events) - gita_covered
    gita_used = sum(e.minutes for e in late_out_events if e.classified == "기타")
    leave_offset_minutes = gita_covered
    leave_shortfall_minutes = gita_used - gita_covered
    leave_shortfall = leave_shortfall_minutes > 0

    weekly_windows = leave_engine.compute_weekly_holiday_windows(contract_start, contract_end, person.events)
    weekly_holiday_days = leave_engine.weekly_holidays_for_month(weekly_windows, year, month)
```

(주의: `weekly_windows`/`weekly_holiday_days` 계산 위치는 유지하되, 위처럼 monthly/consumption 계산 이후로 옮겨도 무방하다. 기존 순서를 지키려면 weekly 블록은 그대로 두고 monthly 블록만 교체해도 된다.)

`PayrollResult(...)` 생성 인자에 신규 필드를 추가:

```python
        late_out_minutes=late_out_minutes,
        ...
        leave_offset_minutes=leave_offset_minutes,
        leave_shortfall_minutes=leave_shortfall_minutes,
        leave_shortfall=leave_shortfall,
        leave_offset_map=offset_map,
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_payroll_leave_offset.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Run regression**

Run: `python -m pytest tests/ -q`
Expected: 이전 합계 + 4 passed. 실패가 있으면 해당 fixture에 "가용 연가 + 조퇴" 조합이 생겨 값이 바뀐 것 — 값 변화가 사양상 올바른지 확인 후 테스트 기대값을 갱신(예상값을 상계 반영 값으로).

- [ ] **Step 6: Commit**

```bash
git add wage_calculator/core/payroll.py wage_calculator/tests/test_payroll_leave_offset.py
git commit -m "feat: 조퇴/외출/지각 연가 상계를 급여/연가보상비에 반영 + 부족 플래그"
```

---

### Task 5: webapp 상태 — 경고 수집 + 서버 응답 + 증거자료 정합

**목적:** 계산 시 부족 인원 경고를 모아 `/api/calculate` 응답에 싣고, 증거자료 연가 원장/late_out 표시를 상계와 일관되게 만든다.

**Files:**
- Modify: `wage_calculator/webapp/state.py`
- Modify: `wage_calculator/webapp/server.py:120-123`
- Test: `wage_calculator/tests/test_webapp_state_leave_offset.py` (create)

**Interfaces:**
- Consumes: `PayrollResult.leave_shortfall`, `.leave_offset_minutes`, `.leave_shortfall_minutes`, `.leave_offset_map`.
- Produces:
  - `AppState.leave_warnings: list[str]` (run_calculation이 채움; `run_calculation`은 종전대로 errors 리스트를 반환)
  - `/api/calculate` 응답에 `"leave_warnings"` 키 추가
  - 증거자료 payload의 leave 원장이 offset_map 반영, late_out 요약에 상계/공제 분 노출

- [ ] **Step 1: Write the failing test**

`wage_calculator/tests/test_webapp_state_leave_offset.py`:

```python
import sys
from pathlib import Path
from datetime import date, time
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import Config
from core.models import build_event
from webapp.state import AppState


def _state_with_person(events):
    state = AppState()
    state.config_obj = Config({"surveys": [], "rates": {"2026": {"daily_wage": 78560, "meal_allowance": 160000}}, "holidays": []})
    state.work_year, state.work_month = 2026, 7
    p = SimpleNamespace(
        contract_start=date(2026, 7, 1), contract_end=date(2026, 9, 30), events=events,
        name="김테스트", birth="1990-01-01", ssn="", bank="", account="", survey_name="테스트조사",
    )
    state.people = {"김테스트::19900101": p}
    return state


def test_shortfall_produces_leave_warning():
    """발생 전 7/10 조퇴 4h -> 상계 불가 -> leave_warnings에 이름이 담긴다."""
    late = build_event("조퇴", date(2026, 7, 10), time(14, 0), time(18, 0), 240)
    state = _state_with_person([late])
    state.run_calculation()
    assert any("김테스트" in w for w in state.leave_warnings)


def test_no_warning_when_fully_offset():
    """가용 연가 내 상계면 경고 없음(8월 계산)."""
    late = build_event("지각", date(2026, 8, 10), time(9, 0), time(13, 0), 240)
    state = _state_with_person([late])
    state.work_month = 8
    state.run_calculation()
    assert state.leave_warnings == []


if __name__ == "__main__":
    test_shortfall_produces_leave_warning()
    test_no_warning_when_fully_offset()
    print("ALL OK")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_webapp_state_leave_offset.py -q`
Expected: FAIL (`leave_warnings` 미존재)

- [ ] **Step 3: Implement**

state.py의 `AppState.__init__`(또는 상태 초기화부)에서 `self.leave_warnings = []`를 추가한다. `run_calculation` 끝부분(`return errors` 직전)에 경고 수집을 추가:

```python
        self.leave_warnings = []
        for r in self.results:
            if getattr(r, "leave_shortfall", False):
                used_h = round((r.leave_offset_minutes + r.leave_shortfall_minutes) / 60, 2)
                offset_h = round(r.leave_offset_minutes / 60, 2)
                excess_h = round(r.leave_shortfall_minutes / 60, 2)
                self.leave_warnings.append(
                    f"{r.name}: 조퇴/외출/지각 {used_h}시간 중 {offset_h}시간은 연가로 상계, "
                    f"초과 {excess_h}시간은 급여에서 공제됩니다."
                )
        return errors
```

(`__init__`에 이미 결과/설정 필드 초기화가 있다면 그 옆에 `self.leave_warnings = []` 추가. 없으면 `run_calculation` 시작부에서 `self.leave_warnings = []`로 리셋하는 것으로 충분.)

server.py의 calculate 라우트를 수정:

```python
    @app.post("/api/calculate")
    def calculate():
        errors = state.run_calculation()
        return {"errors": errors, "leave_warnings": state.leave_warnings}
```

증거자료 정합 — state.py `evidence_for`의 leave 원장 계산에서 offset_map을 넘긴다. 해당 result의 `leave_offset_map`을 사용:

```python
        offset_map = getattr(result, "leave_offset_map", {})
        ...
        usage_text = ", ".join(
            f"{e.d.strftime('%m-%d')}:{leave_usage_minutes(e, offset_map)}" for e in w.usage_events
        )
        ...
        balance_at_row = leave_engine.leave_balance_minutes_as_of(result.monthly_windows, as_of, offset_map)
```

(기존 `leave_usage_minutes(e)` 및 `leave_balance_minutes_as_of(result.monthly_windows, as_of)` 호출을 위처럼 offset_map 인자 포함으로 교체. `late_out`/`leave_final` 섹션은 기존 유지 — `late_out` 리스트는 사건별 원분(e.minutes)을 계속 보여주고, 요약은 아래 선택 필드로 보강 가능하나 필수는 아님.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_webapp_state_leave_offset.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Run regression (전체 + 서버/증거자료)**

Run: `python -m pytest tests/ -q`
Expected: 이전 합계 + 2 passed. (`test_webapp_server_calculate_flow`의 `errors == []` 단언은 그대로 통과 — 키 추가는 무해)

- [ ] **Step 6: Commit**

```bash
git add wage_calculator/webapp/state.py wage_calculator/webapp/server.py wage_calculator/tests/test_webapp_state_leave_offset.py
git commit -m "feat: 계산 시 연가 부족 경고 수집 + 응답 노출 + 증거자료 원장 정합"
```

---

### Task 6: 프론트 — 계산 완료 시 부족 경고 팝업

**목적:** 계산 응답의 `leave_warnings`가 있으면 기존 경고 모달(`showWarning`)로 안내한다.

**Files:**
- Modify: `wage_calculator/webapp/static/js/targets.js:122-125`

**Interfaces:**
- Consumes: `/api/calculate` 응답의 `{ errors, leave_warnings }`, 기존 `showWarning(msg)` 모달.

- [ ] **Step 1: 현재 호출부 확인**

`targets.js`의 calc 실행부(122-125)는 현재:

```javascript
              const { errors } = await api.calculate();
              if (errors.length > 0) showWarning(errors.join("\n"));
              navigate("result");
```

- [ ] **Step 2: 구현 — leave_warnings를 팝업으로**

```javascript
              const { errors, leave_warnings } = await api.calculate();
              const messages = [...errors, ...(leave_warnings || [])];
              if (messages.length > 0) showWarning(messages.join("\n"));
              navigate("result");
```

(errors와 연가 부족 경고를 한 모달에 합쳐 표시. 부족 인원이 없고 오류도 없으면 팝업 없이 결과로 이동 — Global Constraints의 "부족 인원 없으면 팝업 미표시" 충족.)

- [ ] **Step 3: 수동 검증**

`/run` 스킬 또는 서버 기동 후, 발생 전 조퇴가 있는 대상자로 계산을 실행해 "조퇴/외출/지각 … 초과 …시간은 급여에서 공제됩니다." 모달이 뜨는지 확인. 부족이 없는 케이스에서는 모달이 뜨지 않는지 확인.

(주: 이 저장소에는 JS 단위 테스트 하네스가 없어 수동 검증한다. 서버측 응답에 `leave_warnings`가 실리는 것은 Task 5에서 자동 검증됨.)

- [ ] **Step 4: Commit**

```bash
git add wage_calculator/webapp/static/js/targets.js
git commit -m "feat: 계산 완료 시 연가 부족(조퇴/외출/지각 초과) 경고 팝업 표시"
```

---

### Task 7: 공휴일 유급휴일 표기 정정 (휴무일 겹침 제외)

**목적:** 관공서 공휴일 유급 보장(근로기준법 개정)은 유지하되, **휴무일(주말 등 애초 근로제공 의무 없는 날)에 겹친 공휴일은 유급휴일로 카운트하지 않도록** 산정근거 표기를 고용부 공문과 일치시킨다. 이 작업은 연가 상계와 독립적이다.

**배경(공문):** 관공서 공휴일(대체공휴일 포함)은 유급휴일이나, 휴무일 등 애초부터 근로제공이 예정되지 않은 날이 공휴일과 겹치면 그 날을 유급으로 처리하지 않는다. 현재 `paid_holiday_days = len(holidays)`는 주말 공휴일도 카운트해, 산정근거의 "유급휴일" 열이 주말 공휴일을 1일로 잡고 "실출근"을 1일 줄여 표시한다(총 지급액은 `total_days = networkdays − 결근` 이라 주말 공휴일을 애초에 포함하지 않으므로 불변). 이 태스크는 **표기만** 공문과 일치시키며 지급액은 바꾸지 않는다.

**Files:**
- Modify: `wage_calculator/core/payroll.py:73-74`
- Test: `wage_calculator/tests/test_payroll_holiday_weekday_only.py` (create)

**Interfaces:**
- Consumes: `config.holidays_in_range(start_iso, end_iso) -> list[str]`(ISO 날짜 문자열), `date_utils.parse_date`(payroll.py에 이미 import된 `date_utils`).
- Produces: 동작 변경 없음(내부 계산만). `PayrollResult.paid_holiday_days`가 평일 공휴일 수만 반영.

- [ ] **Step 1: Write the failing test**

`wage_calculator/tests/test_payroll_holiday_weekday_only.py`:

```python
import sys
from pathlib import Path
from datetime import date
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import Config
from core.payroll import calc_payroll


def _config(holidays):
    return Config({"surveys": [], "rates": {"2026": {"daily_wage": 78560, "meal_allowance": 160000}}, "holidays": holidays})


def _person():
    return SimpleNamespace(
        contract_start=date(2026, 8, 1), contract_end=date(2026, 8, 31), events=[],
        name="테스트", birth="", ssn="", bank="", account="", survey_name="테스트조사",
    )


def test_weekend_holiday_not_counted_as_paid_holiday():
    """2026-08-15는 토요일(휴무일). 유급휴일로 잡히면 안 되고 실출근도 안 줄어야 한다."""
    r = calc_payroll(_person(), _config(["2026-08-15"]), 2026, 8)
    assert r.paid_holiday_days == 0
    assert r.actual_workdays == 21   # 8월 평일 21일 전부 실출근
    assert r.total_days == 21


def test_weekday_holiday_counted_as_paid_holiday():
    """2026-08-17은 월요일(근로예정일). 유급휴일 1일로 잡히고 실출근은 20."""
    r = calc_payroll(_person(), _config(["2026-08-17"]), 2026, 8)
    assert r.paid_holiday_days == 1
    assert r.actual_workdays == 20
    assert r.total_days == 21


def test_total_pay_unchanged_by_weekend_holiday():
    """주말 공휴일 유무로 지급액(total_days 기반)은 변하지 않는다."""
    r_none = calc_payroll(_person(), _config([]), 2026, 8)
    r_sat = calc_payroll(_person(), _config(["2026-08-15"]), 2026, 8)
    assert r_none.total_days == r_sat.total_days == 21
    assert r_none.gross_pay == r_sat.gross_pay


if __name__ == "__main__":
    test_weekend_holiday_not_counted_as_paid_holiday()
    test_weekday_holiday_counted_as_paid_holiday()
    test_total_pay_unchanged_by_weekend_holiday()
    print("ALL OK")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_payroll_holiday_weekday_only.py -q`
Expected: FAIL (`test_weekend_holiday_not_counted_as_paid_holiday`에서 paid_holiday_days==1, actual_workdays==20으로 나와 단언 실패)

- [ ] **Step 3: Implement**

`payroll.py`의 기존:

```python
    holidays = config.holidays_in_range(period_start.isoformat(), period_end.isoformat())
    paid_holiday_days = len(holidays)
```

교체:

```python
    holidays = config.holidays_in_range(period_start.isoformat(), period_end.isoformat())
    # 관공서 공휴일(대체공휴일 포함)은 유급휴일이나, 휴무일(주말 등 애초 근로제공
    # 의무가 없는 날)에 겹친 공휴일은 유급휴일로 처리하지 않는다(고용부 공문).
    # 근로예정일인 평일 공휴일만 유급휴일로 카운트한다. 총 지급액은 total_days가
    # networkdays(평일) 기반이라 주말 공휴일을 애초에 포함하지 않으므로 불변이며,
    # 이 수정은 산정근거의 '유급휴일/실출근' 표기를 공문과 일치시킨다.
    paid_holiday_days = sum(
        1 for h in holidays if date_utils.parse_date(h).weekday() < 5
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_payroll_holiday_weekday_only.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Run regression**

Run: `python -m pytest tests/ -q`
Expected: 이전 합계 + 3 passed. (기존 webapp 픽스처의 "2026-08-15"(토) 공휴일은 paid_holiday_days 값을 단언하지 않으므로 회귀 없음. 만약 어떤 테스트가 깨지면 그 테스트가 주말 공휴일을 유급휴일로 기대하던 것 — 공문에 맞게 기대값을 0으로 갱신.)

- [ ] **Step 6: Commit**

```bash
git add wage_calculator/core/payroll.py wage_calculator/tests/test_payroll_holiday_weekday_only.py
git commit -m "fix: 휴무일(주말)에 겹친 공휴일을 유급휴일로 카운트하지 않도록 표기 정정"
```

---

## Self-Review

**Spec coverage:**
- 규칙1 부족분만 급여 공제 → Task 2(부분 상계) + Task 4(late_out_minutes=미상계분). ✅
- 규칙2 as-of 날짜 가용분 → Task 2(시간순 walk, `max(balance,0)`). ✅
- 규칙3 부족 경고 → Task 4(플래그) + Task 5(수집/응답) + Task 6(팝업). ✅
- 연가보상비 자동 감소 → Task 3+4(offset 반영 잔량 → remaining_leave_days → leave_compensation). ✅
- 불변(주휴/만근) → 어떤 태스크도 `_worked_minutes_by_day`/`compute_weekly_holiday_windows` 판정 로직 미변경. ✅
- 원장 정합 → Task 3(build_leave_ledger/balance offset) + Task 5(증거자료 offset_map). ✅
- 입력 데이터 요건(계약 전체 커버) → 코드는 이미 `person.events` 통째 사용, 별도 배관 변경 불필요(문서화 완료). ✅
- 경고 위치=계산 시 팝업 → Task 6. ✅
- 공휴일 유급 처리(공문): 지급액은 기존에도 준수(주말 공휴일 미가산). 산정근거 '유급휴일' 표기를 평일 공휴일만 카운트하도록 정정 → Task 7. ✅ (연가 상계와 독립)

**Placeholder scan:** 모든 코드 스텝에 실제 코드/명령/기대출력 포함. TBD/TODO 없음. ✅

**Type consistency:**
- `leave_usage_minutes(event, offset_map=None)` — Task1 정의, Task3/Task5에서 동일 시그니처 사용. ✅
- `simulate_leave_consumption(windows, events) -> LeaveConsumption(offset_by_id, total_offset_minutes)` — Task2 정의, Task4에서 `.offset_by_id` 사용. ✅
- `build_leave_ledger(windows, offset_map=None)`, `leave_balance_minutes_as_of(windows, as_of, offset_map=None)` — Task3 정의, Task4/Task5에서 동일 사용. ✅
- PayrollResult 신규 필드명(`leave_offset_minutes`, `leave_shortfall_minutes`, `leave_shortfall`, `leave_offset_map`) — Task4 정의, Task5에서 동일 참조. ✅
- `late_out_minutes` 의미 변경(총분→미상계분)은 wage_sheet 표시(공제 컬럼)·late_out_deduction과 정합, 증거자료 late_out 리스트는 사건별 원분 유지. ✅

## 참고: 실행 시 유의

- Windows/PowerShell 환경. 테스트는 `wage_calculator` 디렉터리에서 `python -m pytest tests/ -q`.
- 커밋 메시지 끝에 `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` 규칙은 실행 세션에서 적용.
- 회귀 실패 시 systematic-debugging으로 근본 원인 확인 후, 사양상 올바른 값 변화면 기대값 갱신·아니면 구현 수정.
