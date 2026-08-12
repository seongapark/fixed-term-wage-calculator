# 패키징(onefile + WebView2 Evergreen + 예시파일 동봉) 설계

> 관련 코드: `wage_calculator/통계조사관임금계산.spec`, `wage_calculator/main.py`, `wage_calculator/requirements.txt`(신규)
> 선행 문서: `docs/superpowers/specs/2026-08-10-pywebview-webapp-migration-design.md`(§8에서 Fixed Version 번들링을 전제로 했으나 본 문서에서 뒤집음), Plan A/B(완료)
> 불변 대상: `wage_calculator/core/*`, `wage_calculator/output/*`, `wage_calculator/webapp/*`(state.py, server.py, static/*)

## 1. 배경 — Fixed Version에서 Evergreen으로 전환한 이유

원래 설계(§8)는 "내부망/폐쇄망 PC는 인터넷이 안 돼서 WebView2 자동설치가 안 될 수 있다"는 우려로 WebView2 **Fixed Version 런타임을 통째로 번들**하기로 했었다. 실제로 Microsoft 공식 사이트에서 x64 Fixed Version(151.0.4129.78)을 받아 압축을 풀어보니 **659MB**로, 예상(150~200MB)보다 훨씬 컸다.

이 방향을 확정하기 전에 실제 배포 대상인 내부망 PC에서 직접 확인한 결과, **WebView2가 이미 설치되어 있었다**(버전 136.0.4129.64 확인). 번들링의 존재 이유였던 리스크가 실측으로 해소되었으므로, 시스템에 이미 설치된 WebView2를 그대로 쓰는 **Evergreen 방식**으로 전환한다. 다운로드했던 Fixed Version 런타임 폴더는 삭제했다.

Evergreen이든 Fixed Version이든 화면을 그리는 엔진(Chromium 기반 WebView2)은 동일하므로, Plan B에서 만든 HTML/CSS/JS 프론트엔드는 이 전환과 완전히 무관하며 코드 변경이 필요 없다.

이 전환으로 배포 용량이 700~900MB → 30~60MB대로 줄고, 애초에 onedir을 택했던 이유(거대한 번들 런타임을 매번 압축 해제하면 느림)도 사라져 **onefile(exe 단일 파일)로 복귀**한다 — 원래 tkinter 버전과 동일한 "파일 하나 공유" 배포 경험을 유지한다.

## 2. 확정된 요구사항

- WebView2 런타임은 번들하지 않는다. `main.py`에 `WEBVIEW2_BROWSER_EXECUTABLE_FOLDER` 관련 코드를 추가하지 않는다 — pywebview가 시스템에 설치된 WebView2를 자동으로 찾아 쓰는 기본 동작을 그대로 둔다.
- `.spec`은 onefile 구조를 유지한다(`EXE()`만 사용, `COLLECT()` 추가 안 함).
- `datas`에 다음을 추가한다: `webapp/static`(index.html/css/js/참고표 json 전체), `demo_assets/*.xlsx`(A/B/전월 예시 3종 — 데모 영상은 제외).
- `hiddenimports`는 손으로 나열하지 않고 `PyInstaller.utils.hooks.collect_all()`을 `uvicorn`/`fastapi`/`pydantic`/`pydantic_core`/`webview`에 적용해 서브모듈을 통째로 수집한다. 이 프레임워크들은 동적 임포트가 많아(uvicorn이 프로토콜/루프 구현체를 런타임에 탐색하는 방식 등) hiddenimports를 하나씩 나열하면 빠뜨릴 때마다 재빌드가 필요한데, `collect_all`은 그 실패 루프를 대부분 없애준다.
- exe/버전 이름을 `통계조사관임금계산_v4.2` → `통계조사관임금계산_v5.0`으로 올린다.
- `requirements.txt`를 신설해 런타임 의존성(`fastapi`, `uvicorn`, `pywebview`, `openpyxl`, `pydantic`)을 버전 고정한다. 테스트 전용 의존성(`httpx`, `pytest`)은 포함하지 않는다.
- `wage_calculator/core/*`, `output/*`, `webapp/state.py`, `webapp/server.py`, `webapp/static/*`는 이 작업에서 수정하지 않는다.

## 3. 빌드 검증 방식

PyInstaller로 FastAPI/uvicorn 앱을 패키징하는 건 실제로 돌려보기 전까진 어떤 hiddenimport가 빠졌는지 완전히 예측할 수 없는 영역이다. 이 부분은 "정확한 코드"가 아니라 **"빌드 → 실행 → 에러 나면 원인 파악해서 `collect_all`/`hiddenimports`에 보강 → 재빌드"를 exe가 실제로 뜨고 데모 데이터(`demo_assets`)로 업로드부터 결과·산정근거 화면까지 정상 동작할 때까지 반복**하는 절차로 계획을 쓴다. Plan A의 소급계산 테스트에서 "실제 엔진 결과에 맞춰 조정을 허용"했던 것과 같은 방식의 예외다.

검증 기준(완료 조건):
1. `dist/통계조사관임금계산_v5.0.exe`가 콘솔 창 없이 pywebview 창을 띄운다.
2. `demo_assets`의 A/B 예시 파일로 업로드 → 특별휴가 확정 → 대상자 확인 → 계산 실행 → 결과 화면까지 정상 동작한다.
3. "산정근거 확인" 화면과 "엑셀 다운로드"도 정상 동작한다("설정" 화면에서 요율 등록이 먼저 필요할 수 있음).
4. 개발 환경(`python main.py`)의 동작과 결과가 동일하다(계산 로직은 이번 작업에서 손대지 않으므로 당연히 같아야 함).
