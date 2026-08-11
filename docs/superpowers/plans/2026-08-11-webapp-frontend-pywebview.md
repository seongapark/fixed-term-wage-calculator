# 프론트엔드(정적 SPA) + pywebview 부트스트랩 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Plan A에서 완성된 20개 JSON API 라우트 위에 정적 HTML+순수 JS SPA를 얹고, `main.py`를 pywebview 부트스트랩으로 재작성해 exe 하나로 실행되는 완전한 화면을 만든다.

**Architecture:** 빌드도구 없는 순수 JS(ES 모듈, `<script type="module">`)로 화면마다 파일 하나씩 작성하고, 하나의 `<main id="app">` 안에서 `router.js`가 뷰를 교체한다. 서버 검증 로직은 절대 프론트에서 다시 구현하지 않고 API 에러를 그대로 배너로 띄운다. `main.py`는 FastAPI를 백그라운드 스레드로 띄우고 pywebview 창을 그 주소로 연다.

**Tech Stack:** 순수 HTML/CSS/JS(ES modules, 빌드도구 없음), FastAPI `StaticFiles`, `uvicorn`, `pywebview`.

## Global Constraints

- `wage_calculator/core/*`, `wage_calculator/output/*`, `wage_calculator/webapp/state.py`는 이 계획에서 전혀 수정하지 않는다.
- `wage_calculator/webapp/server.py`의 기존 20개 라우트 로직은 수정하지 않는다. 이 계획에서 유일하게 허용된 `server.py` 변경은 `StaticFiles` 마운트 한 줄(Task 1)이다.
- npm/webpack 등 빌드도구를 쓰지 않는다. 모든 JS는 `<script type="module">`로 그대로 로드되는 ES 모듈이다.
- 이 저장소의 Python 테스트는 pytest 설정 파일 없이 스크립트 방식(`sys.path.insert` + `assert` + `if __name__ == "__main__":`)을 따른다. 이 계획의 Task 1, Task 8만 Python 테스트가 있고 같은 관례를 따른다. Task 2~7은 자동 Python 테스트가 없다(JS 코드라 대상이 아님) — 대신 Claude Browser 도구로 실제 화면을 직접 조작해 검증한다.
- 새 런타임 의존성 `uvicorn`, `pywebview`가 필요하다. Task 8을 시작하기 전에 `pip install uvicorn pywebview`를 실행해 둔다(`fastapi`/`httpx`/`pytest`는 Plan A에서 이미 설치됨).
- 테스트 픽스처는 `demo_assets/개인정보_예시(A).xlsx`, `demo_assets/근무상황_예시(B).xlsx`(5명, 특별휴가 1건 포함, 이미 검증됨)를 그대로 사용한다.
- Browser 도구로 화면을 검증할 때는 pywebview 없이 FastAPI 서버만 단독 실행한다(`python -m uvicorn webapp.server:create_app --factory --port 8811`, `wage_calculator/` 디렉터리에서 실행). pywebview 전용 기능(`js_api.pick_file`)은 이 방식으로 검증할 수 없다 — Task 8에서 실제 창을 띄워 별도 확인한다.
- 참조 문서: `docs/superpowers/specs/2026-08-11-webapp-frontend-pywebview-design.md`

---

### Task 1: 정적 파일 서빙 뼈대 (index.html + CSS + server.py 마운트)

**Files:**
- Create: `wage_calculator/webapp/static/index.html`
- Create: `wage_calculator/webapp/static/css/tokens.css`
- Create: `wage_calculator/webapp/static/css/base.css`
- Modify: `wage_calculator/webapp/server.py`
- Test: `wage_calculator/tests/test_webapp_static_serving.py`

**Interfaces:**
- Produces: `create_app()`이 반환하는 앱이 `/`에서 `index.html`을, `/css/...`·`/js/...`에서 정적 파일을 서빙한다(마운트 경로가 `/`이므로 `webapp/static/css/tokens.css` → URL `/css/tokens.css`).

- [ ] **Step 1: `index.html` 작성**

`wage_calculator/webapp/static/index.html`:

```html
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <title>통계조사관 임금계산</title>
  <link rel="stylesheet" href="/css/tokens.css">
  <link rel="stylesheet" href="/css/base.css">
</head>
<body>
  <header class="topbar">
    <span class="topbar-title">통계조사관 임금계산</span>
    <button id="settings-btn" class="btn btn-ghost" type="button">설정</button>
  </header>
  <main id="app"></main>
  <div id="toast-container" class="toast-container"></div>
  <div id="modal-root"></div>
  <script type="module" src="/js/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: `tokens.css` 작성**

`wage_calculator/webapp/static/css/tokens.css`:

```css
:root {
  --color-bg: #ffffff;
  --color-bg-subtle: #f7f7f8;
  --color-border: #e5e5e5;
  --color-text: #1a1a1a;
  --color-text-muted: #6b6b6b;
  --color-primary: #10a37f;
  --color-primary-hover: #0d8c6d;
  --color-primary-bg: #e6f4f1;
  --color-danger: #d92d20;
  --color-danger-bg: #fef3f2;
  --color-warning: #b54708;
  --color-warning-bg: #fffaeb;
  --radius-sm: 6px;
  --radius: 10px;
  --shadow-card: 0 1px 3px rgba(0,0,0,0.08);
  --shadow-modal: 0 8px 24px rgba(0,0,0,0.16);
  --font: -apple-system, "Segoe UI", "Malgun Gothic", sans-serif;
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-6: 24px;
  --space-8: 32px;
}
```

- [ ] **Step 3: `base.css` 작성**

`wage_calculator/webapp/static/css/base.css`:

```css
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: var(--font);
  color: var(--color-text);
  background: var(--color-bg-subtle);
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-6);
  background: var(--color-bg);
  border-bottom: 1px solid var(--color-border);
}
.topbar-title { font-weight: 600; font-size: 15px; }

#app {
  max-width: 960px;
  margin: 0 auto;
  padding: var(--space-6);
}

.card {
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  box-shadow: var(--shadow-card);
  padding: var(--space-6);
  margin-bottom: var(--space-4);
  position: relative;
}

.screen-title { font-size: 18px; font-weight: 700; margin: 0 0 var(--space-2); }
.screen-subtitle { color: var(--color-text-muted); font-size: 13px; margin: 0 0 var(--space-4); white-space: pre-line; }

.form-row { display: flex; align-items: center; gap: var(--space-2); margin-bottom: var(--space-3); }
.form-row label { width: 160px; flex-shrink: 0; font-size: 13px; color: var(--color-text-muted); }

.input {
  flex: 1;
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-family: inherit;
}
.input:focus { outline: 2px solid var(--color-primary); outline-offset: -1px; }
.input-narrow { flex: 0 0 90px; }

.btn {
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius-sm);
  border: 1px solid var(--color-border);
  background: var(--color-bg);
  color: var(--color-text);
  font-size: 13px;
  cursor: pointer;
}
.btn:hover { background: var(--color-bg-subtle); }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary { background: var(--color-primary); border-color: var(--color-primary); color: #fff; }
.btn-primary:hover { background: var(--color-primary-hover); }
.btn-ghost { border-color: transparent; background: transparent; }
.btn-danger { color: var(--color-danger); border-color: var(--color-danger); background: var(--color-danger-bg); }

.actions { display: flex; justify-content: flex-end; gap: var(--space-2); margin-top: var(--space-4); }
.actions-split { display: flex; justify-content: space-between; align-items: center; margin-top: var(--space-4); }

table.table { width: 100%; border-collapse: collapse; font-size: 13px; }
table.table th, table.table td {
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--color-border);
  text-align: center;
}
table.table th { color: var(--color-text-muted); font-weight: 600; background: var(--color-bg-subtle); }
table.table tbody tr:hover { background: var(--color-bg-subtle); }

.status-pill {
  display: inline-block;
  padding: 2px var(--space-2);
  border-radius: 999px;
  font-size: 12px;
  cursor: pointer;
  background: var(--color-bg-subtle);
  border: 1px solid var(--color-border);
}
.status-pill.paid { background: var(--color-primary-bg); color: var(--color-primary-hover); border-color: var(--color-primary); }
.status-pill.unpaid { background: var(--color-warning-bg); color: var(--color-warning); border-color: var(--color-warning); }

.toast-container {
  position: fixed;
  top: var(--space-4);
  right: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  z-index: 1000;
}
.toast {
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow-modal);
  font-size: 13px;
  max-width: 360px;
  white-space: pre-line;
}
.toast-error { background: var(--color-danger-bg); color: var(--color-danger); border: 1px solid var(--color-danger); }
.toast-warning { background: var(--color-warning-bg); color: var(--color-warning); border: 1px solid var(--color-warning); }
.toast-success { background: var(--color-primary-bg); color: var(--color-primary-hover); border: 1px solid var(--color-primary); }

.modal-overlay {
  position: fixed; inset: 0;
  background: rgba(0,0,0,0.4);
  display: flex; align-items: center; justify-content: center;
  z-index: 900;
}
.modal {
  background: var(--color-bg);
  border-radius: var(--radius);
  box-shadow: var(--shadow-modal);
  padding: var(--space-6);
  max-width: 480px;
  width: 90%;
  max-height: 80vh;
  overflow-y: auto;
}
.modal-title { font-weight: 700; font-size: 15px; margin: 0 0 var(--space-4); }
.modal-body { font-size: 13px; line-height: 1.6; white-space: pre-line; }
.modal-actions { display: flex; justify-content: flex-end; gap: var(--space-2); margin-top: var(--space-6); }

.tabs { display: flex; gap: var(--space-2); border-bottom: 1px solid var(--color-border); margin-bottom: var(--space-4); }
.tab { padding: var(--space-2) var(--space-3); cursor: pointer; font-size: 13px; color: var(--color-text-muted); border-bottom: 2px solid transparent; }
.tab.active { color: var(--color-primary); border-bottom-color: var(--color-primary); font-weight: 600; }

.info-icon {
  display: inline-flex; align-items: center; justify-content: center;
  width: 20px; height: 20px;
  border-radius: 50%;
  border: 1px solid var(--color-border);
  color: var(--color-text-muted);
  font-size: 12px;
  cursor: default;
}
.info-panel {
  display: none;
  position: absolute;
  z-index: 800;
  width: 520px;
  max-height: 420px;
  overflow-y: auto;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  box-shadow: var(--shadow-modal);
  padding: var(--space-4);
  font-size: 12px;
}
.info-panel table.table td, .info-panel table.table th { text-align: left; }

.evidence-layout { display: flex; gap: var(--space-4); align-items: flex-start; }
.evidence-col { min-width: 0; }

.text-muted { color: var(--color-text-muted); }
.title-row { display: flex; align-items: center; gap: var(--space-2); }
```

- [ ] **Step 4: `server.py`에 정적 파일 마운트 추가**

`wage_calculator/webapp/server.py` 맨 위 import에 추가(`from fastapi import FastAPI, HTTPException` 다음 줄):

```python
from fastapi.staticfiles import StaticFiles
```

`create_app()` 함수 안, `@app.get("/api/reference/leave-guide")` 라우트 정의가 끝난 직후 · `return app` 바로 앞에 추가:

```python
    static_dir = Path(__file__).resolve().parent / "static"
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
```

- [ ] **Step 5: 실패하는 테스트 작성 후 확인**

`wage_calculator/tests/test_webapp_static_serving.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from webapp.server import create_app


def test_root_serves_index_html():
    app = create_app()
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "통계조사관 임금계산" in resp.text
    print("OK: test_root_serves_index_html")


def test_static_css_is_served():
    app = create_app()
    client = TestClient(app)
    for path in ["/css/tokens.css", "/css/base.css"]:
        resp = client.get(path)
        assert resp.status_code == 200, f"{path} -> {resp.status_code}"
    print("OK: test_static_css_is_served")


def test_api_routes_still_work_after_static_mount():
    app = create_app()
    client = TestClient(app)
    resp = client.get("/api/settings")
    assert resp.status_code == 200
    print("OK: test_api_routes_still_work_after_static_mount")


if __name__ == "__main__":
    test_root_serves_index_html()
    test_static_css_is_served()
    test_api_routes_still_work_after_static_mount()
    print("ALL OK")
```

Run: `python wage_calculator/tests/test_webapp_static_serving.py` (Step 4 없이 실행하면 실패)
Expected(수정 전): `404` — `/` 라우트가 아직 없음

- [ ] **Step 6: 테스트 통과 확인**

Run: `python wage_calculator/tests/test_webapp_static_serving.py`
Expected: `ALL OK`

- [ ] **Step 7: 커밋**

```bash
git add wage_calculator/webapp/static/index.html wage_calculator/webapp/static/css/tokens.css wage_calculator/webapp/static/css/base.css wage_calculator/webapp/server.py wage_calculator/tests/test_webapp_static_serving.py
git commit -m "feat: 정적 파일 서빙 뼈대(index.html/CSS/StaticFiles 마운트) 추가"
```

---

### Task 2: 핵심 JS 인프라 + 업로드 화면

**Files:**
- Create: `wage_calculator/webapp/static/js/utils.js`
- Create: `wage_calculator/webapp/static/js/api.js`
- Create: `wage_calculator/webapp/static/js/toast.js`
- Create: `wage_calculator/webapp/static/js/router.js`
- Create: `wage_calculator/webapp/static/js/upload.js`
- Create: `wage_calculator/webapp/static/js/app.js`

**Interfaces:**
- Consumes: Task 1의 정적 서빙, `POST /api/upload`
- Produces: `escapeHtml(s)`(utils.js), `api.upload/reset/getSpecialLeave/confirmSpecialLeave/getTargets/batchAssign/editContract/proceed/getConfirmInfo/calculate/getResults/download/getEvidence/getSettings/addSurvey/deleteSurvey/addRate/deleteRate/addHoliday/deleteHoliday/getLeaveGuide`(api.js), `showError/showWarning/showSuccess(message)`(toast.js), `registerRoute(name, renderFn)` / `navigate(name, params)`(router.js) — 이후 모든 화면 모듈이 이 시그니처를 그대로 사용한다.

- [ ] **Step 1: `utils.js` 작성**

`wage_calculator/webapp/static/js/utils.js`:

```js
export function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}
```

- [ ] **Step 2: `api.js` 작성**

`wage_calculator/webapp/static/js/api.js`:

```js
async function request(method, path, body) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const resp = await fetch(path, opts);
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    throw new Error(data.detail || `요청 실패 (${resp.status})`);
  }
  return data;
}

export const api = {
  upload: (aPath, bPath, prevPath) => request("POST", "/api/upload", { a_path: aPath, b_path: bPath, prev_path: prevPath || null }),
  reset: () => request("POST", "/api/reset"),
  getSpecialLeave: () => request("GET", "/api/special-leave"),
  confirmSpecialLeave: (statuses) => request("POST", "/api/special-leave/confirm", { statuses }),
  getTargets: () => request("GET", "/api/targets"),
  batchAssign: (keys, surveyName) => request("POST", "/api/targets/batch-assign", { keys, survey_name: surveyName }),
  editContract: (key, start, end) => request("POST", "/api/targets/contract-edit", { key, start, end }),
  proceed: (year, month) => request("POST", "/api/targets/proceed", { year, month }),
  getConfirmInfo: () => request("GET", "/api/confirm-info"),
  calculate: () => request("POST", "/api/calculate"),
  getResults: () => request("GET", "/api/results"),
  download: () => request("POST", "/api/download"),
  getEvidence: (key) => request("GET", `/api/evidence?key=${encodeURIComponent(key)}`),
  getSettings: () => request("GET", "/api/settings"),
  addSurvey: (name, start, end) => request("POST", "/api/settings/survey", { name, start, end }),
  deleteSurvey: (name) => request("DELETE", `/api/settings/survey/${encodeURIComponent(name)}`),
  addRate: (year, dailyWage, mealAllowance) => request("POST", "/api/settings/rate", { year, daily_wage: dailyWage, meal_allowance: mealAllowance }),
  deleteRate: (year) => request("DELETE", `/api/settings/rate/${year}`),
  addHoliday: (date) => request("POST", "/api/settings/holiday", { date }),
  deleteHoliday: (date) => request("DELETE", `/api/settings/holiday/${encodeURIComponent(date)}`),
  getLeaveGuide: () => request("GET", "/api/reference/leave-guide"),
};
```

- [ ] **Step 3: `toast.js` 작성**

`wage_calculator/webapp/static/js/toast.js`:

```js
export function showError(message) { show(message, "toast-error"); }
export function showWarning(message) { show(message, "toast-warning"); }
export function showSuccess(message) { show(message, "toast-success"); }

function show(message, cls) {
  const container = document.getElementById("toast-container");
  const el = document.createElement("div");
  el.className = `toast ${cls}`;
  el.textContent = message;
  container.appendChild(el);
  setTimeout(() => el.remove(), 5000);
}
```

- [ ] **Step 4: `router.js` 작성**

`wage_calculator/webapp/static/js/router.js`:

```js
const routes = {};

export function registerRoute(name, renderFn) {
  routes[name] = renderFn;
}

export function navigate(name, params) {
  const container = document.getElementById("app");
  container.innerHTML = "";
  const renderFn = routes[name];
  if (!renderFn) {
    console.error(`알 수 없는 화면: ${name}`);
    return;
  }
  renderFn(container, params);
}
```

- [ ] **Step 5: `upload.js` 작성**

`wage_calculator/webapp/static/js/upload.js`:

```js
import { api } from "./api.js";
import { navigate } from "./router.js";
import { showError, showWarning } from "./toast.js";

export function render(container) {
  container.innerHTML = `
    <div class="card">
      <h1 class="screen-title">통계조사관 임금계산</h1>
      <div class="form-row">
        <label>개인정보 파일 (A)</label>
        <input class="input" id="a-path" type="text">
        <button class="btn" id="a-browse" type="button">찾아보기</button>
      </div>
      <div class="form-row">
        <label>근무상황 파일 (B)</label>
        <input class="input" id="b-path" type="text">
        <button class="btn" id="b-browse" type="button">찾아보기</button>
      </div>
      <div class="form-row">
        <label>전월 임금내역 (선택)</label>
        <input class="input" id="prev-path" type="text">
        <button class="btn" id="prev-browse" type="button">찾아보기</button>
      </div>
      <p class="text-muted" style="margin: 0 0 var(--space-4) 176px;">※ 비워두면 소급계산을 하지 않습니다.</p>
      <div class="actions">
        <button class="btn btn-primary" id="next-btn" type="button">다음</button>
      </div>
    </div>
  `;

  const aInput = container.querySelector("#a-path");
  const bInput = container.querySelector("#b-path");
  const prevInput = container.querySelector("#prev-path");

  container.querySelector("#a-browse").addEventListener("click", () => pickFile("a", aInput));
  container.querySelector("#b-browse").addEventListener("click", () => pickFile("b", bInput));
  container.querySelector("#prev-browse").addEventListener("click", () => pickFile("prev", prevInput));

  container.querySelector("#next-btn").addEventListener("click", async () => {
    const aPath = aInput.value.trim();
    const bPath = bInput.value.trim();
    const prevPath = prevInput.value.trim();
    if (!aPath || !bPath) {
      showWarning("개인정보(A), 근무상황(B) 파일을 모두 선택하세요.");
      return;
    }
    try {
      const result = await api.upload(aPath, bPath, prevPath || null);
      if (result.ambiguous_names && result.ambiguous_names.length > 0) {
        showError(
          "근무상황(B)에 같은 성명·다른 생년월일을 가진 동명이인이 있는데, " +
          "개인정보(A)만으로는 누가 누군지 구분할 수 없습니다: " +
          result.ambiguous_names.join(", ") +
          "\n\nA파일에 '생년월일' 컬럼을 추가하고 각 동명이인의 생년월일을 " +
          "정확히 입력한 뒤 다시 업로드해야 임금 산정을 진행할 수 있습니다."
        );
        return;
      }
      if (result.has_pending_special_leave) {
        navigate("specialLeave");
      } else {
        navigate("targets");
      }
    } catch (e) {
      showError(e.message);
    }
  });
}

async function pickFile(kind, inputEl) {
  if (window.pywebview && window.pywebview.api && window.pywebview.api.pick_file) {
    const path = await window.pywebview.api.pick_file(kind);
    if (path) inputEl.value = path;
  } else {
    showWarning("이 화면은 pywebview 앱에서 실행할 때만 파일 탐색기가 열립니다. 지금은 경로를 직접 입력해주세요.");
  }
}
```

- [ ] **Step 6: `app.js` 작성 (진입점 — 지금은 업로드 화면만 등록)**

`wage_calculator/webapp/static/js/app.js`:

```js
import { registerRoute, navigate } from "./router.js";
import { render as renderUpload } from "./upload.js";

registerRoute("upload", renderUpload);

navigate("upload");
```

- [ ] **Step 7: 개발 서버 기동**

Run (백그라운드): `cd wage_calculator && python -m uvicorn webapp.server:create_app --factory --port 8811`
Expected: `Uvicorn running on http://127.0.0.1:8811`

- [ ] **Step 8: Browser 도구로 업로드 화면 검증**

1. `mcp__Claude_Browser__navigate`로 `http://127.0.0.1:8811/` 접속
2. `mcp__Claude_Browser__computer` screenshot — 카드 안에 제목 "통계조사관 임금계산", 3개 입력행(개인정보 파일(A)/근무상황 파일(B)/전월 임금내역), "다음" 버튼이 보여야 함
3. "다음" 버튼 클릭(입력값 없이) → 우측 상단에 노란 경고 토스트 "개인정보(A), 근무상황(B) 파일을 모두 선택하세요." 표시 확인
4. A/B 입력창에 각각 `<프로젝트 절대경로>\demo_assets\개인정보_예시(A).xlsx`, `...\근무상황_예시(B).xlsx` 직접 입력(pywebview 없이 브라우저로 테스트 중이므로 "찾아보기"는 경고 토스트만 뜸 — 이것도 함께 확인)
5. "다음" 클릭 → `mcp__Claude_Browser__read_network_requests`로 `POST /api/upload` 요청이 200으로 응답했는지, 응답 바디에 `has_pending_special_leave: true`가 왔는지 확인(데모 데이터는 최지은 건 1개가 있어 true여야 함)
6. 화면 전환은 아직 안 됨(다음 화면이 Task 3에서 만들어짐) — 콘솔에 `알 수 없는 화면: specialLeave` 에러가 찍히는 것은 정상(`mcp__Claude_Browser__read_console_messages`로 확인)

- [ ] **Step 9: 커밋**

```bash
git add wage_calculator/webapp/static/js/utils.js wage_calculator/webapp/static/js/api.js wage_calculator/webapp/static/js/toast.js wage_calculator/webapp/static/js/router.js wage_calculator/webapp/static/js/upload.js wage_calculator/webapp/static/js/app.js
git commit -m "feat: JS 핵심 인프라(api/toast/router) + 업로드 화면 추가"
```

---

### Task 3: 특별휴가 마킹 화면 + 참고표 호버 패널

**Files:**
- Create: `wage_calculator/webapp/static/js/specialLeave.js`
- Modify: `wage_calculator/webapp/static/js/app.js`

**Interfaces:**
- Consumes: `api.getSpecialLeave/confirmSpecialLeave/getLeaveGuide`(Task 2), `navigate`(Task 2), `showWarning/showError`(Task 2)
- Produces: `render(container)` — `app.js`가 `"specialLeave"`로 등록

- [ ] **Step 1: `specialLeave.js` 작성**

`wage_calculator/webapp/static/js/specialLeave.js`:

```js
import { api } from "./api.js";
import { navigate } from "./router.js";
import { showWarning, showError } from "./toast.js";
import { escapeHtml } from "./utils.js";

const STATUS_LABEL = { null: "미정", "유급특별휴가": "유급", "무급특별휴가": "무급" };
const NEXT_STATUS = { null: "유급특별휴가", "유급특별휴가": "무급특별휴가", "무급특별휴가": "유급특별휴가" };

let guideCache = null;
async function ensureGuideLoaded() {
  if (!guideCache) guideCache = (await api.getLeaveGuide()).entries;
  return guideCache;
}

export async function render(container) {
  const { groups } = await api.getSpecialLeave();
  const statuses = groups.map(() => null);

  container.innerHTML = `
    <div class="card">
      <div class="title-row">
        <h1 class="screen-title" style="margin:0;">특별휴가 유급/무급 확인</h1>
        <span class="info-icon" id="guide-icon">ⓘ</span>
      </div>
      <div class="info-panel" id="guide-panel"></div>
      <p class="screen-subtitle">근무상황 파일에 "특별휴가"로만 기록되어 유급/무급을 알 수 없는 건입니다.
행을 클릭하면 미정 → 유급 → 무급 순으로 바뀝니다. 모두 지정해야 다음으로 진행됩니다.</p>
      <table class="table">
        <thead><tr><th>성명</th><th>기간</th><th>사유(원본)</th><th>비고(원본)</th><th>유급/무급</th></tr></thead>
        <tbody id="rows"></tbody>
      </table>
      <div class="actions">
        <button class="btn btn-primary" id="next-btn" type="button" disabled>다음</button>
      </div>
    </div>
  `;

  const icon = container.querySelector("#guide-icon");
  const panel = container.querySelector("#guide-panel");
  let hideTimer = null;
  const showPanel = () => { clearTimeout(hideTimer); panel.style.display = "block"; };
  const scheduleHide = () => { hideTimer = setTimeout(() => { panel.style.display = "none"; }, 150); };

  icon.addEventListener("mouseenter", async () => {
    const entries = await ensureGuideLoaded();
    panel.innerHTML = `<table class="table"><thead><tr><th>종별</th><th>세부</th><th>설명</th><th>공제여부</th><th>시간입력</th></tr></thead><tbody>${
      entries.map(e => `<tr><td>${escapeHtml(e.category)}</td><td>${escapeHtml(e.subtype)}${e.detail ? " · " + escapeHtml(e.detail) : ""}</td><td>${escapeHtml(e.description)}</td><td>${escapeHtml(e.deduction)}</td><td>${escapeHtml(e.time_entry)}${e.note ? "<br><span class=\"text-muted\">" + escapeHtml(e.note) + "</span>" : ""}</td></tr>`).join("")
    }</tbody></table>`;
    showPanel();
  });
  icon.addEventListener("mouseleave", scheduleHide);
  panel.addEventListener("mouseenter", showPanel);
  panel.addEventListener("mouseleave", scheduleHide);

  const tbody = container.querySelector("#rows");
  const nextBtn = container.querySelector("#next-btn");

  function renderRows() {
    tbody.innerHTML = groups.map((g, idx) => {
      const period = g.start === g.end ? g.start : `${g.start}~${g.end}`;
      const status = statuses[idx];
      const cls = status === "유급특별휴가" ? "paid" : status === "무급특별휴가" ? "unpaid" : "";
      return `<tr>
        <td>${escapeHtml(g.person_name)}</td>
        <td>${period}</td>
        <td>${escapeHtml(g.reason)}</td>
        <td>${escapeHtml(g.note)}</td>
        <td><span class="status-pill ${cls}" data-idx="${idx}">${STATUS_LABEL[status]}</span></td>
      </tr>`;
    }).join("");
    nextBtn.disabled = statuses.some(s => s === null);
  }
  renderRows();

  tbody.addEventListener("click", (evt) => {
    const pill = evt.target.closest(".status-pill");
    if (!pill) return;
    const idx = Number(pill.dataset.idx);
    statuses[idx] = NEXT_STATUS[statuses[idx]];
    renderRows();
  });

  nextBtn.addEventListener("click", async () => {
    if (statuses.some(s => s === null)) {
      showWarning("모든 건에 유급/무급을 지정해야 진행할 수 있습니다.");
      return;
    }
    try {
      await api.confirmSpecialLeave(statuses);
      navigate("targets");
    } catch (e) {
      showError(e.message);
    }
  });
}
```

- [ ] **Step 2: `app.js`에 등록**

`wage_calculator/webapp/static/js/app.js` 전체를 다음으로 교체:

```js
import { registerRoute, navigate } from "./router.js";
import { render as renderUpload } from "./upload.js";
import { render as renderSpecialLeave } from "./specialLeave.js";

registerRoute("upload", renderUpload);
registerRoute("specialLeave", renderSpecialLeave);

navigate("upload");
```

- [ ] **Step 3: Browser 도구로 검증**

1. 개발 서버가 이미 떠 있지 않다면 Task 2 Step 7과 동일하게 기동
2. `http://127.0.0.1:8811/`에서 업로드 화면에 demo_assets 경로 입력 후 "다음" 클릭
3. 특별휴가 화면으로 전환되는지 screenshot으로 확인 — 최지은 1건, 상태 "미정"
4. 상태 셀 클릭 → "유급"으로 바뀌는지 확인, 한 번 더 클릭 → "무급"으로 바뀌는지 확인
5. ⓘ 아이콘에 마우스를 올리면(`mcp__Claude_Browser__computer` hover) 참고표 패널이 뜨는지, 패널로 마우스를 이동해도 안 닫히는지 확인
6. "다음" 클릭 → `read_network_requests`로 `POST /api/special-leave/confirm`이 `{"statuses":["유급특별휴가"]}` (또는 마지막으로 선택한 값)으로 200 응답했는지 확인

- [ ] **Step 4: 커밋**

```bash
git add wage_calculator/webapp/static/js/specialLeave.js wage_calculator/webapp/static/js/app.js
git commit -m "feat: 특별휴가 마킹 화면 + 참고표 호버 패널 추가"
```

---

### Task 4: 공통 모달 4종 (계약기간 수정 / 확인창 2종 / 새로계산 확인 / 설정)

**Files:**
- Create: `wage_calculator/webapp/static/js/confirmModals.js`
- Modify: `wage_calculator/webapp/static/js/app.js`

**Interfaces:**
- Consumes: `api.editContract/getConfirmInfo/getSettings/addSurvey/deleteSurvey/addRate/deleteRate/addHoliday/deleteHoliday`(Task 2)
- Produces: `openContractEditModal(person, onSave)`, `openUnassignedConfirmModal(names, onProceed)`, `openContractPeriodCheckModal(onProceed)`, `openConfirmRunModal(onRun)`, `openResetConfirmModal(onConfirm)`, `openSettingsModal()` — Task 5/6이 이 함수들을 그대로 가져다 쓴다.

- [ ] **Step 1: `confirmModals.js` 작성**

`wage_calculator/webapp/static/js/confirmModals.js`:

```js
import { api } from "./api.js";
import { showError } from "./toast.js";
import { escapeHtml } from "./utils.js";

function openModal(innerHtml) {
  const root = document.getElementById("modal-root");
  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";
  overlay.innerHTML = `<div class="modal">${innerHtml}</div>`;
  root.appendChild(overlay);
  overlay.addEventListener("click", (evt) => {
    if (evt.target === overlay) overlay.remove();
  });
  return overlay;
}

export function openContractEditModal(person, onSave) {
  const overlay = openModal(`
    <h2 class="modal-title">계약기간 수정 - ${escapeHtml(person.label)}</h2>
    <div class="form-row"><label>계약 시작일(YYYY-MM-DD)</label><input class="input" id="edit-start" value="${person.contract_start}"></div>
    <div class="form-row"><label>계약 마지막일(YYYY-MM-DD)</label><input class="input" id="edit-end" value="${person.contract_end}"></div>
    <div class="modal-actions">
      <button class="btn" id="edit-cancel" type="button">취소</button>
      <button class="btn btn-primary" id="edit-save" type="button">저장</button>
    </div>
  `);
  overlay.querySelector("#edit-cancel").addEventListener("click", () => overlay.remove());
  overlay.querySelector("#edit-save").addEventListener("click", async () => {
    const start = overlay.querySelector("#edit-start").value.trim();
    const end = overlay.querySelector("#edit-end").value.trim();
    try {
      await api.editContract(person.key, start, end);
      overlay.remove();
      onSave();
    } catch (e) {
      showError(e.message);
    }
  });
}

export function openUnassignedConfirmModal(names, onProceed) {
  const overlay = openModal(`
    <h2 class="modal-title">담당조사 미지정 인원 있음</h2>
    <p class="modal-body">담당조사가 지정되지 않은 인원은 이번 계산에서 제외됩니다: ${escapeHtml(names.join(", "))}
계속하시겠습니까?</p>
    <div class="modal-actions">
      <button class="btn" id="unassigned-no" type="button">아니오</button>
      <button class="btn btn-primary" id="unassigned-yes" type="button">계속</button>
    </div>
  `);
  overlay.querySelector("#unassigned-no").addEventListener("click", () => overlay.remove());
  overlay.querySelector("#unassigned-yes").addEventListener("click", () => { overlay.remove(); onProceed(); });
}

export function openContractPeriodCheckModal(onProceed) {
  const overlay = openModal(`
    <h2 class="modal-title">계약기간 확인</h2>
    <p class="modal-body">중도퇴사자와 추가입사자의 계약기간을 정확히 입력했는지 확인하세요.

계약기간이 틀리면 급여계산기간과 주휴/연차 판정이 모두 잘못 나옵니다.</p>
    <div class="modal-actions">
      <button class="btn" id="check-no" type="button">아니오(다시입력)</button>
      <button class="btn btn-primary" id="check-yes" type="button">네(진행)</button>
    </div>
  `);
  overlay.querySelector("#check-no").addEventListener("click", () => overlay.remove());
  overlay.querySelector("#check-yes").addEventListener("click", () => { overlay.remove(); onProceed(); });
}

export async function openConfirmRunModal(onRun) {
  let info;
  try {
    info = await api.getConfirmInfo();
  } catch (e) {
    showError(e.message);
    return;
  }
  const holidaysText = info.holidays.length
    ? `[이번 달(${info.year}년 ${info.month}월) 공휴일]\n${info.holidays.join(", ")}`
    : `[이번 달(${info.year}년 ${info.month}월) 공휴일 없음]`;
  const overriddenText = info.overridden_names.length
    ? `[계약기간을 개별 수정한 인원]\n${info.overridden_names.join(", ")}`
    : `[계약기간을 개별 수정한 인원]\n없음`;
  const overlay = openModal(`
    <h2 class="modal-title">계산 실행 확인</h2>
    <div class="modal-body">${holidaysText}

[현재 적용 요율(${info.year}년)]
일급: ${info.daily_wage.toLocaleString()}원 / 월 식대: ${info.meal_allowance.toLocaleString()}원

${overriddenText}</div>
    <div class="modal-actions">
      <button class="btn" id="run-cancel" type="button">취소</button>
      <button class="btn btn-primary" id="run-go" type="button">계속(계산 실행)</button>
    </div>
  `);
  overlay.querySelector("#run-cancel").addEventListener("click", () => overlay.remove());
  overlay.querySelector("#run-go").addEventListener("click", () => { overlay.remove(); onRun(); });
}

export function openResetConfirmModal(onConfirm) {
  const overlay = openModal(`
    <h2 class="modal-title">새로 계산</h2>
    <p class="modal-body">처음(파일 업로드)부터 다시 시작하시겠습니까? 현재 업로드된 파일과 계산 결과는 모두 사라집니다.</p>
    <div class="modal-actions">
      <button class="btn" id="reset-no" type="button">아니오</button>
      <button class="btn btn-primary" id="reset-yes" type="button">예</button>
    </div>
  `);
  overlay.querySelector("#reset-no").addEventListener("click", () => overlay.remove());
  overlay.querySelector("#reset-yes").addEventListener("click", () => { overlay.remove(); onConfirm(); });
}

export async function openSettingsModal() {
  let config;
  try {
    config = await api.getSettings();
  } catch (e) {
    showError(e.message);
    return;
  }
  const overlay = openModal(`
    <h2 class="modal-title">설정</h2>
    <div class="tabs">
      <div class="tab active" data-tab="survey">조사종류 관리</div>
      <div class="tab" data-tab="rate">공통 입력값</div>
      <div class="tab" data-tab="holiday">공휴일 관리</div>
    </div>
    <div id="settings-tab-body"></div>
    <div class="modal-actions">
      <button class="btn btn-primary" id="settings-close" type="button">닫기</button>
    </div>
  `);
  overlay.querySelector("#settings-close").addEventListener("click", () => overlay.remove());

  const tabs = overlay.querySelectorAll(".tab");
  const body = overlay.querySelector("#settings-tab-body");

  function renderSurveyTab() {
    body.innerHTML = `
      <table class="table"><thead><tr><th>조사이름</th><th>시작일</th><th>종료일</th><th></th></tr></thead>
      <tbody>${config.surveys.map(s => `<tr><td>${escapeHtml(s.name)}</td><td>${s.start}</td><td>${s.end}</td><td><button class="btn btn-danger" data-del-survey="${escapeHtml(s.name)}" type="button">삭제</button></td></tr>`).join("")}</tbody></table>
      <div class="form-row" style="margin-top:var(--space-4);">
        <input class="input" id="survey-name" placeholder="조사이름">
        <input class="input input-narrow" id="survey-start" placeholder="YYYY-MM-DD">
        <input class="input input-narrow" id="survey-end" placeholder="YYYY-MM-DD">
        <button class="btn btn-primary" id="survey-add" type="button">추가/수정</button>
      </div>
    `;
    body.querySelectorAll("[data-del-survey]").forEach(btn => btn.addEventListener("click", async () => {
      try { config = await api.deleteSurvey(btn.dataset.delSurvey); renderSurveyTab(); } catch (e) { showError(e.message); }
    }));
    body.querySelector("#survey-add").addEventListener("click", async () => {
      const name = body.querySelector("#survey-name").value.trim();
      const start = body.querySelector("#survey-start").value.trim();
      const end = body.querySelector("#survey-end").value.trim();
      if (!name || !start || !end) { showError("조사이름/시작일/종료일을 모두 입력하세요."); return; }
      try { config = await api.addSurvey(name, start, end); renderSurveyTab(); } catch (e) { showError(e.message); }
    });
  }

  function renderRateTab() {
    const years = Object.keys(config.rates).sort();
    body.innerHTML = `
      <table class="table"><thead><tr><th>연도</th><th>일급(원)</th><th>월 식대(원)</th><th></th></tr></thead>
      <tbody>${years.map(y => `<tr><td>${y}</td><td>${config.rates[y].daily_wage.toLocaleString()}</td><td>${config.rates[y].meal_allowance.toLocaleString()}</td><td><button class="btn btn-danger" data-del-rate="${y}" type="button">삭제</button></td></tr>`).join("")}</tbody></table>
      <div class="form-row" style="margin-top:var(--space-4);">
        <input class="input input-narrow" id="rate-year" placeholder="연도">
        <input class="input" id="rate-daily" placeholder="일급(원)">
        <input class="input" id="rate-meal" placeholder="월 식대(원)">
        <button class="btn btn-primary" id="rate-add" type="button">추가/수정</button>
      </div>
    `;
    body.querySelectorAll("[data-del-rate]").forEach(btn => btn.addEventListener("click", async () => {
      try { config = await api.deleteRate(Number(btn.dataset.delRate)); renderRateTab(); } catch (e) { showError(e.message); }
    }));
    body.querySelector("#rate-add").addEventListener("click", async () => {
      const year = Number(body.querySelector("#rate-year").value.trim());
      const daily = Number(body.querySelector("#rate-daily").value.trim().replace(/,/g, ""));
      const meal = Number(body.querySelector("#rate-meal").value.trim().replace(/,/g, ""));
      if (!year || Number.isNaN(daily) || Number.isNaN(meal)) { showError("연도/일급/식대는 모두 숫자로 입력하세요."); return; }
      try { config = await api.addRate(year, daily, meal); renderRateTab(); } catch (e) { showError(e.message); }
    });
  }

  function renderHolidayTab() {
    body.innerHTML = `
      <ul style="list-style:none; padding:0; margin:0; max-height:220px; overflow-y:auto;">
        ${config.holidays.map(h => `<li style="display:flex; justify-content:space-between; padding:var(--space-1) 0;">${h}<button class="btn btn-danger" data-del-holiday="${h}" type="button" style="padding:2px 8px;">삭제</button></li>`).join("")}
      </ul>
      <div class="form-row" style="margin-top:var(--space-4);">
        <input class="input" id="holiday-date" placeholder="예: 2026-01-01">
        <button class="btn btn-primary" id="holiday-add" type="button">추가</button>
      </div>
    `;
    body.querySelectorAll("[data-del-holiday]").forEach(btn => btn.addEventListener("click", async () => {
      try { config = await api.deleteHoliday(btn.dataset.delHoliday); renderHolidayTab(); } catch (e) { showError(e.message); }
    }));
    body.querySelector("#holiday-add").addEventListener("click", async () => {
      const date = body.querySelector("#holiday-date").value.trim();
      if (!date) return;
      try { config = await api.addHoliday(date); renderHolidayTab(); } catch (e) { showError(e.message); }
    });
  }

  const tabRenderers = { survey: renderSurveyTab, rate: renderRateTab, holiday: renderHolidayTab };
  tabs.forEach(tab => tab.addEventListener("click", () => {
    tabs.forEach(t => t.classList.remove("active"));
    tab.classList.add("active");
    tabRenderers[tab.dataset.tab]();
  }));
  renderSurveyTab();
}
```

- [ ] **Step 2: `app.js`에 설정 버튼 연결**

`wage_calculator/webapp/static/js/app.js` 전체를 다음으로 교체:

```js
import { registerRoute, navigate } from "./router.js";
import { render as renderUpload } from "./upload.js";
import { render as renderSpecialLeave } from "./specialLeave.js";
import { openSettingsModal } from "./confirmModals.js";

registerRoute("upload", renderUpload);
registerRoute("specialLeave", renderSpecialLeave);

document.getElementById("settings-btn").addEventListener("click", () => openSettingsModal());

navigate("upload");
```

- [ ] **Step 3: Browser 도구로 검증**

1. 개발 서버 기동 상태 확인(Task 2 Step 7)
2. `http://127.0.0.1:8811/`에서 상단 "설정" 버튼 클릭 → 설정 모달이 뜨는지 확인(3개 탭: 조사종류 관리/공통 입력값/공휴일 관리)
3. 조사종류 관리 탭에서 이름/시작일/종료일 입력 후 "추가/수정" 클릭 → 표에 새 행이 즉시 추가되는지 확인, `read_network_requests`로 `POST /api/settings/survey`가 200인지 확인
4. 방금 추가한 행의 "삭제" 클릭 → 표에서 사라지는지, `DELETE /api/settings/survey/...`가 200인지 확인
5. 공휴일 관리 탭에서도 추가/삭제 한 번씩 확인
6. 모달 바깥(어두운 배경) 클릭 시 닫히는지 확인

- [ ] **Step 4: 커밋**

```bash
git add wage_calculator/webapp/static/js/confirmModals.js wage_calculator/webapp/static/js/app.js
git commit -m "feat: 공통 모달 4종(계약수정/확인창/설정) 추가"
```

---

### Task 5: 대상자 확인 화면

**Files:**
- Create: `wage_calculator/webapp/static/js/targets.js`
- Modify: `wage_calculator/webapp/static/js/app.js`

**Interfaces:**
- Consumes: `api.getTargets/batchAssign/proceed/calculate`(Task 2), `openContractEditModal/openUnassignedConfirmModal/openContractPeriodCheckModal/openConfirmRunModal`(Task 4)
- Produces: `render(container)` — `app.js`가 `"targets"`로 등록

- [ ] **Step 1: `targets.js` 작성**

`wage_calculator/webapp/static/js/targets.js`:

```js
import { api } from "./api.js";
import { navigate } from "./router.js";
import { showError, showWarning } from "./toast.js";
import { escapeHtml } from "./utils.js";
import { openContractEditModal, openUnassignedConfirmModal, openContractPeriodCheckModal, openConfirmRunModal } from "./confirmModals.js";

export async function render(container) {
  const { targets, survey_names } = await api.getTargets();
  const checked = new Set();
  const today = new Date();

  container.innerHTML = `
    <div class="card">
      <h1 class="screen-title">대상자 확인</h1>
      <div class="form-row">
        <label>급여산정 연도</label>
        <input class="input input-narrow" id="year" value="${today.getFullYear()}">
        <label style="width:auto; margin-left:var(--space-4);">급여산정 월</label>
        <input class="input input-narrow" id="month" value="${today.getMonth() + 1}">
      </div>
      <table class="table">
        <thead><tr><th>선택</th><th>성명</th><th>담당조사</th><th>계약시작</th><th>계약마지막</th></tr></thead>
        <tbody id="rows"></tbody>
      </table>
      <div class="actions-split">
        <div>
          <button class="btn" id="select-all" type="button">전체선택</button>
          <button class="btn" id="deselect-all" type="button">전체해제</button>
        </div>
      </div>
      <div class="form-row" style="margin-top:var(--space-4);">
        <label>담당조사 일괄 지정</label>
        <select class="input" id="survey-select">
          <option value="">선택</option>
          ${survey_names.map(n => `<option value="${escapeHtml(n)}">${escapeHtml(n)}</option>`).join("")}
        </select>
        <button class="btn" id="batch-assign" type="button">선택 인원에 일괄 매칭</button>
        <span class="text-muted">(행 더블클릭: 계약기간 개별 수정)</span>
      </div>
      <div class="actions">
        <button class="btn btn-primary" id="calc-btn" type="button">계산 실행</button>
      </div>
    </div>
  `;

  const tbody = container.querySelector("#rows");

  function renderRows() {
    tbody.innerHTML = targets.map(t => `
      <tr data-key="${escapeHtml(t.key)}">
        <td><input type="checkbox" data-check="${escapeHtml(t.key)}" ${checked.has(t.key) ? "checked" : ""}></td>
        <td>${escapeHtml(t.label)}</td>
        <td>${escapeHtml(t.survey_name)}</td>
        <td>${t.contract_start}</td>
        <td>${t.contract_end}</td>
      </tr>
    `).join("");
  }
  renderRows();

  tbody.addEventListener("click", (evt) => {
    const check = evt.target.closest("[data-check]");
    if (check) {
      const key = check.dataset.check;
      if (checked.has(key)) checked.delete(key); else checked.add(key);
    }
  });

  tbody.addEventListener("dblclick", (evt) => {
    const row = evt.target.closest("tr[data-key]");
    if (!row) return;
    const person = targets.find(t => t.key === row.dataset.key);
    openContractEditModal(person, async () => {
      const refreshed = await api.getTargets();
      targets.length = 0;
      targets.push(...refreshed.targets);
      renderRows();
    });
  });

  container.querySelector("#select-all").addEventListener("click", () => {
    targets.forEach(t => checked.add(t.key));
    renderRows();
  });
  container.querySelector("#deselect-all").addEventListener("click", () => {
    checked.clear();
    renderRows();
  });

  container.querySelector("#batch-assign").addEventListener("click", async () => {
    const surveyName = container.querySelector("#survey-select").value;
    if (!surveyName) { showWarning("담당조사를 선택하세요."); return; }
    if (checked.size === 0) { showWarning("일괄 매칭할 인원을 체크하세요."); return; }
    try {
      const result = await api.batchAssign(Array.from(checked), surveyName);
      targets.length = 0;
      targets.push(...result.targets);
      checked.clear();
      renderRows();
    } catch (e) {
      showError(e.message);
    }
  });

  container.querySelector("#calc-btn").addEventListener("click", async () => {
    const year = parseInt(container.querySelector("#year").value, 10);
    const month = parseInt(container.querySelector("#month").value, 10);
    if (!Number.isInteger(year) || !Number.isInteger(month) || month < 1 || month > 12) {
      showWarning("급여산정 연/월을 올바르게 입력하세요.");
      return;
    }
    try {
      const { unassigned_names } = await api.proceed(year, month);
      const proceedToConfirm = () => {
        openContractPeriodCheckModal(() => {
          openConfirmRunModal(async () => {
            try {
              const { errors } = await api.calculate();
              if (errors.length > 0) showWarning(errors.join("\n"));
              navigate("result");
            } catch (e) {
              showError(e.message);
            }
          });
        });
      };
      if (unassigned_names.length > 0) {
        openUnassignedConfirmModal(unassigned_names, proceedToConfirm);
      } else {
        proceedToConfirm();
      }
    } catch (e) {
      showError(e.message);
    }
  });
}
```

- [ ] **Step 2: `app.js`에 등록**

`wage_calculator/webapp/static/js/app.js` 전체를 다음으로 교체:

```js
import { registerRoute, navigate } from "./router.js";
import { render as renderUpload } from "./upload.js";
import { render as renderSpecialLeave } from "./specialLeave.js";
import { render as renderTargets } from "./targets.js";
import { openSettingsModal } from "./confirmModals.js";

registerRoute("upload", renderUpload);
registerRoute("specialLeave", renderSpecialLeave);
registerRoute("targets", renderTargets);

document.getElementById("settings-btn").addEventListener("click", () => openSettingsModal());

navigate("upload");
```

- [ ] **Step 3: Browser 도구로 검증**

demo_assets 픽스처는 5명 모두 담당조사가 비어 있고, `설정` 모달에서 조사종류가 하나도 없다면 먼저 하나 등록해야 "일괄 매칭"을 끝까지 확인할 수 있다.

1. 개발 서버 기동, 업로드 → 특별휴가 확정까지 진행해 대상자 화면 진입
2. "설정" → 조사종류 관리에서 예: 이름 `테스트조사`, 시작일 `2026-08-01`, 종료일 `2026-08-31` 추가 후 모달 닫기
3. 대상자 화면에서 "전체선택" 클릭 → 5개 체크박스 모두 체크되는지 확인
4. 담당조사 드롭다운에서 방금 만든 조사 선택 → "선택 인원에 일괄 매칭" 클릭 → 표의 담당조사/계약시작/계약마지막 컬럼이 채워지는지 확인
5. 아무 행이나 더블클릭 → 계약기간 수정 모달이 뜨는지, 저장 시 표가 갱신되는지 확인
6. "계산 실행" 클릭 → 계약기간 확인 모달 → "네(진행)" → 계산 실행 확인 모달(공휴일/요율 텍스트 확인) → "계속" → `read_network_requests`로 `POST /api/calculate`가 200인지 확인(다음 화면은 Task 6에서 만들어지므로 아직 안 뜨는 게 정상)

- [ ] **Step 4: 커밋**

```bash
git add wage_calculator/webapp/static/js/targets.js wage_calculator/webapp/static/js/app.js
git commit -m "feat: 대상자 확인 화면 추가"
```

---

### Task 6: 결과 화면

**Files:**
- Create: `wage_calculator/webapp/static/js/result.js`
- Modify: `wage_calculator/webapp/static/js/app.js`

**Interfaces:**
- Consumes: `api.getResults/download/reset`(Task 2), `openResetConfirmModal`(Task 4)
- Produces: `render(container)` — `app.js`가 `"result"`로 등록

- [ ] **Step 1: `result.js` 작성**

`wage_calculator/webapp/static/js/result.js`:

```js
import { api } from "./api.js";
import { navigate } from "./router.js";
import { showError, showSuccess } from "./toast.js";
import { escapeHtml } from "./utils.js";
import { openResetConfirmModal } from "./confirmModals.js";

export async function render(container) {
  const { results } = await api.getResults();

  container.innerHTML = `
    <div class="card">
      <h1 class="screen-title">계산 결과</h1>
      <table class="table">
        <thead><tr><th>성명</th><th>조사</th><th>급여계산기간</th><th>계(일)</th><th>주휴(일)</th><th>잔여연가(일)</th><th>지급총액</th></tr></thead>
        <tbody id="rows"></tbody>
      </table>
      <div class="actions-split">
        <div>
          <button class="btn" id="download-btn" type="button">엑셀 다운로드</button>
          <button class="btn" id="evidence-btn" type="button">산정근거 확인</button>
        </div>
        <div>
          <button class="btn" id="back-btn" type="button">뒤로가기</button>
          <button class="btn btn-danger" id="reset-btn" type="button">새로 계산(처음부터)</button>
        </div>
      </div>
    </div>
  `;

  const tbody = container.querySelector("#rows");
  tbody.innerHTML = results.map(r => `
    <tr data-key="${escapeHtml(r.key)}" style="cursor:pointer;">
      <td>${escapeHtml(r.label)}</td>
      <td>${escapeHtml(r.survey)}</td>
      <td>${r.period}</td>
      <td>${r.total_days}</td>
      <td>${r.weekly_holiday_days}</td>
      <td>${r.remaining_leave_days}</td>
      <td>${r.total_payment.toLocaleString()}</td>
    </tr>
  `).join("");

  tbody.addEventListener("dblclick", (evt) => {
    const row = evt.target.closest("tr[data-key]");
    if (!row) return;
    navigate("evidence", { key: row.dataset.key });
  });

  container.querySelector("#download-btn").addEventListener("click", async () => {
    try {
      const { saved_paths } = await api.download();
      showSuccess("저장되었습니다:\n" + saved_paths.join("\n"));
    } catch (e) {
      showError(e.message);
    }
  });

  container.querySelector("#evidence-btn").addEventListener("click", () => navigate("evidence"));
  container.querySelector("#back-btn").addEventListener("click", () => navigate("targets"));
  container.querySelector("#reset-btn").addEventListener("click", () => {
    openResetConfirmModal(async () => {
      await api.reset();
      navigate("upload");
    });
  });
}
```

- [ ] **Step 2: `app.js`에 등록**

`wage_calculator/webapp/static/js/app.js` 전체를 다음으로 교체:

```js
import { registerRoute, navigate } from "./router.js";
import { render as renderUpload } from "./upload.js";
import { render as renderSpecialLeave } from "./specialLeave.js";
import { render as renderTargets } from "./targets.js";
import { render as renderResult } from "./result.js";
import { openSettingsModal } from "./confirmModals.js";

registerRoute("upload", renderUpload);
registerRoute("specialLeave", renderSpecialLeave);
registerRoute("targets", renderTargets);
registerRoute("result", renderResult);

document.getElementById("settings-btn").addEventListener("click", () => openSettingsModal());

navigate("upload");
```

- [ ] **Step 3: Browser 도구로 검증**

1. Task 5 Step 3의 흐름을 끝까지(계산 실행까지) 진행하면 이제 결과 화면으로 전환되는지 확인 — 표에 5명 행이 보여야 함
2. "엑셀 다운로드" 클릭 → 초록 성공 토스트에 저장 경로가 표시되는지 확인, `read_network_requests`로 `POST /api/download`가 200인지 확인. 실제로 다운로드 폴더에 파일이 생겼는지도 확인(`ls`)하고, 테스트로 생성된 파일이면 정리한다.
3. "새로 계산(처음부터)" 클릭 → 확인 모달 → "예" → 업로드 화면으로 돌아가는지, `POST /api/reset`이 200인지 확인
4. "산정근거 확인"/행 더블클릭은 Task 7에서 evidence 화면이 생긴 뒤에 마저 확인(지금은 콘솔에 `알 수 없는 화면: evidence`가 찍히는 게 정상)

- [ ] **Step 4: 커밋**

```bash
git add wage_calculator/webapp/static/js/result.js wage_calculator/webapp/static/js/app.js
git commit -m "feat: 결과 화면 추가"
```

---

### Task 7: 산정근거 화면

**Files:**
- Create: `wage_calculator/webapp/static/js/evidence.js`
- Modify: `wage_calculator/webapp/static/js/app.js`

**Interfaces:**
- Consumes: `api.getResults/getEvidence`(Task 2)
- Produces: `render(container, params)` — `app.js`가 `"evidence"`로 등록. `params.key`가 없으면 첫 번째 결과를 기본 선택한다.

- [ ] **Step 1: `evidence.js` 작성**

`wage_calculator/webapp/static/js/evidence.js`:

```js
import { api } from "./api.js";
import { navigate } from "./router.js";
import { showError } from "./toast.js";
import { escapeHtml } from "./utils.js";

export async function render(container, params) {
  let currentKey = params && params.key;
  if (!currentKey) {
    const { results } = await api.getResults();
    if (results.length === 0) {
      showError("계산 결과가 없습니다.");
      navigate("result");
      return;
    }
    currentKey = results[0].key;
  }

  container.innerHTML = `
    <div class="card">
      <div class="form-row">
        <label>성명 선택</label>
        <select class="input" id="name-select" style="flex: 0 0 220px;"></select>
        <button class="btn" id="back-btn" type="button" style="margin-left:auto;">← 결과 화면</button>
      </div>
      <div class="evidence-layout">
        <div class="evidence-col" style="flex:1;">
          <h3>근무현황 원본(B파일)</h3>
          <table class="table"><thead><tr><th>종별</th><th>사용기간(날짜)</th><th>사용시간(시분)</th><th>사유</th><th>비고</th></tr></thead><tbody id="raw-rows"></tbody></table>
        </div>
        <div class="evidence-col" style="flex:2;">
          <div class="tabs">
            <div class="tab active" data-tab="weekly">주휴 산정근거</div>
            <div class="tab" data-tab="lateout">조퇴외출 산정근거</div>
            <div class="tab" data-tab="meal">식대해당일 산정근거</div>
            <div class="tab" data-tab="leave">잔여연가 산정근거</div>
          </div>
          <div id="tab-body"></div>
        </div>
      </div>
    </div>
  `;

  container.querySelector("#back-btn").addEventListener("click", () => navigate("result"));

  const select = container.querySelector("#name-select");
  let data = null;
  let activeTab = "weekly";

  async function load(key) {
    data = await api.getEvidence(key);
    currentKey = key;
    select.innerHTML = data.names.map(n => `<option value="${escapeHtml(n.key)}" ${n.key === currentKey ? "selected" : ""}>${escapeHtml(n.label)}</option>`).join("");
    renderRaw();
    renderTab(activeTab);
  }

  function renderRaw() {
    container.querySelector("#raw-rows").innerHTML = data.raw_rows.map(r => `
      <tr><td>${escapeHtml(r.category)}</td><td>${escapeHtml(r.period)}</td><td>${escapeHtml(r.time)}</td><td>${escapeHtml(r.reason)}</td><td>${escapeHtml(r.note)}</td></tr>
    `).join("");
  }

  function renderTab(tab) {
    activeTab = tab;
    const body = container.querySelector("#tab-body");
    if (tab === "weekly") {
      body.innerHTML = `<table class="table"><thead><tr><th>창번호</th><th>시작일</th><th>종료일</th><th>근무일수</th><th>결근</th><th>공가</th><th>병가</th><th>판정</th><th>미발생사유</th></tr></thead><tbody>${
        data.weekly.map(w => `<tr><td>${w.index}</td><td>${w.start}</td><td>${w.effective_end}</td><td>${w.workdays}</td><td>${w.absence_days}</td><td>${w.public_leave_days}</td><td>${w.sick_full_days}</td><td>${w.granted ? "O" : "X"}</td><td>${escapeHtml(w.reason)}</td></tr>`).join("")
      }</tbody></table>`;
    } else if (tab === "lateout") {
      body.innerHTML = `<table class="table"><thead><tr><th>날짜</th><th>종별</th><th>시작</th><th>종료</th><th>점심포함</th><th>공제(분)</th></tr></thead><tbody>${
        data.late_out.map(e => `<tr><td>${e.date}</td><td>${escapeHtml(e.category)}</td><td>${e.start}</td><td>${e.end}</td><td>${e.lunch_included}</td><td>${e.minutes}</td></tr>`).join("")
      }<tr><td></td><td></td><td></td><td></td><td>합계(분)</td><td>${data.late_out_total_minutes}</td></tr></tbody></table>`;
    } else if (tab === "meal") {
      const m = data.meal;
      body.innerHTML = `<table class="table"><thead><tr><th>급여계산기간 시작</th><th>급여계산기간 종료</th><th>총일수</th><th>결근일수</th><th>식대해당일</th></tr></thead><tbody>
        <tr><td>${m.period_start}</td><td>${m.period_end}</td><td>${m.total_days}</td><td>${m.absence_days}</td><td>${m.meal_eligible_days}</td></tr>
      </tbody></table>`;
    } else if (tab === "leave") {
      body.innerHTML = `<table class="table"><thead><tr><th>구간번호</th><th>구간시작</th><th>구간종료</th><th>상태</th><th>발생</th><th>구간내 사용</th><th>누적잔여(분)</th></tr></thead><tbody>${
        data.leave.map(w => `<tr><td>${w.index}</td><td>${w.start}</td><td>${w.effective_end}</td><td>${w.status}</td><td>${w.accrued}</td><td>${escapeHtml(w.usage)}</td><td>${w.balance_minutes}</td></tr>`).join("")
      }<tr><td></td><td></td><td></td><td>최종</td><td></td><td>${data.leave_final.remaining_leave_days}일</td><td>${data.leave_final.remaining_leave_minutes}</td></tr></tbody></table>`;
    }
  }

  container.querySelectorAll(".tab").forEach(tab => tab.addEventListener("click", () => {
    container.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
    tab.classList.add("active");
    renderTab(tab.dataset.tab);
  }));

  select.addEventListener("change", () => load(select.value));

  await load(currentKey);
}
```

- [ ] **Step 2: `app.js`에 등록**

`wage_calculator/webapp/static/js/app.js` 전체를 다음으로 교체:

```js
import { registerRoute, navigate } from "./router.js";
import { render as renderUpload } from "./upload.js";
import { render as renderSpecialLeave } from "./specialLeave.js";
import { render as renderTargets } from "./targets.js";
import { render as renderResult } from "./result.js";
import { render as renderEvidence } from "./evidence.js";
import { openSettingsModal } from "./confirmModals.js";

registerRoute("upload", renderUpload);
registerRoute("specialLeave", renderSpecialLeave);
registerRoute("targets", renderTargets);
registerRoute("result", renderResult);
registerRoute("evidence", renderEvidence);

document.getElementById("settings-btn").addEventListener("click", () => openSettingsModal());

navigate("upload");
```

- [ ] **Step 3: Browser 도구로 전체 흐름 검증 (업로드→특별휴가→대상자→결과→산정근거)**

1. 개발 서버를 재기동(코드가 바뀌었으므로) — `uvicorn --reload`를 썼다면 자동 반영됨
2. 업로드부터 계산 실행까지 Task 2~6에서 확인한 흐름을 처음부터 끝까지 한 번에 실행
3. 결과 화면에서 아무 행이나 더블클릭 → 산정근거 화면으로 전환되는지, 좌측에 원본 B파일 표, 우측에 4개 탭이 보이는지 확인
4. 탭을 하나씩 클릭해 주휴/조퇴외출/식대/잔여연가 표가 각각 올바르게 그려지는지 확인(빈 표라도 헤더는 보여야 함 — demo 데이터는 조퇴외출 이벤트가 있는 사람도 있으므로 최소 1명은 조퇴외출 탭에 행이 있어야 함)
5. 성명 선택 드롭다운을 바꿔 다른 사람으로 전환되는지, `read_network_requests`로 매번 `GET /api/evidence?key=...`가 200인지 확인
6. "← 결과 화면" 클릭 → 결과 화면으로 돌아가는지 확인

- [ ] **Step 4: 커밋**

```bash
git add wage_calculator/webapp/static/js/evidence.js wage_calculator/webapp/static/js/app.js
git commit -m "feat: 산정근거 화면 추가"
```

---

### Task 8: main.py pywebview 부트스트랩

**Files:**
- Modify: `wage_calculator/main.py`
- Test: `wage_calculator/tests/test_main_bootstrap.py`

**Interfaces:**
- Consumes: `webapp.server.create_app`, `webapp.state.AppState`(Plan A)
- Produces: `find_free_port() -> int`, `bootstrap_server(state: AppState) -> int`(서버를 백그라운드 스레드로 띄우고 응답 확인 후 포트를 반환), `main()`(실제 pywebview 창을 연다)

- [ ] **Step 1: 의존성 설치**

Run: `pip install uvicorn pywebview`
Expected: 설치 성공(이미 설치돼 있으면 `Requirement already satisfied`)

- [ ] **Step 2: `main.py` 재작성**

`wage_calculator/main.py` 전체를 다음으로 교체:

```python
"""pywebview 부트스트랩. webapp/server.py의 FastAPI 앱을 로컬 서버로 띄우고
네이티브 창에 표시한다. OS 파일 다이얼로그는 js_api가 HTTP 없이 직접 처리한다."""
import socket
import time
import urllib.request
from pathlib import Path
from threading import Thread

import uvicorn
import webview

from webapp.server import create_app
from webapp.state import AppState


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_until_ready(port: int, timeout: float = 10.0):
    deadline = time.monotonic() + timeout
    last_error = None
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=0.5)
            return
        except Exception as e:
            last_error = e
            time.sleep(0.1)
    raise RuntimeError(f"서버가 {timeout}초 안에 응답하지 않았습니다(port={port}): {last_error}")


def bootstrap_server(state: AppState) -> int:
    """FastAPI 앱을 백그라운드 스레드로 띄우고, 응답이 올 때까지 기다린 뒤 포트를 반환한다."""
    app = create_app(state)
    port = find_free_port()
    thread = Thread(
        target=uvicorn.run,
        args=(app,),
        kwargs={"host": "127.0.0.1", "port": port, "log_level": "warning"},
        daemon=True,
    )
    thread.start()
    _wait_until_ready(port)
    return port


class JSApi:
    def __init__(self, state: AppState):
        self.state = state

    def pick_file(self, kind: str):
        start_dir = self.state.config_obj.last_upload_dir or ""
        result = webview.windows[0].create_file_dialog(
            webview.OPEN_DIALOG, directory=start_dir, file_types=("Excel Files (*.xlsx)",)
        )
        if not result:
            return None
        path = result[0]
        self.state.config_obj.set_last_upload_dir(str(Path(path).parent))
        self.state.config_obj.save()
        return path


def main():
    state = AppState()
    port = bootstrap_server(state)
    webview.create_window(
        "통계조사관 임금계산",
        f"http://127.0.0.1:{port}/",
        js_api=JSApi(state),
        width=1100,
        height=780,
    )
    webview.start()


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: 실패하는 테스트 작성**

`wage_calculator/tests/test_main_bootstrap.py`:

```python
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import bootstrap_server, find_free_port
from webapp.state import AppState


def test_find_free_port_returns_distinct_bindable_ports():
    p1 = find_free_port()
    p2 = find_free_port()
    assert p1 != p2
    assert 1024 < p1 < 65536
    assert 1024 < p2 < 65536
    print("OK: test_find_free_port_returns_distinct_bindable_ports")


def test_bootstrap_server_serves_index_html():
    state = AppState()
    port = bootstrap_server(state)
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/") as resp:
        body = resp.read().decode("utf-8")
        status = resp.status
    assert status == 200
    assert "통계조사관 임금계산" in body
    print("OK: test_bootstrap_server_serves_index_html")


if __name__ == "__main__":
    test_find_free_port_returns_distinct_bindable_ports()
    test_bootstrap_server_serves_index_html()
    print("ALL OK")
```

Run: `python wage_calculator/tests/test_main_bootstrap.py` (Step 2 이전 상태에서 실행 시)
Expected: `ImportError` 또는 `ModuleNotFoundError`(옛 `main.py`가 `from gui.app import main`만 하던 상태라 `bootstrap_server`/`find_free_port`가 없음)

- [ ] **Step 4: 테스트 통과 확인**

Run: `python wage_calculator/tests/test_main_bootstrap.py`
Expected: `ALL OK`

- [ ] **Step 5: 전체 회귀 확인**

Run: `python -m pytest wage_calculator/tests/ -v`
Expected: 전부 `passed`(Plan A의 103개 + 이 계획의 신규 테스트 전부)

- [ ] **Step 6: 실제 pywebview 창으로 수동 확인**

Run(백그라운드): `cd wage_calculator && python main.py`

디스플레이가 연결된 환경이라면 실제 네이티브 창이 뜬다. 창에서 다음만 추가로 확인한다(나머지 화면 동작은 Task 2~7에서 Browser 도구로 이미 검증됨):
1. 창 제목이 "통계조사관 임금계산"인지
2. "찾아보기" 버튼을 누르면 실제 OS 파일 탐색기가 열리는지(브라우저 테스트로는 확인 못 했던 부분)
3. 파일을 하나 선택한 뒤 다시 "찾아보기"를 누르면 방금 선택했던 폴더에서 열리는지(`last_upload_dir` 반영 확인)

디스플레이가 없는 환경이면 이 단계는 건너뛰고, Step 4의 자동 테스트(같은 서버 부트스트랩 경로를 pywebview 없이 검증)로 대체한다.

- [ ] **Step 7: 커밋**

```bash
git add wage_calculator/main.py wage_calculator/tests/test_main_bootstrap.py
git commit -m "feat: main.py를 pywebview 부트스트랩으로 재작성"
```

---

## 완료 후 확인

- [ ] **전체 회귀**: `python -m pytest wage_calculator/tests/ -v` — Plan A의 103개 + 이 계획에서 추가된 테스트가 전부 통과해야 한다.
- [ ] **전체 흐름 최종 점검**: Browser 도구로 업로드→특별휴가→대상자→결과→산정근거를 처음부터 끝까지 한 번 더 실행해, 화면 전환마다 걸리는 API 호출이 전부 200(또는 의도된 4xx)인지 `read_network_requests`로 확인한다.
