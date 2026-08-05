# B파일 매칭 단순화 / 비파괴 뒤로가기 / 계약기간 사전확인 / 소급계산 설계

> 관련 코드: `wage_calculator/core/{parser,config,payroll}.py`, `wage_calculator/gui/{app,target_screen,result_screen,confirm_dialog,upload_screen,settings_dialog}.py`, `wage_calculator/output/wage_sheet.py`

## 0. 배경

사용자(급여 담당자)로부터 5가지 개선 요청을 받았다. 그중 3건(매칭 단순화, 뒤로가기, 계약기간 사전확인)은 기존 코드에 국소적으로 대응되는 변경이고, 나머지 2건(절삭 처리, 소급계산) 중 절삭 처리는 조사 결과 **이미 요구사항대로 구현되어 있어 변경이 불필요**했다. 소급계산은 이번 작업에서 가장 규모가 큰 신규 기능으로, 사용자와 여러 차례 확인을 거쳐 아래와 같이 확정했다.

## 1. B파일 매칭 시 직급 필터 제거

### 확정된 요구사항
A파일(개인정보)은 이미 급여계산 대상자만 추려서 관리되고 있다. `build_target_people()`은 이미 A파일을 로스터로 삼아 이름+생년월일로 B파일 행을 매칭하므로, B파일 단계에서 직급으로 다시 거를 필요가 없다.

### 변경
[`parser.py:53-74`](../../../wage_calculator/core/parser.py) `load_giganje_rows()`에서 다음 부분을 제거한다.

```python
rank = str(row.get("직급") or "")
if "기간제" not in rank:
    continue
```

필수 컬럼 검증(`required = [..., "직급", ...]`)은 그대로 유지한다(직급 컬럼 자체는 `person.rank` 표시용으로 계속 읽으므로).

### 영향
- B파일에 직급이 "기간제"가 아닌 사람의 행이 있어도, A파일에 있는 사람이면 정상적으로 근무상황이 매칭된다.
- A파일에 없는 이름의 행은 지금처럼 `missing_names`로 잡힌다(동작 변화 없음).
- 기존 테스트 중 직급 필터를 전제로 한 것이 있는지 확인 후 갱신한다.

## 2. 결과화면 비파괴 뒤로가기 추가

### 확정된 요구사항
계산 실행 후 결과 화면에서 산정월 등을 잘못 입력한 걸 알았을 때, 처음(파일 업로드)부터 다시 시작하지 않고도 대상자 확인 화면(TargetScreen)으로 돌아가 값을 고칠 수 있어야 한다. 단, 전체초기화 기능 자체는 없애지 않고 유지한다 — 두 버튼을 나란히 배치한다.

### 변경
- [`app.py`](../../../wage_calculator/gui/app.py)에 `show_target_screen()`을 그대로 호출하는 것 외에 별도 상태초기화가 필요 없다(`self.people`, `self.employees`, `self.giganje_rows` 등은 이미 보존되어 있음).
- [`result_screen.py`](../../../wage_calculator/gui/result_screen.py) 하단 버튼 영역에 기존 "새로 계산(처음부터)" 버튼 옆에 **"뒤로가기"** 버튼을 새로 추가한다.
  - "뒤로가기": 확인 팝업 없이 바로 `self.app.show_target_screen()` 호출(비파괴).
  - "새로 계산(처음부터)": 기존 동작(확인 팝업 후 `self.app.reset()`) 그대로 유지.
- 메뉴바([`app.py:_build_menu`](../../../wage_calculator/gui/app.py))에도 "새 파일로 시작" 항목을 추가해 어느 화면에서든 전체초기화에 접근 가능하게 한다(현재는 ResultScreen에서만 가능).

## 3. 계산 실행 전 계약기간 사전확인 확인창

### 확정된 요구사항
"계산 실행" 클릭 시 뜨는 기존 확인창(`ConfirmRunDialog`, 공휴일/공통입력값/계약기간 수정 인원 안내) **앞에**, 중도퇴사자·추가입사자의 계약기간을 제대로 입력했는지 묻는 확인창을 먼저 띄운다.

### 변경
- 새 클래스 `ContractPeriodCheckDialog`를 [`confirm_dialog.py`](../../../wage_calculator/gui/confirm_dialog.py)에 추가한다.
  - 문구: "중도퇴사자와 추가입사자의 계약기간을 정확히 입력했는지 확인하세요." (안내 문구만, 별도 데이터 조회 없음 — 실제 값 검증이 아니라 담당자 확인 절차이므로)
  - 버튼 2개: **"아니오(다시입력)"** → 다이얼로그만 닫음(TargetScreen에 그대로 남음). **"네(진행)"** → 다이얼로그를 닫고 `self.app.open_confirm_dialog()`(기존 `ConfirmRunDialog`) 오픈.
- [`target_screen.py`](../../../wage_calculator/gui/target_screen.py) `_proceed()`의 마지막 줄 `self.app.open_confirm_dialog()`를 새 다이얼로그를 여는 호출로 교체한다.
- `app.py`에 `open_contract_period_check_dialog()` 헬퍼를 추가(기존 `open_confirm_dialog()`와 동일한 패턴).

## 4. 절삭(반올림 금지) — 변경 없음

`late_out_deduction`(조퇴외출공제)과 `total_payment`(지급총액)를 포함해 `payroll.py`의 모든 금액 계산은 이미 `round_down()`(내림, floor)으로 처리되어 있다. 코드 전체에서 금액에 대해 파이썬 `round()`(반올림)를 쓰는 곳은 없다(날짜/시간 수량 표시용 `round()`만 존재하며 원 단위 금액과 무관). **코드 변경 없음.**

## 5. 소급계산

### 5.1 배경 / 확정된 요구사항

급여는 매월 20일 전후로 계산해 25일에 지급하므로, 계산 시점에는 그 달 21~말일 근무상황이 아직 반영되지 못한다. 이 구간의 변동사항(예: 계약 중도종료, 추가 결근 등)은 다음 달 급여 계산 시 소급 반영(환수 또는 추가지급)한다.

확정된 동작:
1. 당월 계산 시, 이 프로그램이 지난달에 직접 생성했던 임금내역 엑셀 파일을 추가로 업로드 받는다.
2. 당월 B파일(근무상황)에는 전월 21~말일치 근무상황까지 포함되어 있다는 전제 하에(사용자 확인 완료), 같은 `person.events`로 전월분을 다시 계산한다.
3. 재계산한 전월 지급총액과, 업로드된 전월 파일에 기록된 실지급액을 비교해 차액(소급조정액, 양수=추가지급/음수=환수)을 산출한다.
4. 소급조정액은 당월 임금내역에 별도 열로 표시하고 최종지급액에 합산한다.
5. 전월 파일에는 있지만 당월 A파일에는 없는 사람(계약 종료로 완전히 퇴사)도, 당월 B파일에 남아있는 잔여 근무상황 행으로 전월분만 재계산해 소급 처리한다. 이 사람들은 당월 계산 대상자 명단에는 포함되지 않고 별도 파일로 출력한다.
6. 연도 경계(예: 12월 계산 중 1월분 소급, 또는 그 반대)에도 각 연도에 맞는 시급/식대 요율을 적용한다.

### 5.2 연도별 요율 관리 (`config.py`)

현재 `config.common = {"hourly_wage": ..., "meal_allowance": ...}` 단일 값 구조를, 연도별 값을 담는 구조로 바꾼다.

```python
DEFAULT_CONFIG = {
    "surveys": [],
    "rates": {},   # {"2026": {"hourly_wage": 9820, "meal_allowance": 160000}, ...}
    "holidays": []
}
```

- `Config.rates: dict[str, dict]` (JSON 키는 문자열 연도)
- `Config.hourly_wage_for(year: int) -> int`, `Config.meal_allowance_for(year: int) -> int`: 해당 연도 키가 없으면 `ValueError`(어느 연도 요율이 빠졌는지 메시지에 명시)
- `Config.set_year_rates(year: int, hourly_wage: int, meal_allowance: int)`, `Config.delete_year_rates(year: int)`, `Config.rate_years() -> list[int]`(정렬된 연도 목록)
- **마이그레이션**: 기존 `config.json`에 `"common"`은 있고 `"rates"`가 없으면, 로드 시 `date.today().year`를 키로 하여 1회 자동 이전한다(레거시 `common`은 이후 무시).
- 기존 `hourly_wage`/`meal_allowance` 프로퍼티(연도 없이 호출되던 것)는 삭제한다 — 호출부가 전부 연도를 아는 컨텍스트(`calc_payroll` 등)이므로 대체 가능.

### 5.3 `calc_payroll` 요율 조회 방식 변경

[`payroll.py:64-65`](../../../wage_calculator/core/payroll.py)의

```python
daily_wage = round_down(config.hourly_wage * 8, 1)
daily_meal = round_down(config.meal_allowance / 209 * 8, 1)
```

를

```python
daily_wage = round_down(config.hourly_wage_for(year) * 8, 1)
daily_meal = round_down(config.meal_allowance_for(year) / 209 * 8, 1)
```

로 변경한다(`calc_payroll`은 이미 `year` 인자를 받고 있어 시그니처 변경 불필요). 해당 연도 요율이 설정에 없으면 `ValueError`가 그대로 전파되어, `app.run_calculation()`의 기존 개인별 오류 수집 로직(`errors.append(...)`)에 잡혀 사용자에게 안내된다.

### 5.4 설정화면 (`settings_dialog.py`)

"공통 입력값" 탭을 연도별 요율 관리 탭으로 바꾼다(조사종류 탭과 동일한 Treeview + 입력폼 패턴).

- Treeview 컬럼: 연도 / 시급환산(원) / 월 식대(원)
- 입력폼: 연도, 시급, 식대 입력 후 "추가/수정" 버튼(같은 연도 재입력 시 덮어씀) — `_add_or_update_survey`/`_reload_surveys` 패턴을 그대로 따라 `_add_or_update_rate`/`_reload_rates` 구현
- "선택 삭제" 버튼

### 5.5 전월 임금내역 파일 업로드 + 파싱

- [`upload_screen.py`](../../../wage_calculator/gui/upload_screen.py)에 3번째 파일 선택 행 추가: **"전월 임금내역 파일 (선택 - 소급계산용)"**. 비워두면 소급계산을 건너뛴다(기존 동작 그대로).
- `parser.py`에 `load_previous_payroll(path) -> dict[str, dict]` 추가.
  - `output/wage_sheet.py`의 `COL` 딕셔너리와 동일한 고정 컬럼 위치로 "임금내역(월중)" 시트를 읽는다(이 프로그램이 직접 생성한 파일이므로 헤더 텍스트가 아니라 고정 열 위치로 파싱 — 헤더가 병합 셀이라 텍스트 파싱이 불안정함).
  - 키는 **주민번호**(`COL["ssn"]`)로 한다 — 이 파일에는 생년월일 컬럼이 없어 현재 앱의 이름+생년월일 매칭 키를 그대로 쓸 수 없고, 주민번호가 A파일/전월파일 양쪽에 공통으로 존재하는 유일한 안정적 식별자다.
  - 값: `{ssn, name, contract_start, contract_end, total_payment, bank, account}` (모두 `COL`의 기존 열에서 읽음)

### 5.6 재계산 + 대상자 구성

새 함수 `core/retroactive.py`(신규 모듈)에 로직을 모은다.

```python
def compute_retroactive(people, previous_payroll, giganje_rows, employees, config, prev_year, prev_month):
    """반환: (current_month_adjustments, departed_only_results)
    - current_month_adjustments: {person_key: 소급조정액} — 당월 대상자 중 전월파일에도 있던 사람
    - departed_only_results: [(전월파일 정보, 전월 재계산 PayrollResult), ...] — 당월 A파일엔 없는 완전퇴사자
    """
```

- **당월 대상자**: `people`(이미 만들어진 이 달 로스터) 각각에 대해, `previous_payroll`에서 같은 `ssn`을 찾으면 `calc_payroll(person, config, prev_year, prev_month)`를 호출해 전월분을 재계산하고, `재계산액 - previous_payroll[ssn].total_payment`를 소급조정액으로 기록. `previous_payroll`에 없으면(신규입사자 등) 소급 없음(0).
- **완전퇴사자**: `previous_payroll`의 각 항목 중 당월 `people`에 매칭되는 `ssn`이 없는 사람. 이 사람들은 당월 A파일에 없으므로 `build_target_people()`의 정식 로스터에는 없다.
  - `giganje_rows`(직급 필터 제거된 당월 B파일 전체, §1)에서 **같은 이름**의 행을 먼저 찾는다. B파일에는 주민번호가 없고 생년월일만 있으므로, `previous_payroll`의 주민번호(앞 6자리 YYMMDD + 성별 구분 숫자)로부터 생년월일을 역산하는 `date_utils.birth_from_ssn(ssn) -> "YYYY-MM-DD"`를 새로 추가해 B파일의 생년월일과 비교, 동명이인이 있어도 정확히 구분한다.
  - 이름이 일치하는 B파일 잔여 행이 **하나도 없으면** 재계산할 새 정보가 없다는 뜻이므로 소급조정액 0으로 간주하고 별도 출력 대상에서도 제외한다(즉, 소급 전용 파일에는 실제로 조정이 발생한 사람만 나열됨).
  - 잔여 행이 있으면 그 행들로 임시 `TargetPerson`을 구성한다(`contract_start`/`contract_end`/`bank`/`account`/`ssn`은 전월 파일 값을 그대로 사용 — 이번 달엔 새 계약정보가 없으므로). 이 임시 인물로 `calc_payroll(temp_person, config, prev_year, prev_month)`를 호출해 전월분만 계산하고, 그 결과 전체가 소급조정액이 된다(당월분 없음).
  - 이름은 일치하지만 `birth_from_ssn` 결과와 B파일 생년월일이 둘 다 존재하는데 서로 다른 경우(동명이인)는 매칭하지 않고 경고만 남긴다(기존 `ambiguous_names` 처리와 같은 원칙 — 잘못된 사람에게 소급액을 붙이는 사고 방지).

### 5.7 출력

- **임금내역(월중) 시트** (`wage_sheet.py`): 기존 열 뒤에 두 열 추가.
  - `소급조정액`: 양수=추가지급, 음수=환수, 소급 대상이 아니면 0.
  - `최종지급액`: `지급총액 + 소급조정액`.
  - 기존 `지급총액`(W열, `COL["total_payment"]`) 값과 헤더는 그대로 유지한다(당월 순계산액 그대로, 감사 추적용).
  - 헤더 셀 `W1`에 잘못 붙어있던 "기존지급액" 라벨(실제로는 이 프로그램이 계산한 당월 지급총액이 들어가는 자리로, 원본 수기 엑셀 템플릿에서 넘어온 라벨 불일치로 보임)은 이번 작업 범위 밖이라 손대지 않는다.
- **엑셀 다운로드** (`result_screen.py` `_download()`): 소급 전용(완전퇴사) 대상자가 1명 이상이면 파일 2개를 자동 저장한다 — ① 당월 대상자 임금내역(기존과 동일 파일명), ② `'{yy}년 {month}월 소급대상자 내역.xlsx`(성명/주민번호/은행/계좌/전월재계산액/전월실지급액/소급조정액=최종지급액). 소급 전용 대상자가 없으면 지금처럼 파일 1개만 저장한다.

### 5.8 테스트 범위

- `parser.load_giganje_rows`: 직급이 "기간제"가 아닌 행도 그대로 반환되는지(§1)
- `config.py`: 연도별 요율 저장/조회, 레거시 `common` 마이그레이션, 미설정 연도 조회 시 예외
- `calc_payroll`이 연도별 요율을 정확히 골라 쓰는지(연도 경계 케이스: 12월/1월)
- `parser.load_previous_payroll`: 고정 열 위치 파싱 정확성
- `retroactive.compute_retroactive`: 당월 대상자 소급조정액 계산, 완전퇴사자 분리 및 재계산, 전월파일에 없는 신규입사자는 소급 0
- `wage_sheet.py`: 소급조정액/최종지급액 열 출력, 완전퇴사자 별도 파일 생성 여부(있음/없음 두 케이스)
- GUI: `result_screen.py` 뒤로가기가 `app.reset()`을 호출하지 않고 상태를 보존하는지, `ContractPeriodCheckDialog`의 예/아니오 분기

## 6. 지급내역(금액) 수식 근거 시트 (신규)

### 6.1 배경 / 확정된 요구사항

실제 테스트 중 특정 인원 1명의 최종 지급액이 비교 대상(다른 청 등에서 쓰던 엑셀)과 10원 차이가 났다. 조사 결과 이 프로그램의 절삭(내림) 로직 자체(§4: 조퇴외출공제/기본급/정액급식비/지급총액 4곳에서 각각 10원 단위 절삭, `daily_wage`/`daily_meal`/`leave_compensation`은 1원 단위 절삭) 에는 문제가 없고, 절삭 지점·순서가 참조처마다 다른 데서 오는 정상적인 차이로 보인다. **절삭 로직(4곳, 각 단위)은 그대로 유지**하고, 사람이 엑셀에서 직접 "이 값이 어느 셀에서 어떤 수식으로 나왔는지" 눈으로 추적할 수 있게 만드는 것이 목표다.

범위는 **지급내역(금액) 부분만**이다. 실출근일수·주휴·연차 발생 여부 같은 판정 로직(`leave_engine.py`)은 분기가 많아 엑셀 수식으로 옮기지 않는다(절삭 논란과 무관하고, 이미 임금내역 시트에 판정 결과 값이 나와 있음).

### 6.2 시트 설계

기존 워크북에 **"산정근거(수식)"** 시트를 하나 추가한다(임금내역(월중) 시트는 지금처럼 고정값 그대로 유지 — 다른 용도로 그대로 쓰일 수 있으므로 변경하지 않음).

행 구성은 임금내역(월중) 시트와 동일한 사람 순서를 따르되, 열은 두 종류로 나뉜다.

- **입력값 셀(고정값)**: 파이썬에서 이미 계산된, 수식으로 표현하지 않는 값들을 그대로 적어 넣는다 — 시급(연도별 요율), 조퇴외출(분), 계(일), 주휴(일), 잔여연가(일), 월력상 일수, 식대해당일, 월 식대(연도별 요율), 전월재계산액·전월실지급액(§5, 소급 대상자만).
- **수식 셀**: 위 입력값 셀들을 같은 행 안에서 참조하는 엑셀 수식으로 써넣는다(`ws.cell(...).value = "=ROUNDDOWN(...)"` 형태의 문자열).

| 항목 | 수식(참조 대상은 같은 행의 입력값 셀) |
|---|---|
| 일급 | `=ROUNDDOWN(시급×8, 0)` |
| 일급식대 | `=ROUNDDOWN(월식대/209×8, 0)` |
| 급여액 | `=일급×계(일)` |
| 조퇴외출공제 | `=ROUNDDOWN(시급/60×조퇴외출(분), -1)` |
| 기본급 | `=ROUNDDOWN(급여액−조퇴외출공제, -1)` |
| 주휴수당 | `=일급×주휴(일)` |
| 정액급식비 | `=ROUNDDOWN(월식대/월력상×식대해당일, -1)` |
| 연가보상비 | `=ROUNDDOWN((일급+일급식대)×잔여연가, 0)` (최종월 아니면 0, 입력값 그대로) |
| 지급총액 | `=ROUNDDOWN(기본급+주휴수당+정액급식비+연가보상비, -1)` |
| 소급조정액 (§5) | `=전월재계산액−전월실지급액` (소급 대상자만; 아니면 0) |
| 최종지급액 | `=지급총액+소급조정액` |

각 수식 셀은 실제 파이썬 계산 결과(`PayrollResult`의 값)와 **반드시 일치**해야 한다 — 수식이 별도 계산 경로가 아니라 기존 로직을 엑셀 문법으로 그대로 옮긴 것이므로, 구현 후 두 값(파이썬 계산값 vs 엑셀에서 수식으로 재계산된 값)이 일치하는지 검증한다(6.4 참고).

### 6.3 적용 범위

당월 대상자 임금내역 파일뿐 아니라, §5.7의 소급 전용(완전퇴사자) 별도 파일에도 동일한 방식의 "산정근거(수식)" 시트를 추가한다(이쪽은 소급조정액=최종지급액이므로 지급총액 관련 행은 생략하고 소급조정액 수식만 표시).

### 6.4 테스트 범위

- `output/evidence_sheet.py`(신규 모듈): 각 수식 문자열이 §6.2 표와 정확히 일치하는 셀 주소를 참조하는지
- 엑셀을 실제로 열어 수식이 계산된 값(LibreOffice/Excel 재계산 결과)이 `PayrollResult`의 해당 필드와 1원 단위까지 일치하는지 — `openpyxl`은 수식을 계산하지 않으므로, 이 검증은 `data_only=False`로 수식 문자열 자체의 정확성만 자동 테스트하고, 실제 재계산값 일치는 수동 확인(엑셀에서 열어보기) 절차로 문서화
