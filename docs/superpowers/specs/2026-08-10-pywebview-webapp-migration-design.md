# tkinter GUI → pywebview 기반 웹 UI 마이그레이션 설계

> 관련 코드: `wage_calculator/gui/*`(전체 교체 대상), `wage_calculator/main.py`, `wage_calculator/통계조사관임금계산.spec`
> 불변 대상: `wage_calculator/core/*`, `wage_calculator/output/*` (계산/엑셀 생성 로직은 손대지 않음)

## 1. 배경

현재 프로그램은 tkinter 기반 GUI를 PyInstaller onefile exe로 배포하는 구조다. 각 직원이 exe를 개별 실행하는 방식은 유지하고 싶지만, tkinter 위젯의 디자인이 낡아 보인다는 문제가 있었다.

두 가지 대안(① 내부망에 웹서비스로 띄우기 ② 고용노동부 내부 GPT에 프롬프트 기반으로 연동)을 검토했으나:
- ①은 상시 구동 서버 PC 확보, 내부망 포트 개방에 대한 보안 심의 등 인프라 문제가 크다.
- ②는 임금 계산처럼 절삭 원칙·소급계산 같은 정밀한 규칙이 있는 도메인에서 LLM이 프롬프트만으로 계산을 재현하면 오류/할루시네이션 위험이 크고, 내부 GPT가 커스텀 도구/코드 실행을 지원하지 않는 한 실효성이 낮다.

대신 **"디자인만 웹 앱처럼 바꾸되, 배포/실행 방식은 지금처럼 exe 하나로 유지"**하는 방향으로 결정했다. `pywebview`로 로컬 HTML/CSS UI를 네이티브 창에 띄우면, 서버 인프라 없이도 ChatGPT/Claude 스타일의 모던한 디자인을 구현할 수 있다. 백엔드를 FastAPI로 만들어두면, 훗날 내부망 인프라가 갖춰질 경우 UI 재작성 없이 바인딩 주소만 바꿔 공용 웹서비스로 전환할 수 있는 여지도 남는다.

## 2. 확정된 요구사항

- 화면 흐름(업로드 → 특별휴가 마킹 → 대상자 확인 → 계약기간 확인 → 계산 실행 확인 → 결과 → 산정근거)은 **지금과 동일**하게 유지한다. 이번 작업은 UX 흐름 개선이 아니라 프레젠테이션 레이어 교체다.
- 모든 검증/차단 규칙(동명이인 차단, 특별휴가 미정 건 진행 차단, 담당조사 미지정 경고 등)은 서버 쪽(`AppState`)에 그대로 유지한다.
- `core/`, `output/`은 변경하지 않는다. 계산 결과와 엑셀 산출물은 마이그레이션 전후로 완전히 동일해야 한다.
- 디자인 톤은 ChatGPT/Claude 스타일(흰/연회색 기반, 카드형 레이아웃, 단계별 진행 느낌).
- 상시 구동 서버나 내부망 인프라는 요구하지 않는다 — 각 직원이 exe를 실행하는 동안에만 로컬(`127.0.0.1`)에서 서버가 뜨고, 창을 닫으면 함께 종료된다.
- 설정값(`config.json`)은 지금처럼 exe가 위치한 폴더에 저장되어 PC별로 독립적으로 유지된다 (변경 없음).

## 3. 아키텍처

### 실행 흐름
1. `main.py`가 빈 로컬 포트를 찾아 FastAPI 앱을 백그라운드 스레드(uvicorn)로 `127.0.0.1:<port>`에 기동
2. pywebview 창을 열어 그 주소를 로드. 동시에 `js_api` 객체를 노출해 OS 파일 선택 다이얼로그처럼 웹 서버를 거칠 필요 없는 네이티브 기능을 직접 처리
3. `webview.start()`가 창을 띄우고 블로킹. 창을 닫으면 서버 스레드도 함께 정리됨

### 상태 관리
`App(tk.Tk)`가 들고 있던 `employees`, `people`, `results`, `retro_adjustments` 등의 속성과 `load_files()`, `run_calculation()`, `reset()` 같은 orchestration 메서드를 **`AppState`**(평범한 Python 객체)로 옮긴다. 로컬 1인용 앱이라 로그인/세션 개념 없이 FastAPI 프로세스 안에 싱글턴으로 유지한다. 로직은 그대로, "tkinter 위젯을 그리던 부분"만 "JSON을 반환하는 부분"으로 바뀐다.

### 새 디렉터리 구조
`gui/`를 대체하는 `webapp/` 패키지:
- `webapp/server.py` — FastAPI 라우트
- `webapp/state.py` — `AppState`
- `webapp/static/` — CSS/JS
- `webapp/templates/` — 화면별 HTML(Jinja2)

## 4. 화면별 매핑

각 화면의 동작·검증 로직은 그대로 두고 렌더링만 바뀐다. 다이얼로그(설정, 확인창, 계약기간 수정)는 별도 OS 창 대신 **페이지 내 모달 카드**로 구현한다.

| 현재 화면 | 새 API | 비고 |
|---|---|---|
| UploadScreen | `POST /api/upload` | A/B/전월 파일 선택은 `js_api.pick_file()`로 OS 네이티브 다이얼로그 사용. 마지막 사용 경로 기억(§5) |
| SpecialLeaveScreen | `GET /api/special-leave`, `POST /api/special-leave/confirm` | 상태 토글(미정→유급→무급)은 클라이언트에서 처리, "다음" 클릭 시 한 번에 서버 전송 |
| TargetScreen + ContractEditDialog | `GET /api/targets`, `POST /api/targets/batch-assign`, `POST /api/targets/contract-edit`, `POST /api/targets/proceed` | 체크박스 선택은 클라이언트 상태로 관리. 더블클릭 시 계약기간 수정은 인라인 모달 |
| ContractPeriodCheckDialog + ConfirmRunDialog | `GET /api/confirm-info`, `POST /api/calculate` | 2단계 확인 모달 유지(계약기간 확인 → 공휴일/요율/수정인원 안내 → 계산 실행) |
| ResultScreen | `GET /api/results`, `POST /api/download` | 다운로드는 지금처럼 자동으로 다운로드 폴더에 저장 후 저장 경로를 토스트로 안내(저장 위치를 묻지 않는 현재 동작 유지) |
| EvidenceScreen | `GET /api/evidence?key=` | 좌측 원본 B파일 표 + 우측 4개 탭(주휴/조퇴외출/식대/잔여연가)을 한 번의 호출로 받아 클라이언트에서 탭만 전환 |
| SettingsDialog | `GET /api/settings`, `POST/DELETE /api/settings/survey`, `POST/DELETE /api/settings/rate`, `POST/DELETE /api/settings/holiday` | 조사종류/요율/공휴일 3개 탭 CRUD 유지, 앱 시작 시 자동으로 뜨는 동작 유지 |

## 5. 신규 기능: 파일 선택 마지막 경로 기억

- `Config`에 `last_upload_dir` 필드를 추가한다.
- A/B/전월임금내역 세 버튼은 이 값을 **공유**한다 — 셋 중 어느 것으로든 파일을 성공적으로 고르면 그 폴더로 `last_upload_dir`를 갱신한다.
- 다음 "찾아보기" 클릭 시 `js_api.pick_file()`이 이 경로를 시작 위치로 사용한다.
- `config.json`에 함께 저장되므로 앱 재시작 후에도 유지된다.

## 6. 에러 처리 & 다이얼로그

- **차단성 에러**(동명이인, 파일 로드 실패, 형식 오류 등 — 기존 `showerror`): 화면 상단 빨간 배너/토스트. API는 `4xx` + `{"error": "..."}` 응답.
- **확인이 필요한 경고**(담당조사 미지정 인원 있음 — 기존 `askyesno`): 페이지 내 모달로 "계속/취소" 제공. 서버 검증 로직은 그대로 재사용.
- **부분 실패**(계산 중 일부 인원만 오류 — 기존 `showwarning`): `POST /api/calculate` 응답에 `{"results": [...], "errors": [...]}`를 함께 담아, 결과 화면 진입 시 노란 경고 배너로 표시하고 나머지는 정상 진행.
- **앱 자체 기동 실패**(WebView2 로드 실패, 포트 바인딩 실패 등): 웹 UI로 보여줄 수 없으므로 `main.py`에서 표준 Windows 메시지박스(`ctypes.windll.user32.MessageBoxW`)나 콘솔 출력으로 원인을 알리고 종료. 흔치 않은 상황이라 최소한으로만 처리.

## 7. 테스트

- `core/`·`output/`을 직접 검증하는 기존 테스트(`test_build_workbook_integration.py`, `test_payroll_*` 등)는 변경 없이 그대로 통과해야 한다.
- `app.py`에 있던 검증 로직(동명이인 차단, 담당조사 미지정 경고 등)이 옮겨간 `AppState`에 대해 동일한 검증을 단위테스트로 커버한다.
- HTML/JS 화면 자체는 지금 tkinter 위젯처럼 자동테스트 없이 직접 실행해서 확인한다.

## 8. 패키징 (onedir + WebView2 Fixed Version 번들링)

- **spec 변경**: `EXE()` 뒤에 `COLLECT()`를 추가해 현재의 onefile 방식을 **onedir**로 전환한다. WebView2 Fixed Version 런타임(~150~200MB)을 onefile로 묶으면 매 실행마다 임시 폴더에 풀어놓는 과정 때문에 구동이 느려지기 때문이다. 결과물은 `통계조사관임금계산_v5.0/` 폴더 안에 exe + 의존성 dll + `webapp/static`·`webapp/templates` + WebView2 런타임 폴더가 함께 들어간다. 배포는 이 폴더를 zip으로 압축해 전달한다(단일 exe 파일 첨부에서 폴더 배포로 변경).
- **WebView2 런타임**: Microsoft가 제공하는 Fixed Version Runtime을 다운로드해 프로젝트에 포함시키고 `datas`에 등록, 인터넷 연결이나 시스템의 WebView2 설치 여부와 무관하게 항상 이 번들 런타임을 사용한다.
- **main.py 부트스트랩**: frozen 상태로 실행될 때 `WEBVIEW2_BROWSER_EXECUTABLE_FOLDER` 환경변수를 exe와 같은 폴더 내 런타임 경로로 지정한 뒤 pywebview 창을 연다.
- **새 의존성**: `fastapi`, `uvicorn`, `pywebview`, `jinja2`. 현재 없는 `requirements.txt`를 신설한다. PyInstaller `hiddenimports`에 `uvicorn`과 `pywebview`의 플랫폼별 백엔드 모듈을 명시적으로 추가한다(둘 다 동적 임포트를 사용해 PyInstaller가 자동으로 못 찾는 경우가 있음).
- **버전 네이밍**: 아키텍처 대규모 변경이므로 `통계조사관임금계산_v4.2` → `v5.0`으로 올린다.
- **예시 파일 동봉**: `demo_assets/`에 A(개인정보)·B(근무상황)·전월 임금내역 3종 예시 파일을 배포 폴더에 함께 넣는다. A/B 예시는 실제 직원 정보가 아닌 **가상 인물 5명의 더미 데이터**로 새로 만든다(주민번호·계좌번호 등은 전부 가짜 값). B 예시에는 특별휴가 마킹 화면까지 시연되도록 "특별휴가" 종별 건을 하나 포함한다. `datas`에 `demo_assets/`를 등록해 onedir 폴더 안에 그대로 복사되게 한다.
