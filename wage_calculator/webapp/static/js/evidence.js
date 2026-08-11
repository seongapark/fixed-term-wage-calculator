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
        data.weekly.map(w => `<tr><td>${w.index}</td><td>${escapeHtml(w.start)}</td><td>${escapeHtml(w.effective_end)}</td><td>${w.workdays}</td><td>${w.absence_days}</td><td>${w.public_leave_days}</td><td>${w.sick_full_days}</td><td>${w.granted ? "O" : "X"}</td><td>${escapeHtml(w.reason)}</td></tr>`).join("")
      }</tbody></table>`;
    } else if (tab === "lateout") {
      body.innerHTML = `<table class="table"><thead><tr><th>날짜</th><th>종별</th><th>시작</th><th>종료</th><th>점심포함</th><th>공제(분)</th></tr></thead><tbody>${
        data.late_out.map(e => `<tr><td>${escapeHtml(e.date)}</td><td>${escapeHtml(e.category)}</td><td>${escapeHtml(e.start)}</td><td>${escapeHtml(e.end)}</td><td>${e.lunch_included}</td><td>${e.minutes}</td></tr>`).join("")
      }<tr><td></td><td></td><td></td><td></td><td>합계(분)</td><td>${data.late_out_total_minutes}</td></tr></tbody></table>`;
    } else if (tab === "meal") {
      const m = data.meal;
      body.innerHTML = `<table class="table"><thead><tr><th>급여계산기간 시작</th><th>급여계산기간 종료</th><th>총일수</th><th>결근일수</th><th>식대해당일</th></tr></thead><tbody>
        <tr><td>${escapeHtml(m.period_start)}</td><td>${escapeHtml(m.period_end)}</td><td>${m.total_days}</td><td>${m.absence_days}</td><td>${m.meal_eligible_days}</td></tr>
      </tbody></table>`;
    } else if (tab === "leave") {
      body.innerHTML = `<table class="table"><thead><tr><th>구간번호</th><th>구간시작</th><th>구간종료</th><th>상태</th><th>발생</th><th>구간내 사용</th><th>누적잔여(분)</th></tr></thead><tbody>${
        data.leave.map(w => `<tr><td>${w.index}</td><td>${escapeHtml(w.start)}</td><td>${escapeHtml(w.effective_end)}</td><td>${w.status}</td><td>${w.accrued}</td><td>${escapeHtml(w.usage)}</td><td>${w.balance_minutes}</td></tr>`).join("")
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
