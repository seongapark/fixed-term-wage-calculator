import { api } from "./api.js";
import { navigate } from "./router.js";
import { showError, showSuccess } from "./toast.js";
import { escapeHtml } from "./utils.js";
import { openResetConfirmModal } from "./confirmModals.js";

export async function render(container) {
  const { results, has_retroactive } = await api.getResults();

  // 소급(전월 임금내역) 첨부로 소급조정액이 잡힌 경우에만 소급조정액/최종지급액
  // 열을 추가로 보여준다(엑셀 최종지급액과 동일: 최종지급액 = 지급총액 + 소급조정액).
  const retroHead = has_retroactive
    ? `<th>소급조정액</th><th>최종지급액</th>`
    : "";

  container.innerHTML = `
    <div class="card">
      <h1 class="screen-title">계산 결과</h1>
      <table class="table">
        <thead><tr><th>성명</th><th>조사</th><th>급여계산기간</th><th>계(일)</th><th>주휴(일)</th><th>잔여연가(일)</th><th>지급총액</th>${retroHead}</tr></thead>
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
  tbody.innerHTML = results.map(r => {
    const retroCells = has_retroactive
      ? `<td>${r.retro_adjustment.toLocaleString()}</td><td>${r.final_payment.toLocaleString()}</td>`
      : "";
    return `
    <tr data-key="${escapeHtml(r.key)}" style="cursor:pointer;">
      <td>${escapeHtml(r.label)}</td>
      <td>${escapeHtml(r.survey)}</td>
      <td>${escapeHtml(r.period)}</td>
      <td>${r.total_days}</td>
      <td>${r.weekly_holiday_days}</td>
      <td>${r.remaining_leave_days}</td>
      <td>${r.total_payment.toLocaleString()}</td>
      ${retroCells}
    </tr>`;
  }).join("");

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
