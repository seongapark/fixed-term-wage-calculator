# 프론트엔드(정적 SPA) + pywebview 부트스트랩 설계

> 관련 코드: `wage_calculator/webapp/static/*`(신규), `wage_calculator/main.py`(재작성), `wage_calculator/webapp/server.py`(정적 파일 마운트만 추가)
> 선행 문서: `docs/superpowers/specs/2026-08-10-pywebview-webapp-migration-design.md`(전체 아키텍처), `docs/superpowers/plans/2026-08-10-webapp-backend-migration.md`(Plan A, 완료됨)
> 불변 대상: `wage_calculator/core/*`, `wage_calculator/output/*`, `wage_calculator/webapp/state.py`, `wage_calculator/webapp/server.py`의 기존 20개 라우트 로직

## 1. 배경

Plan A(백엔드)가 완료되어 `wage_calculator/webapp/server.py`에 업로드/특별휴가/대상자/계산/결과/산정근거/설정/참고표를 아우르는 JSON API 20개가 전부 테스트로 검증된 상태다. 이번 Plan B는 그 위에 실제로 사람이 보는 화면을 얹고, `main.py`를 pywebview 부트스트랩으로 재작성해 "exe 하나 실행하면 뜨는 앱" 형태로 만드는 작업이다.

최초 설계 문서(§3)는 화면별 Jinja2 템플릿(`webapp/templates/`)을 가정했으나, 백엔드가 순수 JSON API로 완성된 지금은 서버가 HTML을 직접 만들 필요가 없다. 정적 HTML 1개 + JS가 `fetch()`로 API를 호출해 화면을 그리는 SPA 구조가 지금 백엔드 구조와 가장 일관되고 단순하다.

## 2. 확정된 요구사항

- **Jinja2 없음**: `webapp/templates/`는 만들지 않는다. `webapp/static/index.html` 정적 파일 1개 + JS가 전체 화면을 그린다.
- **빌드도구 없음**: npm/webpack 등 일절 사용하지 않는다. 순수 `<script>`/`<style>` 파일을 그대로 작성한다.
- **화면 흐름/디자인 톤**: 기존 설계 문서(§2, §4)의 ChatGPT/Claude 스타일 톤과 업로드→특별휴가→대상자→확인→결과→증빙 흐름을 그대로 따른다.
- **파일 다이얼로그와 `last_upload_dir`**: HTTP를 거치지 않고 `js_api` 브리지가 직접 처리한다(§4).
- **`core/`, `output/`, `webapp/state.py`, 기존 `webapp/server.py`의 20개 라우트**: 이번 작업에서 수정하지 않는다. `server.py`에는 정적 파일 마운트(`app.mount`) 한 줄만 추가한다.

## 3. 파일 구조

```
wage_calculator/webapp/static/
  index.html
  css/
    tokens.css      색상/여백/폰트 변수(디자인 토큰)
    base.css         리셋 + 공통 레이아웃(버튼/입력창/모달/토스트/탭/표)
  js/
    api.js           fetch() 래퍼 — 20개 라우트 호출 함수 모음
    router.js         화면 전환(단일 <main id="app"> 안에서 뷰 교체, 풀 리로드 없음)
    toast.js          에러/경고 배너
    upload.js
    specialLeave.js
    targets.js
    confirmModals.js  계약기간 수정 / 계약기간 확인 / 계산실행 확인 / 설정, 4종 모달
    result.js
    evidence.js
  reference/
    leave_category_guide.json   (Plan A Task 9에서 이미 완성, 변경 없음)
wage_calculator/main.py          재작성 — pywebview 부트스트랩
```

`gui/*.py`와 이름을 1:1로 맞춰 원본 화면과의 대응관계가 코드에서 바로 보이게 한다. `gui/*.py` 자체는 이번 작업에서 삭제하지 않는다(별도 정리 작업으로 남김).

## 4. main.py 부트스트랩 + js_api 브리지

```python
state = AppState()                          # create_app()과 js_api가 공유하는 단일 인스턴스
app = create_app(state)
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True))

port = find_free_port()                     # socket.bind(('127.0.0.1', 0))
Thread(target=uvicorn.run, args=(app,), kwargs={"host": "127.0.0.1", "port": port}, daemon=True).start()

class JSApi:
    def pick_file(self, kind: str):          # kind: "a" | "b" | "prev"
        start_dir = state.config_obj.last_upload_dir or None
        result = webview.windows[0].create_file_dialog(
            webview.OPEN_DIALOG, directory=start_dir or "", file_types=("Excel (*.xlsx)",)
        )
        if not result:
            return None
        path = result[0]
        state.config_obj.set_last_upload_dir(str(Path(path).parent))
        state.config_obj.save()
        return path

webview.create_window("통계조사관 임금계산", f"http://127.0.0.1:{port}/", js_api=JSApi(), width=1100, height=780)
webview.start()
```

- `state`를 `create_app()`과 `JSApi`가 공유하므로 `last_upload_dir` 읽기/쓰기가 별도 HTTP 라우트 없이 `Config` 객체에 바로 반영된다(Plan A에서 만든 `set_last_upload_dir`/`save()` 재사용).
- 파일 선택창은 `js_api`가 전담하고, 나머지는 전부 `fetch()`로 HTTP 호출한다.
- 창을 닫으면 `daemon=True` 서버 스레드가 메인 프로세스와 함께 정리된다. 별도 종료 처리 불필요.
- Plan C(패키징)에서 `frozen` 여부에 따라 WebView2 런타임 경로를 지정하는 코드만 이 구조 위에 추가하면 되도록 지금부터 이 형태로 짠다.

## 5. 화면 모듈 공통 규칙

- 각 JS 모듈은 `render(container)` 함수 하나를 export한다. `router.js`가 화면 전환 시 `container.innerHTML = ""` 후 새 모듈의 `render()`를 호출 — 원본 `gui/app.py`의 `_set_screen()`(기존 화면 destroy → 새 화면 pack)과 1:1 대응.
- `api.js`는 20개 라우트를 감싼 얇은 `fetch()` 함수 모음. 에러 시 FastAPI의 `{"detail": "..."}`를 파싱해 `toast.showError(detail)`을 호출하고 예외를 던진다.
- 서버가 검증하는 규칙(동명이인 차단, 특별휴가 미정 차단 등)은 프론트에서 다시 판단하지 않고 API 에러를 그대로 배너로 띄운다 — 검증 로직 중복 없음.
- 체크박스 선택, 탭 전환처럼 서버에 보낼 필요 없는 화면 국소 상태는 각 JS 모듈의 지역 변수로만 관리한다.
- 계약기간 수정·계약기간 확인·계산실행 확인·설정, 이 4종 모달은 `confirmModals.js` 하나에 모아 오버레이 `<div>`로 구현한다(별도 OS 창 없음).

### 특별휴가 참고표 호버 패널 (`specialLeave.js`)

```js
let guideCache = null;
async function ensureGuideLoaded() {
  if (!guideCache) guideCache = (await api.getLeaveGuide()).entries;
  return guideCache;
}

let hideTimer = null;
function showPanel() { clearTimeout(hideTimer); panelEl.style.display = "block"; }
function scheduleHide() { hideTimer = setTimeout(() => panelEl.style.display = "none", 150); }

icon.addEventListener("mouseenter", async () => { await ensureGuideLoaded(); renderPanelRows(guideCache); showPanel(); });
icon.addEventListener("mouseleave", scheduleHide);
panelEl.addEventListener("mouseenter", showPanel);   // 패널로 마우스 이동 시 유지
panelEl.addEventListener("mouseleave", scheduleHide);
```

아이콘/패널 둘 다에 `mouseenter`가 `clearTimeout`을 걸어서, 아이콘→패널로 마우스가 이동하는 짧은 순간에도 안 닫힌다. 표 데이터는 `/api/reference/leave-guide`를 한 번만 불러와 모듈 변수에 캐시한다.

## 6. 테스트 방식

JS 유닛테스트 프레임워크는 도입하지 않는다(§2의 "빌드도구 없음" 원칙과 상충하고, 검증 로직이 전부 서버에 있어 JS는 그리기만 하기 때문).

1. **자동화(최소)**: `wage_calculator/tests/test_webapp_static_serving.py`를 추가해 FastAPI `TestClient`로 `GET /`이 `index.html`을 반환하는지, `GET /static/js/api.js` 등 핵심 정적 파일이 200으로 서빙되는지만 확인한다.
2. **Browser 도구로 실제 화면 검증(메인 방법)**: pywebview 창의 내용물은 `http://127.0.0.1:<port>`에 뜬 평범한 웹페이지다. 구현 중에는 FastAPI 서버만 단독 실행하고 Claude Browser 도구로 그 주소를 직접 열어 스크린샷·클릭·폼 입력으로 검증한다. `demo_assets`의 더미 A/B 파일로 업로드→특별휴가 마킹→대상자→계산→결과→산정근거 전체 흐름을 실제로 눌러보며 확인한다.
3. **pywebview 자체는 마지막에 한 번만**: Browser 도구로는 확인 못 하는 유일한 부분(`js_api.pick_file`의 OS 네이티브 파일 다이얼로그)만 실제 pywebview 창을 띄워 별도 확인한다.
