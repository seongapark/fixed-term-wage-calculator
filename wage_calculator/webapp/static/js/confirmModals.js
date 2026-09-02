import { api } from "./api.js";
import { showError } from "./toast.js";
import { escapeHtml } from "./utils.js";

function openModal(innerHtml, extraClass = "") {
  const root = document.getElementById("modal-root");
  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";
  overlay.innerHTML = `<div class="modal ${extraClass}">${innerHtml}</div>`;
  root.appendChild(overlay);
  overlay.addEventListener("click", (evt) => {
    if (evt.target === overlay) overlay.remove();
  });
  return overlay;
}

export function openContractEditModal(person, onSave) {
  const overlay = openModal(`
    <h2 class="modal-title">계약기간 수정 - ${escapeHtml(person.label)}</h2>
    <div class="form-row"><label>계약 시작일(YYYY-MM-DD)</label><input class="input" id="edit-start" value="${escapeHtml(person.contract_start)}"></div>
    <div class="form-row"><label>계약 마지막일(YYYY-MM-DD)</label><input class="input" id="edit-end" value="${escapeHtml(person.contract_end)}"></div>
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

export function openPrevStatusCheckModal(lastDateIso, onProceed, onReattach) {
  const last = new Date(lastDateIso + "T00:00:00");
  const next = new Date(last.getTime() + 24 * 60 * 60 * 1000);
  const fmt = (d) => `${d.getMonth() + 1}/${d.getDate()}`;

  const overlay = openModal(`
    <h2 class="modal-title">전월 근무상황 확인</h2>
    <p class="modal-body">전월 임금내역 파일에 담긴 마지막 근무상황은 <strong>${escapeHtml(fmt(last))}</strong>입니다.

<strong>${escapeHtml(fmt(next))} 이후</strong> 전월분 근무상황이 더 발생하지 않은 것이 맞습니까?

급여를 20일경 선지급한 뒤 생긴 결근·조퇴 등은 전월 파일에 들어 있지 않습니다. 그런 건이 있는데 근무상황(B)에도 없으면, 그 금액이 소급계산에 반영되지 않고 조용히 빠집니다.</p>
    <div class="modal-actions">
      <button class="btn" id="prev-status-reattach" type="button">아니오(다시 첨부)</button>
      <button class="btn btn-primary" id="prev-status-ok" type="button">네(계속)</button>
    </div>
  `);
  overlay.querySelector("#prev-status-reattach").addEventListener("click", () => { overlay.remove(); onReattach(); });
  overlay.querySelector("#prev-status-ok").addEventListener("click", () => { overlay.remove(); onProceed(); });
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
    ? `[이번 달(${info.year}년 ${info.month}월) 공휴일]\n${escapeHtml(info.holidays.join(", "))}`
    : `[이번 달(${info.year}년 ${info.month}월) 공휴일 없음]`;
  const overriddenText = info.overridden_names.length
    ? `[계약기간을 개별 수정한 인원]\n${escapeHtml(info.overridden_names.join(", "))}`
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
  `, "modal-wide");
  overlay.querySelector("#settings-close").addEventListener("click", () => overlay.remove());

  const tabs = overlay.querySelectorAll(".tab");
  const body = overlay.querySelector("#settings-tab-body");

  function renderSurveyTab() {
    body.innerHTML = `
      <table class="table"><thead><tr><th>조사이름</th><th>시작일</th><th>종료일</th><th></th></tr></thead>
      <tbody>${config.surveys.map(s => `<tr><td>${escapeHtml(s.name)}</td><td>${escapeHtml(s.start)}</td><td>${escapeHtml(s.end)}</td><td><button class="btn btn-danger" data-del-survey="${escapeHtml(s.name)}" type="button">삭제</button></td></tr>`).join("")}</tbody></table>
      <div class="form-row" style="margin-top:var(--space-4);">
        <input class="input" id="survey-name" placeholder="조사이름">
        <input class="input" id="survey-start" placeholder="YYYY-MM-DD">
        <input class="input" id="survey-end" placeholder="YYYY-MM-DD">
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
        ${config.holidays.map(h => `<li style="display:flex; justify-content:space-between; padding:var(--space-1) 0;">${escapeHtml(h)}<button class="btn btn-danger" data-del-holiday="${escapeHtml(h)}" type="button" style="padding:2px 8px;">삭제</button></li>`).join("")}
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
