# 패키징(onefile + WebView2 Evergreen) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `wage_calculator/통계조사관임금계산.spec`을 고쳐서, Plan A/B로 완성된 FastAPI+정적 SPA+pywebview 앱을 시스템에 이미 설치된 WebView2(Evergreen)를 사용하는 단일 exe(`통계조사관임금계산_v5.0.exe`)로 패키징한다.

**Architecture:** onefile 구조는 그대로 유지한다. WebView2 런타임은 번들하지 않는다(내부망 PC에 이미 설치돼 있음을 실측 확인). `PyInstaller.utils.hooks.collect_all()`로 동적 임포트가 많은 프레임워크들(uvicorn/fastapi/pydantic 및 pywebview의 .NET 연동 체인)을 통째로 수집해 hiddenimport 누락을 최소화하고, `webapp/static`을 datas로 번들한다.

**Tech Stack:** PyInstaller 6.21.0(이미 설치됨), fastapi/uvicorn/pywebview/openpyxl/pydantic(이미 설치됨).

## Global Constraints

- `wage_calculator/core/*`, `wage_calculator/output/*`, `wage_calculator/webapp/state.py`, `wage_calculator/webapp/server.py`, `wage_calculator/webapp/static/*`, `wage_calculator/main.py`는 이 계획에서 수정하지 않는다. `main.py`에 `WEBVIEW2_BROWSER_EXECUTABLE_FOLDER` 관련 코드를 **추가하지 않는다** — Evergreen이므로 pywebview가 시스템 WebView2를 자동으로 찾는다.
- onefile 구조를 유지한다(`COLLECT()`를 추가하지 않는다).
- `demo_assets/*`는 이번 패키징에 포함하지 않는다 — onefile은 실행마다 임시폴더(매번 다른 이름)에 압축을 풀기 때문에 번들해도 사용자가 "찾아보기"로 접근할 방법이 사실상 없다. 예시 파일은 exe와 별도로 `demo_assets` 폴더를 함께 전달하는 방식으로 배포한다(코드 작업 아님, 배포 시 안내만 하면 됨).
- exe 이름은 `통계조사관임금계산_v4.2` → `통계조사관임금계산_v5.0`으로 올린다.
- 참조 문서: `docs/superpowers/specs/2026-08-12-packaging-onefile-evergreen-design.md`

---

### Task 1: `requirements.txt` 신설

**Files:**
- Create: `wage_calculator/requirements.txt`

**Interfaces:**
- Produces: 런타임 의존성 버전 고정 목록(테스트 전용 패키지인 `httpx`/`pytest`는 제외).

- [ ] **Step 1: 현재 설치된 버전 확인**

Run: `pip show fastapi uvicorn pywebview openpyxl pydantic | grep -E "^Name|^Version"`
Expected: 아래와 동일한 버전이 출력됨(이미 이 환경에 설치되어 Plan A/B 전체를 통과시킨 조합)

```
Name: fastapi
Version: 0.141.1
Name: uvicorn
Version: 0.52.1
Name: pywebview
Version: 6.2.1
Name: openpyxl
Version: 3.1.5
Name: pydantic
Version: 2.13.4
```

- [ ] **Step 2: `requirements.txt` 작성**

`wage_calculator/requirements.txt`:

```
fastapi==0.141.1
uvicorn==0.52.1
pywebview==6.2.1
openpyxl==3.1.5
pydantic==2.13.4
```

- [ ] **Step 3: 새 가상환경 없이 그대로 설치 확인(회귀 없음 확인)**

Run: `pip install -r wage_calculator/requirements.txt`
Expected: 전부 `Requirement already satisfied`(이미 설치된 버전과 동일하므로 아무것도 새로 설치되지 않아야 함 — 다른 버전이 새로 설치된다면 기존 Plan A/B 테스트가 그 버전 조합으로 다시 통과하는지 확인 필요)

Run: `python -m pytest wage_calculator/tests/ -v`
Expected: 전부 `passed`(108개, Plan B 완료 시점과 동일)

- [ ] **Step 4: 커밋**

```bash
git add wage_calculator/requirements.txt
git commit -m "feat: 런타임 의존성 requirements.txt 신설"
```

---

### Task 2: `.spec` 재작성 + 빌드/검증 (onefile, WebView2 Evergreen, collect_all)

**Files:**
- Modify: `wage_calculator/통계조사관임금계산.spec`

**Interfaces:**
- Consumes: `wage_calculator/main.py`(Plan B에서 완성, 무수정), `wage_calculator/webapp/static/*`(Plan B에서 완성)
- Produces: `wage_calculator/dist/통계조사관임금계산_v5.0.exe` — 이 계획의 최종 산출물

이 태스크는 기존 태스크들과 다르게 TDD형 RED/GREEN이 아니라, **"고치고 → 빌드하고 → 실행해보고 → 에러가 있으면 원인을 읽고 spec을 보강하고 → 다시 빌드"를 exe가 실제로 뜨고 데모 흐름이 동작할 때까지 반복**하는 절차다. FastAPI/uvicorn/pywebview(특히 .NET 연동 체인인 pythonnet/clr_loader)는 동적 임포트가 많아 정확히 어떤 hiddenimport가 빠졌는지는 실제로 빌드해보기 전엔 100% 예측할 수 없다.

- [ ] **Step 1: 현재 `.spec` 내용 확인**

Run: `cat wage_calculator/통계조사관임금계산.spec`
Expected:

```python
# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='통계조사관임금계산_v4.2',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
```

- [ ] **Step 2: `.spec` 재작성(첫 시도 — 시작점)**

`wage_calculator/통계조사관임금계산.spec` 전체를 다음으로 교체:

```python
# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

BASE_DIR = Path(SPECPATH)

datas = [
    (str(BASE_DIR / "webapp" / "static"), "webapp/static"),
]
binaries = []
hiddenimports = []

for pkg in ("uvicorn", "fastapi", "pydantic", "pydantic_core", "webview", "pythonnet", "clr_loader", "cffi"):
    pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(pkg)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hiddenimports

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='통계조사관임금계산_v5.0',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
```

`(str(BASE_DIR / "webapp" / "static"), "webapp/static")`에서 목적지를 `"webapp/static"`(소스와 동일한 상대경로)으로 지정하는 이유: `wage_calculator/webapp/server.py`가 `Path(__file__).resolve().parent / "static"`로 정적 파일 위치를 찾는데, freeze된 상태에서 `__file__`은 `<번들 임시폴더>/webapp/server.py`로 해석되므로, 번들 안에서도 `webapp/static`이 그 상대 위치에 있어야 기존 코드(무수정)가 그대로 동작한다.

- [ ] **Step 3: 첫 빌드 시도**

Run: `cd wage_calculator && pyinstaller 통계조사관임금계산.spec --noconfirm`
Expected: `completed successfully`로 끝나거나, 빌드 자체는 되지만 `dist/통계조사관임금계산_v5.0.exe` 실행 시 에러가 날 수 있음(다음 스텝에서 확인)

- [ ] **Step 4: 콘솔 모드로 먼저 실행해 에러를 눈으로 확인**

`console=False`인 상태로는 에러가 나도 창이 그냥 안 뜨고 끝나버려 원인을 알 수 없다. 디버깅 중에는 `.spec`의 `console=False`를 `console=True`로 임시로 바꾸고 다시 빌드해서, cmd 창에 뜨는 실제 트레이스백을 읽는다.

Run:
```bash
cd wage_calculator
# .spec에서 console=True로 임시 변경 후
pyinstaller 통계조사관임금계산.spec --noconfirm
./dist/통계조사관임금계산_v5.0.exe
```
Expected: pywebview 창이 뜨고 업로드 화면이 보이거나, `ModuleNotFoundError`/`ImportError` 등의 트레이스백이 콘솔에 출력됨

- [ ] **Step 5: 에러가 나오면 원인 분석 후 `.spec` 보강, 반복**

흔히 나올 수 있는 에러와 대응:
- `ModuleNotFoundError: No module named 'X'`이지만 `X`가 Step 2의 `collect_all` 대상 패키지 중 하나의 서브모듈이라면 → 이미 있어야 정상인데 빠졌다는 뜻이므로, `X`의 최상위 패키지명을 확인해 `collect_all` 목록에 없는 관련 패키지(예: `bottle`, `proxy_tools`)를 추가
- `Python.Runtime.dll`을 못 찾는다는 취지의 pythonnet 관련 에러 → `collect_all("pythonnet")`이 `.dll`을 `binaries`로 수집하는지 확인(안 되면 `collect_dynamic_libs("pythonnet")`을 추가로 import해서 `binaries`에 합침)
- `FileNotFoundError`로 `webapp/static/...`를 못 찾는다는 에러 → Step 2의 datas 경로 매핑이 잘못된 것이므로, 빌드 결과물(`dist/통계조사관임금계산_v5.0.exe`를 실행했을 때 생기는 임시폴더 - `console=True` 상태에서 에러 메시지에 실제 찾던 경로가 출력됨)을 보고 목적지 경로를 맞춤

매 시도마다: `.spec` 수정 → `pyinstaller 통계조사관임금계산.spec --noconfirm` 재실행 → `./dist/통계조사관임금계산_v5.0.exe` 재실행 → 에러 확인, 을 에러가 없어질 때까지 반복한다.

- [ ] **Step 6: 정상 동작 확인 (완료 조건)**

`console=True`로 문제없이 창이 뜨는 게 확인되면 `.spec`의 `console=True`를 다시 `console=False`로 되돌리고 마지막으로 한 번 더 빌드한 뒤, 아래를 전부 확인한다:

1. `dist/통계조사관임금계산_v5.0.exe`를 더블클릭(또는 `./dist/통계조사관임금계산_v5.0.exe` 실행) → 콘솔 창 없이 pywebview 창만 뜬다
2. 업로드 화면에서 `demo_assets/개인정보_예시(A).xlsx`, `demo_assets/근무상황_예시(B).xlsx`(저장소 루트의 `demo_assets/` — 번들 안에 없으므로 실제 파일시스템 경로를 입력) 경로를 입력하고 "다음" → 특별휴가 화면으로 정상 전환
3. 특별휴가 확정 → 대상자 화면 → (설정에서 2026년 요율 + 조사 하나 등록 후) 전체선택 → 일괄매칭 → "계산 실행" → 계약기간 확인 → 계산실행 확인 모달 → "계속" → 결과 화면까지 정상 전환
4. 결과 화면에서 "엑셀 다운로드" → 다운로드 폴더에 실제 파일 생성 확인, "산정근거 확인" → 산정근거 화면 정상 렌더링
5. `python main.py`(개발 모드)로 같은 흐름을 실행했을 때와 계산 결과가 동일한지 확인(이번 작업은 계산 로직을 전혀 건드리지 않으므로 당연히 같아야 함 — 다르면 패키징 문제가 아니라 훨씬 심각한 문제이므로 즉시 보고)

- [ ] **Step 7: 전체 자동 테스트 스위트 회귀 확인**

Run: `python -m pytest wage_calculator/tests/ -v`
Expected: 108개 전부 `passed`(이 태스크는 `.spec`/빌드 산출물만 다루고 Python 소스는 건드리지 않으므로 회귀가 있으면 안 됨)

- [ ] **Step 8: 커밋**

```bash
git add "wage_calculator/통계조사관임금계산.spec"
git commit -m "feat: .spec을 onefile+WebView2 Evergreen+collect_all 기반으로 재작성(v5.0)"
```

`dist/`, `build/`는 이미 `.gitignore`에 등록되어 있어 커밋 대상에서 자동 제외된다.

---

## 완료 후 확인

- [ ] **배포 안내**: `dist/통계조사관임금계산_v5.0.exe`를 실제로 동료에게 전달할 때는, 필요하면 저장소의 `demo_assets/` 폴더(개인정보_예시(A).xlsx, 근무상황_예시(B).xlsx, 전월_임금내역_예시(7월).xlsx)를 exe와 같은 폴더에 함께 넣어서 전달한다. 코드 작업이 아니라 배포 시 참고사항이다.
- [ ] **전체 회귀**: `python -m pytest wage_calculator/tests/ -v` — Plan A/B의 108개가 전부 통과해야 한다.
