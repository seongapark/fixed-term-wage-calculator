# 특별휴가 처리 + 공가·결근 급여 버그 수정 + 주휴수당 판정 최신화 (v3.0) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `wage_calculator`(통계조사관 임금계산 프로그램)를 v3.0으로 올리면서 (1) 종별 "특별휴가"의 유급/무급을 화면에서 건별로 확정하는 기능을 추가하고, (2) 공가/결근이 급여일수(계일) 계산에 반대로 반영되던 버그를 고치고, (3) 5-1(주휴) 판정 로직을 근로기준법 최신 행정해석에 맞게 고치고, (4) 이 모든 로직을 사람이 읽고 추적할 수 있는 참고 텍스트 문서를 만든다.

**Architecture:** 기존 `core/{mapping,models,parser,leave_engine,payroll}.py` 파이프라인(원본 행 파싱 → `LeaveEvent` → 주휴/만근 판정 → 급여 계산 → 엑셀 출력)에 손을 대되, "특별휴가"는 원본 파일만으로 유급/무급을 알 수 없으므로 파싱 시점엔 `"특별휴가_미정"`이라는 임시 분류로 통과시키고, 업로드 직후 새 GUI 화면(`SpecialLeaveScreen`)에서 사람이 건별로 확정한 뒤에야 `"유급특별휴가"`/`"무급특별휴가"`로 굳힌다. 이후 급여 계산에서는 유급 특별휴가를 공가와, 무급 특별휴가를 결근과 같은 버킷으로 합산하되, 주휴/연차 판정에서는 결근과 달리 "깨지 않는" 쪽으로 분류한다.

**Tech Stack:** Python 3, tkinter(GUI), openpyxl(엑셀 입출력), PyInstaller(exe 빌드). 외부 서버/DB 없음. pytest 미설치 — 이 프로젝트의 기존 관행(`tests/manual_check.py`)대로 `assert` 기반의 순수 스크립트를 `python3`으로 직접 실행하는 방식을 그대로 따른다.

## Global Constraints

- 근무관리 전체 단위는 1분(시간 단위 반올림 없이 분단위로 처리) — 기존 원칙 유지, 이번 작업에서 위반하지 않음
- 필요한 기능만 구현, 부수적 시나리오 대비 코딩 지양(YAGNI)
- 완전 로컬 파일 입출력만 사용(서버/DB/외부 API 없음)
- `임금내역(월중)` 시트의 열 구성·헤더·순서는 원본과 동일하게 유지(임의 변경 금지) — 특별휴가 전용 열을 새로 만들지 않음
- 이번 기능이 반영된 실행 프로그램은 버전 **3.0**으로 표기
- 설계 근거 문서: [`docs/superpowers/specs/2026-08-05-special-leave-design.md`](../specs/2026-08-05-special-leave-design.md) — 이 계획의 모든 결정은 이 스펙에서 사용자 승인을 받은 내용

---

## Task 1: Git 저장소 초기화

**Files:**
- Create: `.gitignore` (프로젝트 루트, `기간제임금/.gitignore`)

**Interfaces:** 없음(저장소 세팅만).

- [ ] **Step 1: 저장소 상태 확인**

Run: `git -C "/c/Users/seong/Desktop/기간제임금" status`
Expected: `fatal: not a git repository` (아직 저장소 아님을 확인)

- [ ] **Step 2: 저장소 초기화**

Run: `git -C "/c/Users/seong/Desktop/기간제임금" init`
Expected: `Initialized empty Git repository in .../기간제임금/.git/`

- [ ] **Step 3: `.gitignore` 작성**

```gitignore
__pycache__/
*.pyc
wage_calculator/build/
wage_calculator/dist/
config.json
*.xlsx
*.zip
*.exe
```

- [ ] **Step 4: 소스 파일만 스테이징 후 베이스라인 커밋**

Run:
```bash
git -C "/c/Users/seong/Desktop/기간제임금" add .gitignore wage_calculator docs
git -C "/c/Users/seong/Desktop/기간제임금" commit -m "$(cat <<'EOF'
chore: v3.0 작업 시작 전 현재 소스 상태 베이스라인 커밋

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```
Expected: 커밋 성공, `git status`에 `wage_calculator/**/*.py`, `*.spec`, `docs/**`가 커밋됨(엑셀/exe/zip/config.json은 `.gitignore`로 제외)

---

## Task 2: `mapping.py` — "특별휴가" 임시 분류 추가

**Files:**
- Modify: `wage_calculator/core/mapping.py`
- Test: `wage_calculator/tests/test_mapping_special_leave.py`

**Interfaces:**
- Produces: `mapping.classify("특별휴가") == "특별휴가_미정"`, `mapping.full_day_breaks("특별휴가") == False`, `mapping.full_day_weight("특별휴가") == 1.0`. 목록에 없는 다른 종별은 여전히 `ValueError`.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# wage_calculator/tests/test_mapping_special_leave.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import mapping


def test_special_leave_classifies_as_pending():
    assert mapping.classify("특별휴가") == "특별휴가_미정"
    print("OK: test_special_leave_classifies_as_pending")


def test_special_leave_does_not_break_attendance():
    assert mapping.full_day_breaks("특별휴가") is False
    print("OK: test_special_leave_does_not_break_attendance")


def test_special_leave_full_day_weight_is_one():
    assert mapping.full_day_weight("특별휴가") == 1.0
    print("OK: test_special_leave_full_day_weight_is_one")


def test_unknown_category_still_raises():
    try:
        mapping.classify("존재하지않는종별")
        raise AssertionError("ValueError가 발생했어야 함")
    except ValueError:
        print("OK: test_unknown_category_still_raises")


if __name__ == "__main__":
    test_special_leave_classifies_as_pending()
    test_special_leave_does_not_break_attendance()
    test_special_leave_full_day_weight_is_one()
    test_unknown_category_still_raises()
    print("ALL OK")
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `cd "/c/Users/seong/Desktop/기간제임금/wage_calculator" && python3 tests/test_mapping_special_leave.py`
Expected: `ValueError: 알 수 없는 종별: '특별휴가' (5-2 매핑표에 없음)` 트레이스백과 함께 종료(첫 assert에서 실패)

- [ ] **Step 3: `CATEGORY_MAP`에 항목 추가**

`wage_calculator/core/mapping.py`의 `CATEGORY_MAP` 딕셔너리 마지막 줄 뒤에 추가:

```python
CATEGORY_MAP = {
    "결근": "결근",
    "공가": "공가",
    "사망(본인 및 배우자의 조부모·외조부모)": "공가",
    "자녀돌봄휴가": "공가",
    "기타": "기타",
    "반일연가(오후)": "반일연가",
    "반일연가(오전)": "반일연가",
    "조퇴(일반병가,진단서미첨부)": "병가",
    "지각(일반병가,진단서미첨부)": "병가",
    "외출(일반병가,진단서미첨부)": "병가",
    "일반병가(진단서미첨부)": "병가",
    "연가": "연가",
    "외출(연가)": "연가",
    "조퇴(연가)": "연가",
    "일반병가(진단서첨부)": "병가",
    "지각(일반병가,진단서첨부)": "병가",
    "조퇴(일반병가,진단서첨부)": "병가",
    "외출(일반병가,진단서첨부)": "병가",
    "특별휴가": "특별휴가_미정",
}
```

(마지막 줄 `"특별휴가": "특별휴가_미정",` 한 줄만 추가하는 것 — 나머지는 기존 그대로.)

파일 상단 docstring에 한 줄 추가(선택 사항이지만 추적성을 위해 권장):

```python
"""5-2 종별 -> 분류 매핑표 (고정값) + "특별휴가"(유급/무급 미확정) 임시 분류.

...(기존 docstring 내용 그대로)...

"특별휴가"는 원본 B파일에 유급/무급 구분 없이 뭉뚱그려 찍혀 나오는 경우가 있어,
일단 "특별휴가_미정"으로 분류해 파싱을 통과시킨다. 실제 유급/무급 확정은
gui/special_leave_screen.py에서 사람이 건별로 선택한 뒤 LeaveEvent.classified를
"유급특별휴가"/"무급특별휴가"로 직접 덮어써서 이뤄진다(이 매핑표를 다시 타지 않음).
"""
```

- [ ] **Step 4: 테스트 재실행 → 통과 확인**

Run: `cd "/c/Users/seong/Desktop/기간제임금/wage_calculator" && python3 tests/test_mapping_special_leave.py`
Expected:
```
OK: test_special_leave_classifies_as_pending
OK: test_special_leave_does_not_break_attendance
OK: test_special_leave_full_day_weight_is_one
OK: test_unknown_category_still_raises
ALL OK
```

- [ ] **Step 5: 커밋**

```bash
git -C "/c/Users/seong/Desktop/기간제임금" add wage_calculator/core/mapping.py wage_calculator/tests/test_mapping_special_leave.py
git -C "/c/Users/seong/Desktop/기간제임금" commit -m "$(cat <<'EOF'
feat: 종별 "특별휴가"를 임시 분류(특별휴가_미정)로 통과시키도록 매핑표 추가

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: `models.py` / `parser.py` — `source_range` 필드 추가

원본 B파일 한 행(같은 사람의 연속 날짜 범위)에서 펼쳐진 여러 `LeaveEvent`가 같은 그룹임을 나중에(마킹 화면에서) 알아볼 수 있도록, 이벤트마다 "원본 행의 (시작일, 종료일)"을 붙여둔다.

**Files:**
- Modify: `wage_calculator/core/models.py`
- Modify: `wage_calculator/core/parser.py`
- Test: `wage_calculator/tests/test_source_range.py`

**Interfaces:**
- Produces: `LeaveEvent.source_range: tuple[date, date]`(항상 값이 있음 — 단일 날짜 항목도 `(d, d)`), `build_event(raw_category, d, time_start=None, time_end=None, minutes=0, source_range=None) -> LeaveEvent`.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# wage_calculator/tests/test_source_range.py
import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.models import build_event


def test_default_source_range_is_single_day():
    e = build_event("공가", date(2026, 7, 6))
    assert e.source_range == (date(2026, 7, 6), date(2026, 7, 6)), e.source_range
    print("OK: test_default_source_range_is_single_day")


def test_explicit_source_range_is_kept():
    e = build_event("특별휴가", date(2026, 7, 8), source_range=(date(2026, 7, 6), date(2026, 7, 10)))
    assert e.source_range == (date(2026, 7, 6), date(2026, 7, 10)), e.source_range
    print("OK: test_explicit_source_range_is_kept")


if __name__ == "__main__":
    test_default_source_range_is_single_day()
    test_explicit_source_range_is_kept()
    print("ALL OK")
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `cd "/c/Users/seong/Desktop/기간제임금/wage_calculator" && python3 tests/test_source_range.py`
Expected: `TypeError: build_event() got an unexpected keyword argument 'source_range'`

- [ ] **Step 3: `models.py` 수정**

`wage_calculator/core/models.py`의 `LeaveEvent` dataclass 마지막 필드 뒤에 추가:

```python
@dataclass
class LeaveEvent:
    """근무상황 원본 1행이 펼쳐진, 특정 하루에 대한 사건 1건."""
    raw_category: str
    classified: str          # 결근/공가/기타/반일연가/병가/연가/특별휴가_미정/유급특별휴가/무급특별휴가
    d: date
    is_time_based: bool
    time_start: Optional[time] = None
    time_end: Optional[time] = None
    minutes: int = 0          # 조퇴/지각/외출 공제 분
    day_weight: float = 1.0   # 종일 기준 일수(반일연가=0.5, 조퇴/지각/외출=0)
    breaks: bool = False      # 5-1/5-3 판정을 깨는 사유인지
    source_range: tuple = None  # (원본 B파일 행의 사용기간 시작일, 종료일) - 같은 행에서 펼쳐진 이벤트 그룹 식별용
```

`build_event` 함수 전체를 아래로 교체:

```python
def build_event(raw_category: str, d: date, time_start=None, time_end=None, minutes: int = 0, source_range=None) -> LeaveEvent:
    classified = mapping.classify(raw_category)
    # 사용시간(시분)이 실제로 기재된 행이면 종별(사유) 무관하게 시간공제 대상.
    # 기간제는 조퇴/외출/지각을 "기타"로 등록하는 경우가 있어, 종별 문자열이
    # 아니라 실제 시간값 유무로 판정해야 그런 행도 정확히 분단위 공제된다.
    time_based = time_start is not None
    weight = 0.0 if time_based else mapping.full_day_weight(raw_category)
    breaks = True if time_based else mapping.full_day_breaks(raw_category)
    return LeaveEvent(
        raw_category=raw_category,
        classified=classified,
        d=d,
        is_time_based=time_based,
        time_start=time_start,
        time_end=time_end,
        minutes=minutes if time_based else 0,
        day_weight=weight,
        breaks=breaks,
        source_range=source_range or (d, d),
    )
```

- [ ] **Step 4: 테스트 재실행 → 통과 확인**

Run: `cd "/c/Users/seong/Desktop/기간제임금/wage_calculator" && python3 tests/test_source_range.py`
Expected:
```
OK: test_default_source_range_is_single_day
OK: test_explicit_source_range_is_kept
ALL OK
```

- [ ] **Step 5: `parser.py`에서 다일(多日) 종일 항목에 `source_range` 전달**

`wage_calculator/core/parser.py`의 `build_target_people` 함수 내, 아래 블록을 찾는다:

```python
        else:
            # 종일 항목의 다일(多日) 사용기간은 근무일(월~금)만 하루로 집계.
            # 토/일이 기간 중간에 끼어도 원래 근무의무가 없던 날이라 공가/결근 등으로
            # 잡히면 실출근(NETWORKDAYS 기준) 계산과 불일치가 생기므로 주말은 제외.
            for d in date_utils.daterange(start_d, end_d):
                if d.weekday() < 5:
                    person.events.append(build_event(raw_category, d))
```

아래로 교체:

```python
        else:
            # 종일 항목의 다일(多日) 사용기간은 근무일(월~금)만 하루로 집계.
            # 토/일이 기간 중간에 끼어도 원래 근무의무가 없던 날이라 공가/결근 등으로
            # 잡히면 실출근(NETWORKDAYS 기준) 계산과 불일치가 생기므로 주말은 제외.
            # source_range=(start_d, end_d): 원본 행 전체 기간을 넘겨서, 같은 행에서
            # 펼쳐진 이벤트들이 나중에(특별휴가 마킹 화면 등에서) 한 그룹으로 묶이게 함.
            for d in date_utils.daterange(start_d, end_d):
                if d.weekday() < 5:
                    person.events.append(build_event(raw_category, d, source_range=(start_d, end_d)))
```

시간 기재분(if 분기, `build_event(raw_category, start_d, t_start, t_end, minutes)`)은 원래부터 단일 날짜라 `source_range` 기본값 `(d, d)`로 충분하므로 수정하지 않는다.

- [ ] **Step 6: 기존 수동 검증 스크립트로 회귀 확인**

Run: `cd "/c/Users/seong/Desktop/기간제임금/wage_calculator" && PYTHONIOENCODING=utf-8 python3 tests/manual_check.py`
Expected: 이전과 동일하게 에러 없이 실행되고 각 인원 요약이 출력됨(이 스크립트는 assert가 없는 출력 확인용이므로, "에러 없이 끝까지 실행됨"을 확인하는 것으로 충분)

- [ ] **Step 7: 커밋**

```bash
git -C "/c/Users/seong/Desktop/기간제임금" add wage_calculator/core/models.py wage_calculator/core/parser.py wage_calculator/tests/test_source_range.py
git -C "/c/Users/seong/Desktop/기간제임금" commit -m "$(cat <<'EOF'
feat: LeaveEvent에 source_range 추가해 원본 행 단위 그룹 식별 가능하게 함

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: `leave_engine.py` — 5-1(주휴) 판정 로직 최신화

**Files:**
- Modify: `wage_calculator/core/leave_engine.py`
- Test: `wage_calculator/tests/test_leave_engine_weekly.py`

**Interfaces:**
- Consumes: 없음(기존 `compute_weekly_holiday_windows(contract_start, contract_end, events)` 시그니처 유지)
- Produces: 동일 시그니처, 두 조건만 교체(15시간 재검증 삭제, "다음 근무 예정일" → "그 주 주휴일까지 근로관계 유지").

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# wage_calculator/tests/test_leave_engine_weekly.py
import sys
from pathlib import Path
from datetime import date, time, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import leave_engine
from core.models import build_event


def test_no_15h_reverification():
    """지각/조퇴/외출로 그 주 실근무시간 합계가 15시간 미만이어도, 결근·종일병가
    없이 매일 출근(개근)했으면 주휴가 발생해야 한다. 소정근로시간 15시간
    요건은 계약(주5일 8시간) 자체로 이미 충족되는 계약상 기준이지, 매주
    실제 근무시간으로 재검증할 대상이 아니다."""
    contract_start = date(2026, 7, 6)   # 월요일
    contract_end = date(2026, 8, 3)     # 월요일(첫 창이 계약 경계로 잘리지 않도록 충분히 김)
    events = []
    for i in range(5):
        d = contract_start + timedelta(days=i)
        # 09:00~15:45 사이 405분을 조퇴/외출로 공제 -> 실근무 75분/일, 주 합계 375분(6.25시간) < 900분(15시간)
        events.append(build_event("조퇴(연가)", d, time(9, 0), time(15, 45), 405))
    windows = leave_engine.compute_weekly_holiday_windows(contract_start, contract_end, events)
    first = windows[0]
    assert first.granted, f"15시간 미만이어도 개근이면 발생해야 하는데 미발생: {first.reason}"
    print("OK: test_no_15h_reverification")


def test_reaches_week_off_day_grants_last_week():
    """계약이 그 주 주휴일(7일 창의 명목상 종료일)까지 정확히 연장되면,
    그 다음 주 근무 예정이 없어도 주휴가 발생해야 한다
    (2021.4.7 행정해석 변경: 다음 주 근무 예정 여부는 무관)."""
    contract_start = date(2026, 7, 6)  # 월요일
    contract_end = date(2026, 7, 12)   # 일요일(이 7일 창의 나머지 마지막 날과 정확히 일치)
    windows = leave_engine.compute_weekly_holiday_windows(contract_start, contract_end, [])
    only_window = windows[0]
    assert only_window.granted, f"계약이 주휴일(일요일)까지 유지됐으면 발생해야 하는데: {only_window.reason}"
    print("OK: test_reaches_week_off_day_grants_last_week")


def test_friday_end_still_denies_last_week():
    """계약이 평소처럼 금요일(마지막 근무일)에 끝나면, 여전히 그 주는
    미발생이어야 한다(일반적인 계약 마지막 주 판정 결과는 바뀌지 않음)."""
    contract_start = date(2026, 7, 6)  # 월요일
    contract_end = date(2026, 7, 10)   # 금요일
    windows = leave_engine.compute_weekly_holiday_windows(contract_start, contract_end, [])
    only_window = windows[0]
    assert not only_window.granted, "계약이 금요일에 끝나면 그 주는 미발생이어야 함"
    assert only_window.reason == "근로관계가 그 주 주휴일까지 유지되지 않음(계약 종료로 주휴일 이전 근로관계 종료)", only_window.reason
    print("OK: test_friday_end_still_denies_last_week")


if __name__ == "__main__":
    test_no_15h_reverification()
    test_reaches_week_off_day_grants_last_week()
    test_friday_end_still_denies_last_week()
    print("ALL OK")
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `cd "/c/Users/seong/Desktop/기간제임금/wage_calculator" && PYTHONIOENCODING=utf-8 python3 tests/test_leave_engine_weekly.py`
Expected: 첫 번째 assert에서 `AssertionError: 15시간 미만이어도 개근이면 발생해야 하는데 미발생: 주 실근무시간 15시간 미만`

- [ ] **Step 3: `leave_engine.py`의 `compute_weekly_holiday_windows` 수정**

`wage_calculator/core/leave_engine.py`에서 함수 docstring과 본문을 아래로 교체:

```python
def compute_weekly_holiday_windows(contract_start: date, contract_end: date, events) -> List[WeeklyWindowResult]:
    """5-1: 계약시작일 요일 기준 7일 창을 계약기간 끝까지 반복 판정.

    주휴 발생 조건: 창의 월~금 5일이 모두 실근무(1분이라도 근무, 결근/종일병가나
    8시간 전부를 조퇴 등으로 비운 날이 없어야 함) + 근로관계가 그 주 주휴일까지
    유지(계약 종료로 창이 주휴일 이전에 잘리지 않아야 함, 2021.4.7 행정해석
    변경 반영 - 다음 주 근무 예정 여부는 무관)가 모두 만족될 때만 발생한다.
    소정근로시간 15시간 이상 요건은 계약 자체(주5일 8시간)로 이미 충족되므로
    주 단위로 재검증하지 않는다.
    """
    results = []
    idx = 1
    w_start = contract_start
    while w_start <= contract_end:
        nominal_end = w_start + timedelta(days=6)
        eff_end = min(nominal_end, contract_end)
        window_events = _events_in_range(events, w_start, eff_end)

        workdays = date_utils.networkdays(w_start, eff_end)
        absence_days = sum(e.day_weight for e in window_events if e.classified == "결근")
        public_leave_days = sum(e.day_weight for e in window_events if e.classified == "공가")
        sick_full_days = sum(
            1 for e in window_events if e.classified == "병가" and not e.is_time_based
        )

        by_day = _worked_minutes_by_day(window_events, w_start, eff_end)
        worked_days = sum(1 for m in by_day.values() if m > 0)
        reaches_week_off_day = eff_end == nominal_end

        granted = True
        reason = "발생"
        if workdays < 5:
            granted, reason = False, "근무일수 5일 미만"
        elif worked_days < 5:
            granted, reason = False, "실근무 없는 날 발생(결근·종일병가 또는 8시간 전부 공제)"
        elif not reaches_week_off_day:
            granted, reason = False, "근로관계가 그 주 주휴일까지 유지되지 않음(계약 종료로 주휴일 이전 근로관계 종료)"

        results.append(WeeklyWindowResult(
            index=idx, start=w_start, end=nominal_end, effective_end=eff_end,
            workdays=workdays, absence_days=int(absence_days),
            public_leave_days=int(public_leave_days), sick_full_days=sick_full_days,
            granted=granted, reason=reason,
            accrual_month=eff_end.month, accrual_year=eff_end.year,
        ))
        idx += 1
        w_start = w_start + timedelta(days=7)
    return results
```

(`total_worked_minutes` 변수는 삭제, `has_next_day` 변수는 `reaches_week_off_day`로 교체. `by_day`/`worked_days`/`absence_days`/`public_leave_days`/`sick_full_days`는 그대로 유지 — 다른 조건과 산정근거 표시용으로 계속 필요.)

- [ ] **Step 4: 테스트 재실행 → 통과 확인**

Run: `cd "/c/Users/seong/Desktop/기간제임금/wage_calculator" && PYTHONIOENCODING=utf-8 python3 tests/test_leave_engine_weekly.py`
Expected:
```
OK: test_no_15h_reverification
OK: test_reaches_week_off_day_grants_last_week
OK: test_friday_end_still_denies_last_week
ALL OK
```

- [ ] **Step 5: 커밋**

```bash
git -C "/c/Users/seong/Desktop/기간제임금" add wage_calculator/core/leave_engine.py wage_calculator/tests/test_leave_engine_weekly.py
git -C "/c/Users/seong/Desktop/기간제임금" commit -m "$(cat <<'EOF'
fix: 5-1 주휴 판정에서 15시간 재검증 삭제, 근로관계 존속 요건을 2021년 행정해석 기준으로 교체

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: `payroll.py` — 공가/결근 버그 수정 + 특별휴가 버킷 통합

**Files:**
- Modify: `wage_calculator/core/payroll.py`
- Test: `wage_calculator/tests/test_payroll_special_leave.py`

**Interfaces:**
- Consumes: `LeaveEvent.classified`(Task 2/3 결과 — `"공가"`, `"결근"`, `"유급특별휴가"`, `"무급특별휴가"` 등), `LeaveEvent.source_range`(Task 3)
- Produces: `PayrollResult.special_leave_events: list[LeaveEvent]`, `PayrollResult.special_leave_note: str`(예: `"특별휴가(유급) 7/20~7/21, 특별휴가(무급) 7/27"`). `total_days` 계산식 변경.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# wage_calculator/tests/test_payroll_special_leave.py
import sys
from pathlib import Path
from datetime import date
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import Config
from core.payroll import calc_payroll
from core.models import build_event, LeaveEvent


def _config():
    return Config({"surveys": [], "common": {"hourly_wage": 9820, "meal_allowance": 160000}, "holidays": []})


def _person(events):
    return SimpleNamespace(
        contract_start=date(2026, 7, 1), contract_end=date(2026, 7, 31), events=events,
        name="테스트", birth="", ssn="", bank="", account="", survey_name="테스트조사",
    )


def test_public_leave_no_longer_reduces_total_days():
    """공가 3일만 있는 달: workdays=23(2026-07 NETWORKDAYS). 버그 수정 전에는
    total_days가 20으로 깎였는데, 수정 후에는 공가가 급여에 영향을 주지
    않아야 하므로 23이어야 한다(결근 없음)."""
    events = [build_event("공가", d) for d in [date(2026, 7, 6), date(2026, 7, 7), date(2026, 7, 8)]]
    r = calc_payroll(_person(events), _config(), 2026, 7)
    assert r.total_days == 23, f"공가만 있으면 total_days가 workdays(23)와 같아야 하는데: {r.total_days}"
    print("OK: test_public_leave_no_longer_reduces_total_days")


def test_absence_reduces_total_days():
    """결근 2일만 있는 달: total_days = workdays(23) - absence_days(2) = 21이어야 한다."""
    events = [build_event("결근", d) for d in [date(2026, 7, 13), date(2026, 7, 14)]]
    r = calc_payroll(_person(events), _config(), 2026, 7)
    assert r.total_days == 21, f"결근 2일이면 total_days=21이어야 하는데: {r.total_days}"
    print("OK: test_absence_reduces_total_days")


def test_special_leave_folds_into_buckets_and_note():
    d1, d2, d3 = date(2026, 7, 6), date(2026, 7, 7), date(2026, 7, 8)   # 공가 3일
    a1, a2 = date(2026, 7, 13), date(2026, 7, 14)                       # 결근 2일
    p1, p2 = date(2026, 7, 20), date(2026, 7, 21)                       # 유급특별휴가 2일(한 그룹)
    u1 = date(2026, 7, 27)                                              # 무급특별휴가 1일

    events = [build_event("공가", d) for d in (d1, d2, d3)]
    events += [build_event("결근", d) for d in (a1, a2)]
    events += [
        LeaveEvent(raw_category="특별휴가", classified="유급특별휴가", d=d, is_time_based=False,
                   day_weight=1.0, breaks=False, source_range=(p1, p2))
        for d in (p1, p2)
    ]
    events.append(
        LeaveEvent(raw_category="특별휴가", classified="무급특별휴가", d=u1, is_time_based=False,
                   day_weight=1.0, breaks=False, source_range=(u1, u1))
    )

    r = calc_payroll(_person(events), _config(), 2026, 7)

    assert r.public_leave_days == 5, f"공가3+유급특별휴가2=5이어야 하는데: {r.public_leave_days}"
    assert r.absence_days == 3, f"결근2+무급특별휴가1=3이어야 하는데: {r.absence_days}"
    # total_days = actual_workdays + paid_holiday_days + public_leave_days
    #            = (23-5-(0+3)) + 0 + 5 = 20
    assert r.total_days == 20, f"total_days=20이어야 하는데: {r.total_days}"
    # meal_eligible_days = period_total_days(31) - absence_days(3) = 28
    assert r.meal_eligible_days == 28, f"meal_eligible_days=28이어야 하는데: {r.meal_eligible_days}"
    assert r.special_leave_note == "특별휴가(유급) 7/20~7/21, 특별휴가(무급) 7/27", r.special_leave_note
    print("OK: test_special_leave_folds_into_buckets_and_note")


if __name__ == "__main__":
    test_public_leave_no_longer_reduces_total_days()
    test_absence_reduces_total_days()
    test_special_leave_folds_into_buckets_and_note()
    print("ALL OK")
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `cd "/c/Users/seong/Desktop/기간제임금/wage_calculator" && PYTHONIOENCODING=utf-8 python3 tests/test_payroll_special_leave.py`
Expected: 첫 번째 테스트에서 `AssertionError: 공가만 있으면 total_days가 workdays(23)와 같아야 하는데: 20`

- [ ] **Step 3: `payroll.py` 수정**

`wage_calculator/core/payroll.py` 상단 import에 헬퍼 추가 없이, `calc_payroll` 함수 내부를 수정한다. 먼저 아래 블록을 찾는다:

```python
    period_events = [e for e in person.events if period_start <= e.d <= period_end]

    public_leave_days = sum(e.day_weight for e in period_events if e.classified == "공가")
    absence_days = sum(e.day_weight for e in period_events if e.classified == "결근")

    holidays = config.holidays_in_range(period_start.isoformat(), period_end.isoformat())
    paid_holiday_days = len(holidays)

    workdays = date_utils.networkdays(period_start, period_end)
    actual_workdays = workdays - public_leave_days - (paid_holiday_days + absence_days)
    total_days = actual_workdays + paid_holiday_days + absence_days
```

아래로 교체:

```python
    period_events = [e for e in person.events if period_start <= e.d <= period_end]

    public_leave_days = sum(e.day_weight for e in period_events if e.classified in ("공가", "유급특별휴가"))
    absence_days = sum(e.day_weight for e in period_events if e.classified in ("결근", "무급특별휴가"))
    special_leave_events = [e for e in period_events if e.classified in ("유급특별휴가", "무급특별휴가")]

    holidays = config.holidays_in_range(period_start.isoformat(), period_end.isoformat())
    paid_holiday_days = len(holidays)

    workdays = date_utils.networkdays(period_start, period_end)
    actual_workdays = workdays - public_leave_days - (paid_holiday_days + absence_days)
    total_days = actual_workdays + paid_holiday_days + public_leave_days
```

다음으로, 파일 하단 `daily_meal_allowance` 함수 앞에 헬퍼 함수를 추가한다:

```python
def _format_special_leave_note(events) -> str:
    """특별휴가 이벤트 목록을 (유급/무급 구분 + 날짜) 비고 텍스트로 요약.
    같은 원본 행(source_range)에서 나온 이벤트는 한 항목으로 묶는다."""
    groups = {}
    order = []
    for e in events:
        key = (e.classified, e.source_range)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(e.d)
    parts = []
    for classified, source_range in order:
        label = "유급" if classified == "유급특별휴가" else "무급"
        dates = sorted(groups[(classified, source_range)])
        start, end = dates[0], dates[-1]
        if start == end:
            date_text = f"{start.month}/{start.day}"
        else:
            date_text = f"{start.month}/{start.day}~{end.month}/{end.day}"
        parts.append(f"특별휴가({label}) {date_text}")
    return ", ".join(parts)
```

마지막으로 `PayrollResult` dataclass 끝(`late_out_events: list = field(default_factory=list)` 다음 줄)에 필드 2개를 추가:

```python
    weekly_windows: list = field(default_factory=list)
    monthly_windows: list = field(default_factory=list)
    late_out_events: list = field(default_factory=list)
    special_leave_events: list = field(default_factory=list)
    special_leave_note: str = ""
```

그리고 `calc_payroll` 함수 끝의 `return PayrollResult(...)` 호출부에 두 인자를 추가:

```python
    return PayrollResult(
        name=person.name, birth=person.birth, ssn=person.ssn, bank=person.bank, account=person.account,
        survey_name=person.survey_name or "",
        period_start=period_start, period_end=period_end,
        contract_start=contract_start, contract_end=contract_end,
        daily_wage=daily_wage,
        actual_workdays=actual_workdays, public_leave_days=public_leave_days,
        paid_holiday_days=paid_holiday_days, absence_days=absence_days,
        total_days=total_days, late_out_minutes=late_out_minutes,
        weekly_holiday_days=weekly_holiday_days, calendar_month_days=calendar_month_days,
        meal_eligible_days=meal_eligible_days, remaining_leave_days=remaining_leave_days,
        is_final_month=is_final_month,
        gross_pay=gross_pay, late_out_deduction=late_out_deduction, base_pay=base_pay,
        weekly_holiday_pay=weekly_holiday_pay, meal_allowance=meal_allowance,
        leave_compensation=leave_compensation, total_payment=total_payment,
        weekly_windows=weekly_windows, monthly_windows=monthly_windows,
        late_out_events=late_out_events,
        special_leave_events=special_leave_events,
        special_leave_note=_format_special_leave_note(special_leave_events),
    )
```

- [ ] **Step 4: 테스트 재실행 → 통과 확인**

Run: `cd "/c/Users/seong/Desktop/기간제임금/wage_calculator" && PYTHONIOENCODING=utf-8 python3 tests/test_payroll_special_leave.py`
Expected:
```
OK: test_public_leave_no_longer_reduces_total_days
OK: test_absence_reduces_total_days
OK: test_special_leave_folds_into_buckets_and_note
ALL OK
```

- [ ] **Step 5: 기존 수동 검증 스크립트로 회귀 확인**

Run: `cd "/c/Users/seong/Desktop/기간제임금/wage_calculator" && PYTHONIOENCODING=utf-8 python3 tests/manual_check.py`
Expected: 에러 없이 실행 완료(공가/결근 처리 방식이 바뀌었으니 출력되는 계/급여액 숫자는 이전 실행과 달라질 수 있음 — 이는 의도된 버그 수정 결과이므로 정상)

- [ ] **Step 6: 커밋**

```bash
git -C "/c/Users/seong/Desktop/기간제임금" add wage_calculator/core/payroll.py wage_calculator/tests/test_payroll_special_leave.py
git -C "/c/Users/seong/Desktop/기간제임금" commit -m "$(cat <<'EOF'
fix: 공가가 급여일수를 깎던 버그 수정(결근만 깎이도록), 유급/무급 특별휴가를 공가/결근 버킷에 통합

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: `gui/special_leave_screen.py` — 특별휴가 마킹 화면 (신규)

**Files:**
- Create: `wage_calculator/gui/special_leave_screen.py`
- Test: `wage_calculator/tests/test_special_leave_grouping.py`

**Interfaces:**
- Consumes: `app.people: dict[str, TargetPerson]`(각 `TargetPerson.events: list[LeaveEvent]`), `app.giganje_rows: list[dict]`(사유/비고 힌트 조회용)
- Produces: `collect_pending_groups(people: dict) -> list[dict]`(순수 함수, GUI 없이 테스트 가능). 각 그룹 dict: `{"person_key", "person_name", "start", "end", "events", "status"}` (`status`는 `None`/`"유급특별휴가"`/`"무급특별휴가"`). `class SpecialLeaveScreen(ttk.Frame)` — `__init__(self, master, app)`, 확정 시 `app.show_target_screen()` 호출.

- [ ] **Step 1: 실패하는 테스트 작성 (순수 함수 부분만)**

```python
# wage_calculator/tests/test_special_leave_grouping.py
import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.models import TargetPerson, LeaveEvent
from gui.special_leave_screen import collect_pending_groups


def test_same_source_range_merges_into_one_group():
    d1, d2 = date(2026, 7, 20), date(2026, 7, 21)
    events = [
        LeaveEvent(raw_category="특별휴가", classified="특별휴가_미정", d=d1, is_time_based=False,
                   day_weight=1.0, breaks=False, source_range=(d1, d2)),
        LeaveEvent(raw_category="특별휴가", classified="특별휴가_미정", d=d2, is_time_based=False,
                   day_weight=1.0, breaks=False, source_range=(d1, d2)),
        LeaveEvent(raw_category="공가", classified="공가", d=d1, is_time_based=False,
                   day_weight=1.0, breaks=False, source_range=(d1, d1)),
    ]
    person = TargetPerson(name="홍길동", events=events)
    groups = collect_pending_groups({"홍길동::": person})
    assert len(groups) == 1, f"공가는 제외, 특별휴가 2건은 한 그룹: {groups}"
    assert len(groups[0]["events"]) == 2
    assert groups[0]["start"] == d1 and groups[0]["end"] == d2
    assert groups[0]["status"] is None
    print("OK: test_same_source_range_merges_into_one_group")


def test_different_source_range_forms_separate_groups():
    d1 = date(2026, 7, 20)
    d2 = date(2026, 7, 27)
    events = [
        LeaveEvent(raw_category="특별휴가", classified="특별휴가_미정", d=d1, is_time_based=False,
                   day_weight=1.0, breaks=False, source_range=(d1, d1)),
        LeaveEvent(raw_category="특별휴가", classified="특별휴가_미정", d=d2, is_time_based=False,
                   day_weight=1.0, breaks=False, source_range=(d2, d2)),
    ]
    person = TargetPerson(name="홍길동", events=events)
    groups = collect_pending_groups({"홍길동::": person})
    assert len(groups) == 2, groups
    print("OK: test_different_source_range_forms_separate_groups")


def test_no_pending_events_returns_empty():
    events = [LeaveEvent(raw_category="공가", classified="공가", d=date(2026, 7, 1),
                          is_time_based=False, day_weight=1.0, breaks=False, source_range=(date(2026, 7, 1), date(2026, 7, 1)))]
    person = TargetPerson(name="홍길동", events=events)
    groups = collect_pending_groups({"홍길동::": person})
    assert groups == []
    print("OK: test_no_pending_events_returns_empty")


if __name__ == "__main__":
    test_same_source_range_merges_into_one_group()
    test_different_source_range_forms_separate_groups()
    test_no_pending_events_returns_empty()
    print("ALL OK")
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `cd "/c/Users/seong/Desktop/기간제임금/wage_calculator" && PYTHONIOENCODING=utf-8 python3 tests/test_special_leave_grouping.py`
Expected: `ModuleNotFoundError: No module named 'gui.special_leave_screen'`

- [ ] **Step 3: `special_leave_screen.py` 작성**

```python
# wage_calculator/gui/special_leave_screen.py
"""특별휴가(유급/무급) 마킹 화면.

원본 B파일 종별이 "특별휴가"로만 기록되어 유급/무급을 구분할 수 없는 건을
파일 업로드 직후 화면에서 사람이 직접 건별(원본 행 단위)로 선택하게 한다.
선택이 끝나야 대상자 확인 화면으로 진행할 수 있다.
"""
import tkinter as tk
from tkinter import messagebox, ttk

from core import date_utils


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

        columns = ("name", "period", "reason", "note", "status")
        headers = {"name": "성명", "period": "기간", "reason": "사유(원본)", "note": "비고(원본)", "status": "유급/무급"}
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=14)
        for c in columns:
            self.tree.heading(c, text=headers[c])
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
        all_decided = all(g["status"] is not None for g in self.groups)
        self.next_btn.config(state="normal" if all_decided else "disabled")

    def _on_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region != "cell":
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
```

- [ ] **Step 4: 테스트 재실행 → 통과 확인**

Run: `cd "/c/Users/seong/Desktop/기간제임금/wage_calculator" && PYTHONIOENCODING=utf-8 python3 tests/test_special_leave_grouping.py`
Expected:
```
OK: test_same_source_range_merges_into_one_group
OK: test_different_source_range_forms_separate_groups
OK: test_no_pending_events_returns_empty
ALL OK
```

- [ ] **Step 5: import 스모크 확인(문법 오류 없는지)**

Run: `cd "/c/Users/seong/Desktop/기간제임금/wage_calculator" && python3 -c "from gui.special_leave_screen import SpecialLeaveScreen, collect_pending_groups; print('import OK')"`
Expected: `import OK`

- [ ] **Step 6: 커밋**

```bash
git -C "/c/Users/seong/Desktop/기간제임금" add wage_calculator/gui/special_leave_screen.py wage_calculator/tests/test_special_leave_grouping.py
git -C "/c/Users/seong/Desktop/기간제임금" commit -m "$(cat <<'EOF'
feat: 특별휴가 유급/무급 건별 확인 화면(SpecialLeaveScreen) 추가

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: `gui/app.py`, `gui/upload_screen.py` — 라우팅 연결 + 버전 타이틀 v3.0

**Files:**
- Modify: `wage_calculator/gui/app.py`
- Modify: `wage_calculator/gui/upload_screen.py`

**Interfaces:**
- Consumes: `special_leave_screen.collect_pending_groups`, `special_leave_screen.SpecialLeaveScreen`(Task 6)
- Produces: `App.after_upload()`, `App.show_special_leave_screen()`

- [ ] **Step 1: `app.py` 수정 — import 및 라우팅 메서드 추가**

`wage_calculator/gui/app.py` 상단 import 블록:

```python
from gui.confirm_dialog import ConfirmRunDialog
from gui.evidence_screen import EvidenceScreen
from gui.result_screen import ResultScreen
from gui.settings_dialog import SettingsDialog
from gui.special_leave_screen import SpecialLeaveScreen, collect_pending_groups
from gui.target_screen import TargetScreen
from gui.upload_screen import UploadScreen
```

`self.title("통계조사관 임금계산 v2.2")`를 아래로 교체:

```python
        self.title("통계조사관 임금계산 v3.0")
```

`show_target_screen` 메서드 바로 앞에 새 메서드 추가:

```python
    def after_upload(self):
        if collect_pending_groups(self.people):
            self.show_special_leave_screen()
        else:
            self.show_target_screen()

    def show_special_leave_screen(self):
        self._set_screen(SpecialLeaveScreen(self.container, self))

```

- [ ] **Step 2: `upload_screen.py` 수정 — 라우팅 호출 변경**

`wage_calculator/gui/upload_screen.py`의 `_next` 메서드 마지막 줄:

```python
        self.app.show_target_screen()
```

아래로 교체:

```python
        self.app.after_upload()
```

- [ ] **Step 3: import 스모크 확인**

Run: `cd "/c/Users/seong/Desktop/기간제임금/wage_calculator" && python3 -c "from gui.app import App; print('import OK')"`
Expected: `import OK`

- [ ] **Step 4: 커밋**

```bash
git -C "/c/Users/seong/Desktop/기간제임금" add wage_calculator/gui/app.py wage_calculator/gui/upload_screen.py
git -C "/c/Users/seong/Desktop/기간제임금" commit -m "$(cat <<'EOF'
feat: 업로드 직후 특별휴가 미정 건이 있으면 마킹 화면으로 라우팅, 타이틀 v3.0으로 변경

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: `output/wage_sheet.py` — 비고란 자동 기재 + 헤더 코멘트

**Files:**
- Modify: `wage_calculator/output/wage_sheet.py`
- Test: `wage_calculator/tests/test_wage_sheet_special_leave.py`

**Interfaces:**
- Consumes: `PayrollResult.special_leave_note`(Task 5)
- Produces: 비고(AC)열에 `special_leave_note` 값 기재, H3·J3 헤더 셀에 openpyxl 코멘트 부착.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# wage_calculator/tests/test_wage_sheet_special_leave.py
import sys
from pathlib import Path
from datetime import date
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import openpyxl
from core.config import Config
from core.payroll import calc_payroll
from core.models import LeaveEvent
from output.wage_sheet import build_wage_sheet


def test_note_column_and_header_comments():
    p1, p2 = date(2026, 7, 20), date(2026, 7, 21)
    u1 = date(2026, 7, 27)
    events = [
        LeaveEvent(raw_category="특별휴가", classified="유급특별휴가", d=d, is_time_based=False,
                   day_weight=1.0, breaks=False, source_range=(p1, p2))
        for d in (p1, p2)
    ]
    events.append(
        LeaveEvent(raw_category="특별휴가", classified="무급특별휴가", d=u1, is_time_based=False,
                   day_weight=1.0, breaks=False, source_range=(u1, u1))
    )
    person = SimpleNamespace(
        contract_start=date(2026, 7, 1), contract_end=date(2026, 7, 31), events=events,
        name="테스트", birth="", ssn="", bank="", account="", survey_name="테스트조사",
    )
    config = Config({"surveys": [], "common": {"hourly_wage": 9820, "meal_allowance": 160000}, "holidays": []})
    result = calc_payroll(person, config, 2026, 7)

    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    ws = build_wage_sheet(wb, [result])

    assert ws["AC4"].value == "특별휴가(유급) 7/20~7/21, 특별휴가(무급) 7/27", ws["AC4"].value
    assert ws["H3"].comment is not None, "H3(공가)에 코멘트가 없음"
    assert "유급 특별휴가" in ws["H3"].comment.text, ws["H3"].comment.text
    assert ws["J3"].comment is not None, "J3(결근)에 코멘트가 없음"
    assert "무급 특별휴가" in ws["J3"].comment.text, ws["J3"].comment.text
    print("OK: test_note_column_and_header_comments")


if __name__ == "__main__":
    test_note_column_and_header_comments()
    print("ALL OK")
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `cd "/c/Users/seong/Desktop/기간제임금/wage_calculator" && PYTHONIOENCODING=utf-8 python3 tests/test_wage_sheet_special_leave.py`
Expected: `AssertionError: ` (AC4 값이 빈 문자열이라 기대값과 다름)

- [ ] **Step 3: `wage_sheet.py` 수정**

파일 상단 import에 추가:

```python
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font
```

(기존 `from openpyxl.styles import Alignment, Font` 줄이 이미 있으므로, 그 줄 위에 `from openpyxl.comments import Comment`만 추가.)

`_write_headers` 함수 마지막(`for col in range(1, 30): ...` 블록 뒤)에 추가:

```python
    ws["H3"].comment = Comment(
        "공가(일)에는 유급 특별휴가 일수가 합산되어 있습니다. 세부 날짜는 비고란 참고.",
        "임금계산 프로그램",
    )
    ws["J3"].comment = Comment(
        "(결근)에는 무급 특별휴가 일수가 합산되어 있습니다. 세부 날짜는 비고란 참고.",
        "임금계산 프로그램",
    )
```

`build_wage_sheet` 함수 내, 아래 줄을 찾는다:

```python
        ws.cell(row=row, column=COL["note"], value="")
```

아래로 교체:

```python
        ws.cell(row=row, column=COL["note"], value=r.special_leave_note)
```

- [ ] **Step 4: 테스트 재실행 → 통과 확인**

Run: `cd "/c/Users/seong/Desktop/기간제임금/wage_calculator" && PYTHONIOENCODING=utf-8 python3 tests/test_wage_sheet_special_leave.py`
Expected:
```
OK: test_note_column_and_header_comments
ALL OK
```

- [ ] **Step 5: 커밋**

```bash
git -C "/c/Users/seong/Desktop/기간제임금" add wage_calculator/output/wage_sheet.py wage_calculator/tests/test_wage_sheet_special_leave.py
git -C "/c/Users/seong/Desktop/기간제임금" commit -m "$(cat <<'EOF'
feat: 임금내역 시트 비고란에 특별휴가 날짜 자동 기재, 공가/결근 헤더에 안내 코멘트 추가

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: `통계조사관임금계산.spec` — 버전 v3.0

**Files:**
- Modify: `wage_calculator/통계조사관임금계산.spec`

**Interfaces:** 없음(빌드 산출물 이름만 변경).

- [ ] **Step 1: 버전 문자열 교체**

`wage_calculator/통계조사관임금계산.spec`에서:

```python
    name='통계조사관임금계산_v2.2',
```

아래로 교체:

```python
    name='통계조사관임금계산_v3.0',
```

- [ ] **Step 2: 변경 확인**

Run: `grep -n "name=" "/c/Users/seong/Desktop/기간제임금/wage_calculator/통계조사관임금계산.spec"`
Expected: `name='통계조사관임금계산_v3.0',`

- [ ] **Step 3: 커밋**

```bash
git -C "/c/Users/seong/Desktop/기간제임금" add "wage_calculator/통계조사관임금계산.spec"
git -C "/c/Users/seong/Desktop/기간제임금" commit -m "$(cat <<'EOF'
chore: 빌드 산출물 이름을 v3.0으로 변경

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: 통합 시나리오 검증 스크립트

Task 2~8을 각각 단위로 검증했으니, 이번엔 파일 파싱부터 엑셀 출력까지 전체 파이프라인을 한 사람 기준으로 끝까지 통과시켜 확인한다(특별휴가 마킹 화면만 GUI라 스크립트에서는 건너뛰고, 그 화면이 하는 일 — `classified` 덮어쓰기 — 을 코드로 직접 흉내낸다).

**Files:**
- Test: `wage_calculator/tests/test_end_to_end_v3.py`

**Interfaces:** 없음(Task 2~8 전체를 소비하는 최종 통합 테스트).

- [ ] **Step 1: 테스트 작성**

```python
# wage_calculator/tests/test_end_to_end_v3.py
import sys
from pathlib import Path
from datetime import date
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import openpyxl
from core.config import Config
from core.parser import person_key
from core.payroll import calc_payroll
from core.models import build_event, TargetPerson
from core import leave_engine
from gui.special_leave_screen import collect_pending_groups
from output.wage_sheet import build_wage_sheet


def test_full_pipeline_with_special_leave():
    contract_start = date(2026, 7, 1)
    contract_end = date(2026, 7, 31)

    events = []
    events += [build_event("공가", d) for d in [date(2026, 7, 6), date(2026, 7, 7)]]
    events += [build_event("결근", date(2026, 7, 13))]
    # "특별휴가" 원본 종별(파싱 시점엔 유급/무급 모름) - 7/20~7/21 연속 2일
    for d in [date(2026, 7, 20), date(2026, 7, 21)]:
        events.append(build_event("특별휴가", d, source_range=(date(2026, 7, 20), date(2026, 7, 21))))

    person = TargetPerson(
        name="홍길동", birth="19900101", ssn="", bank="", account="",
        survey_name="테스트조사", contract_start=contract_start, contract_end=contract_end,
        events=events,
    )
    people = {person_key("홍길동", "19900101"): person}

    # 1) 마킹 전: "특별휴가_미정" 그룹이 하나 잡혀야 함
    groups = collect_pending_groups(people)
    assert len(groups) == 1, groups
    assert groups[0]["person_name"] == "홍길동"

    # 2) SpecialLeaveScreen._proceed()가 하는 일을 그대로 재현: 유급으로 확정
    for e in groups[0]["events"]:
        e.classified = "유급특별휴가"

    # 3) 마킹 후: 더 이상 미정 그룹이 없어야 함
    assert collect_pending_groups(people) == []

    # 4) 급여 계산
    config = Config({"surveys": [], "common": {"hourly_wage": 9820, "meal_allowance": 160000}, "holidays": []})
    result = calc_payroll(person, config, 2026, 7)

    # workdays(2026-07-01~07-31) = 23
    # public_leave_days = 공가2 + 유급특별휴가2 = 4
    # absence_days = 결근1 = 1
    # actual_workdays = 23 - 4 - (0+1) = 18
    # total_days = 18 + 0 + 4 = 22
    assert result.public_leave_days == 4, result.public_leave_days
    assert result.absence_days == 1, result.absence_days
    assert result.total_days == 22, result.total_days
    assert result.special_leave_note == "특별휴가(유급) 7/20~7/21", result.special_leave_note

    # 5) 5-1 주휴 판정에 유급특별휴가가 껴 있어도 정상적으로 발생 판정이 나와야 함
    #    (7/20 주: 월~금 중 유급특별휴가 2일 + 정상근무 3일 -> 개근 유지)
    weekly = leave_engine.compute_weekly_holiday_windows(contract_start, contract_end, person.events)
    week_of_20 = next(w for w in weekly if w.start <= date(2026, 7, 20) <= w.effective_end)
    assert week_of_20.granted, f"유급특별휴가가 껴도 주휴가 발생해야 하는데: {week_of_20.reason}"

    # 6) 엑셀 출력까지 에러 없이 완료되는지
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    ws = build_wage_sheet(wb, [result])
    assert ws["AC4"].value == "특별휴가(유급) 7/20~7/21"

    print("OK: test_full_pipeline_with_special_leave")


if __name__ == "__main__":
    test_full_pipeline_with_special_leave()
    print("ALL OK")
```

- [ ] **Step 2: 실행 → 통과 확인**

Run: `cd "/c/Users/seong/Desktop/기간제임금/wage_calculator" && PYTHONIOENCODING=utf-8 python3 tests/test_end_to_end_v3.py`
Expected:
```
OK: test_full_pipeline_with_special_leave
ALL OK
```

(만약 실패하면 Task 2~8 중 어딘가 누락된 것이므로, 실패한 assert 메시지를 보고 해당 Task로 돌아가 확인한다.)

- [ ] **Step 3: 전체 테스트 스위트 한 번에 재확인**

Run:
```bash
cd "/c/Users/seong/Desktop/기간제임금/wage_calculator" && PYTHONIOENCODING=utf-8 bash -c '
for f in tests/test_mapping_special_leave.py tests/test_source_range.py tests/test_leave_engine_weekly.py tests/test_payroll_special_leave.py tests/test_special_leave_grouping.py tests/test_wage_sheet_special_leave.py tests/test_end_to_end_v3.py; do
  echo "=== $f ===";
  python3 "$f" || exit 1;
done
'
```
Expected: 7개 파일 모두 `ALL OK`로 끝남, exit code 0

- [ ] **Step 4: 커밋**

```bash
git -C "/c/Users/seong/Desktop/기간제임금" add wage_calculator/tests/test_end_to_end_v3.py
git -C "/c/Users/seong/Desktop/기간제임금" commit -m "$(cat <<'EOF'
test: 특별휴가 마킹부터 엑셀 출력까지 전체 파이프라인 통합 검증 추가

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: 산정로직 참고문서 작성

**Files:**
- Create: `기간제임금/임금계산_로직_안내(v3.0).txt`

**Interfaces:** 없음(문서 산출물).

- [ ] **Step 1: 문서 작성**

```text
통계조사관 임금계산 프로그램 (v3.0) 산정로직 안내
====================================================

이 문서는 급여 결과를 검토하는 사람이 "이 숫자가 왜 이렇게 나왔는지"를
추적할 수 있도록, 프로그램(v3.0)이 실제로 쓰는 계산 로직을 정리한
것입니다. 버전이 올라가면서 무엇이 바뀌었는지가 아니라, 지금(v3.0) 기준으로
어떻게 동작하는지만 정리했습니다.


1. 종별(근무상황 종류)별 처리 기준
------------------------------------

결근: 무급입니다. 그 날은 일급도 정액급식비도 나오지 않습니다. 그 주의
주휴수당과 그 달의 연차(월차) 발생도 함께 깨집니다. 예를 들어 월~금 중
하루라도 결근하면 그 주는 주휴수당이 나오지 않고, 그 달의 만근 구간에
결근이 하루라도 끼면 그 구간의 연차 1일이 발생하지 않습니다.

공가(국가기관 소환, 예방접종 등 공적인 사유로 쉬는 날): 유급입니다. 그
날 일급과 정액급식비가 정상 지급됩니다. 주휴수당·연차 발생에도 전혀
영향이 없습니다 — 마치 정상 출근한 것처럼 취급됩니다.

연가(개인 사유로 쓰는 유급휴가): 유급입니다. 하루 종일 쓰면 그 날 일급이
나가는 대신 잔여 연가에서 8시간(480분)이 차감됩니다. 반일연가는
4시간(240분)만 차감됩니다. 연가를 쓴다고 해서 주휴수당이나 그 달 연차
발생이 깨지지는 않습니다.

병가(아파서 하루 종일 쉬는 경우, 진단서 첨부/미첨부 모두 포함): 급여일수
계산에는 관여하지 않지만, 주휴수당과 그 달 연차 발생을 깨뜨립니다. 예를
들어 화요일에 하루 종일 병가를 쓰면, 그 주는 5일 중 하루가 "실근무 없는
날"이 되어 주휴수당이 나오지 않습니다.

조퇴·지각·외출(시간 단위로 근무시간 일부만 쓰는 경우 — 사유가 병가든
연가든 상관없이 시간이 기재된 모든 항목): 그 시간만큼만 시급으로
공제됩니다(점심시간 12~13시와 겹치는 부분은 무급 휴게시간이라 자동으로
빠집니다). 예를 들어 09:00~11:00에 2시간 외출했다면 시급×2시간만
공제되고, 나머지는 정상 근무로 인정됩니다. 다만 단 1분이라도 이렇게
시간 단위로 자리를 비우면, 사유가 무엇이든 그 주의 주휴수당과 그 달의
연차 발생은 깨집니다 — "몇 시간만 비웠으니 괜찮다"가 아니라 "하루를
온전히 채우지 못했다"로 판단하기 때문입니다.

기타: 급여·주휴·연차 어느 쪽에도 영향을 주지 않습니다. 정상 출근한
것으로 취급됩니다.

유급휴일(설정 화면에 등록해 둔 공휴일): 급여계산기간에 포함돼 있으면
일급이 지급됩니다. 이 날은 근무상황 파일에 애초에 아무 기록도 남지
않는 게 보통이라(공휴일에 휴가를 신청하는 사람은 없으니까요), 주휴·연차
판정에서도 "정상 출근한 날"처럼 자동으로 처리됩니다. 예를 들어 어느 주의
수요일이 공휴일이라 아무도 출근하지 않았더라도, 나머지 4일을 모두
출근했다면 그 주는 만근으로 보고 주휴수당이 나갑니다.

유급 특별휴가(경조사휴가, 포상휴가 등 기관에서 유급으로 승인한 특별휴가):
공가와 완전히 동일하게 처리됩니다. 그 날 일급·정액급식비 지급,
주휴·연차 발생에는 영향 없음.

무급 특별휴가(가족돌봄휴가, 생리휴가 등 법적으로는 인정되지만 무급인
특별휴가): 그 날 일급도 정액급식비도 나오지 않습니다(급여 처리는
결근과 동일). 다만 결근과 달리 주휴수당·연차 발생에는 영향을 주지
않습니다 — 사유가 있는 정당한 휴가이기 때문입니다.

근무상황 파일에는 "특별휴가"라고만 찍혀 나오고 유급인지 무급인지 구분이
안 되는 경우가 있습니다. 이럴 때 프로그램은 파일을 불러온 직후 건별로
"유급인가요, 무급인가요?"를 화면에서 직접 물어봅니다. 이 화면에서 고른
값이 위 두 항목 중 어느 쪽으로 처리될지를 결정합니다.

임금내역 시트 표기 주의사항: 유급 특별휴가는 "공가(일)" 열 숫자에
합산되고, 무급 특별휴가는 "(결근)" 열 숫자에 합산됩니다(엑셀 서식 자체를
바꿀 수 없어서 기존 열에 얹는 방식입니다). 그 사람의 "비고" 칸에
"특별휴가(유급) 7/15"처럼 실제 날짜가 자동으로 적히니, 공가나 결근 숫자가
예상과 다르면 비고 칸을 먼저 확인하면 됩니다. "공가(일)"과 "(결근)" 헤더
칸에 마우스를 올리면 같은 안내가 메모로 뜹니다.


2. 주휴수당 발생 규칙
------------------------------------

계약 시작일의 요일을 기준으로 7일씩 창을 나눠서(예: 계약이 수요일에
시작하면 수~화가 한 창) 판정합니다. 한 창 안에서 아래 두 조건을 모두
만족해야 그 주의 주휴수당이 나옵니다.

조건 1 — 개근: 월~금 5일 중 단 하루도 "실근무 0분"인 날이 없어야
합니다. 결근이나 병가로 하루를 통째로 쉬면 그 날은 0분 처리되어
깨집니다. 반대로 조퇴·지각·외출로 시간 일부만 비웠다면(8시간을 전부
비운 게 아닌 이상) 그날은 "출근한 날"로 인정됩니다. 예: 월요일에 2시간
외출했어도 나머지 6시간을 일했으면 그날은 정상 출근으로 봅니다.

(참고: 예전에는 그 주 실제 근무시간 합계가 15시간 미만이면 미발생
처리했는데, 이 요건은 계약(주 5일 8시간 = 주 40시간) 자체로 이미
넉넉히 충족되는 것이라 v3.0부터는 매주 다시 확인하지 않습니다.
조퇴·지각·외출이 많이 몰린 주라도, 결근이나 종일 병가 없이 매일
출근만 했다면 주휴수당이 나옵니다.)

조건 2 — 근로관계가 그 주 주휴일까지 유지: 그 7일 창이 계약 종료로
도중에 잘리지 않고 끝까지(창의 마지막 날, 즉 주휴일까지) 이어져야
합니다. 계약이 보통 그렇듯 금요일(마지막 근무일)에 끝나면, 그 창은
주휴일(일요일 등)에 못 미쳐서 끝나기 때문에 그 마지막 주는 주휴수당이
나오지 않습니다. 반대로 계약 종료일이 예외적으로 그 주 주휴일까지
연장돼 있다면, 그 다음 주에 근무 예정이 없더라도(이 계약이 그걸로
끝나더라도) 주휴수당은 나옵니다 — 2021년 바뀐 행정해석(다음 주 근무
예정 여부는 안 봄)을 반영한 것입니다.

예시: 계약이 7/6(월)에 시작해서 7/10(금)에 끝나는 사람이 매일
출근했다면, 마지막 주(7/6~7/10)는 조건 2에서 막혀 주휴수당이 나오지
않습니다. 반면 같은 사람의 계약이 7/12(일)까지였다면(조건 1도 만족한다는
전제 하에) 그 주는 주휴수당이 나옵니다.


3. 정액급식비 계산식
------------------------------------

식대해당일 = 급여계산기간의 총 일수(주말 포함 달력일수) − 결근일수(무급
특별휴가 포함)

정액급식비 = 월 식대 ÷ 그 달 달력상 일수 × 식대해당일 (10원 단위 절사)

예시: 7월(31일)에 계약이 꽉 차 있고, 그 달에 결근 2일과 무급 특별휴가
1일이 있었다고 하면 — 식대해당일 = 31 − 3 = 28일. 월 식대가 160,000원이면,
160,000 ÷ 31 × 28 ≈ 144,516원인데, 10원 단위로 절사해서 144,510원이
지급됩니다.

공가, 연가, 유급 특별휴가는 이 계산에서 전혀 깎이지 않습니다(결근이
아니므로). 오직 결근과 무급 특별휴가만 식대해당일을 줄입니다.
```

- [ ] **Step 2: 문서 존재 및 내용 확인**

Run: `PYTHONIOENCODING=utf-8 grep -c "" "/c/Users/seong/Desktop/기간제임금/임금계산_로직_안내(v3.0).txt"`
Expected: 0보다 큰 줄 수 출력(파일이 비어있지 않음을 확인)

- [ ] **Step 3: 커밋 여부**

이 파일은 `.gitignore`에 걸리지 않으므로(확장자가 `.txt`) 원하면 커밋 가능:

```bash
git -C "/c/Users/seong/Desktop/기간제임금" add "임금계산_로직_안내(v3.0).txt"
git -C "/c/Users/seong/Desktop/기간제임금" commit -m "$(cat <<'EOF'
docs: v3.0 산정로직 참고문서 추가

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: PyInstaller로 v3.0 exe 빌드

**Files:** 없음(빌드 산출물만 생성) — 결과: `wage_calculator/dist/통계조사관임금계산_v3.0.exe`

**Interfaces:** 없음(최종 배포 산출물).

- [ ] **Step 1: 빌드 실행**

Run: `cd "/c/Users/seong/Desktop/기간제임금/wage_calculator" && python3 -m PyInstaller "통계조사관임금계산.spec" --noconfirm`
Expected: 마지막 줄 근처에 `INFO: Building EXE from EXE-00.toc completed successfully.` 출력, `dist/통계조사관임금계산_v3.0.exe` 생성

- [ ] **Step 2: 산출물 확인**

Run: `ls -la "/c/Users/seong/Desktop/기간제임금/wage_calculator/dist/통계조사관임금계산_v3.0.exe"`
Expected: 파일이 존재하고 크기가 0보다 큼(수십 MB대)

- [ ] **Step 3: 사용자에게 위치 안내**

빌드된 exe는 `wage_calculator/dist/통계조사관임금계산_v3.0.exe`에 있다. 기존 `기간제임금/통계조사관임금계산_v2.2.exe`(프로젝트 루트)는 그대로 두고, 새 v3.0 exe를 실제로 업무망에서 쓸지 사용자가 확인한 뒤 원하는 위치로 직접 옮기도록 안내한다(자동으로 옮기거나 기존 v2.2를 덮어쓰지 않음 — 배포 파일 이동은 사용자 판단 영역).

---

## Self-Review 체크리스트 (계획 작성자용, 참고)

- **스펙 커버리지**: §2(요구사항)→Task 2/5/6, §3(버그수정)→Task 5, §4(매핑/파서)→Task 2/3, §5(화면)→Task 6/7, §6(계산계층)→Task 5, §7(출력계층)→Task 8, §8(5-1 최신화)→Task 4, §9(버전)→Task 7/9, §11(참고문서)→Task 11. 모두 매핑됨.
- **플레이스홀더 스캔**: 모든 스텝에 실제 코드/명령/기대출력 포함, "TODO"/"적절히 처리" 없음.
- **타입 일관성**: `LeaveEvent.source_range`(Task 3)를 Task 5/6/10에서 동일한 튜플 형태로 사용. `PayrollResult.special_leave_note`(Task 5)를 Task 8/10에서 그대로 소비. `collect_pending_groups`/`SpecialLeaveScreen`(Task 6)을 Task 7/10에서 동일 시그니처로 사용.
