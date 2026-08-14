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
        <button class="btn" id="back-to-upload-btn" type="button">← 파일 다시 첨부하기</button>
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
        <td>${escapeHtml(t.contract_start)}</td>
        <td>${escapeHtml(t.contract_end)}</td>
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

  container.querySelector("#back-to-upload-btn").addEventListener("click", () => {
    navigate("upload");
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
              const { errors, leave_warnings } = await api.calculate();
              const messages = [...errors, ...(leave_warnings || [])];
              if (messages.length > 0) showWarning(messages.join("\n"));
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
