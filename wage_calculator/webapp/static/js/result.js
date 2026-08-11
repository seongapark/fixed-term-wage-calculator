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
      <td>${escapeHtml(r.period)}</td>
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
