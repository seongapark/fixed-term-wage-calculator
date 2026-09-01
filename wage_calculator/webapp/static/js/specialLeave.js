import { api } from "./api.js";
import { navigate } from "./router.js";
import { showWarning, showError } from "./toast.js";
import { escapeHtml } from "./utils.js";

const PAID_LABEL = { null: "미정", true: "유급", false: "무급" };
const ACCRUAL_LABEL = { null: "미정", true: "발생", false: "미발생" };

// 미정 -> 참 -> 거짓 -> 참 ... 순으로 돈다.
function nextTri(value) {
  if (value === null || value === undefined) return true;
  return !value;
}

let guideCache = null;
async function ensureGuideLoaded() {
  if (!guideCache) guideCache = (await api.getLeaveGuide()).entries;
  return guideCache;
}

export async function render(container) {
  const { groups } = await api.getSpecialLeave();
  // 인식된 종별(사유·비고 때문에 올라온 건)은 규칙이 정한 값이 미리 채워져 온다.
  // 목록에 없는 종별은 기본값이 없어 사람이 직접 골라야 한다.
  const decisions = groups.map((g) => ({
    paid: g.default_paid === undefined ? null : g.default_paid,
    accrual: g.default_accrual === undefined ? null : g.default_accrual,
  }));

  container.innerHTML = `
    <div class="card">
      <div class="title-row">
        <h1 class="screen-title" style="margin:0;">근무상황 확인</h1>
        <span class="info-icon" id="guide-icon">ⓘ</span>
      </div>
      <div class="info-panel" id="guide-panel"></div>
      <p class="screen-subtitle">사람이 판단해야 하는 건입니다. 종별이 목록(연가·반일연가·공가·일반병가·결근·조퇴·외출·지각·기타)에 없거나, 사유·비고에 적힌 내용이 있어 한 번 더 확인이 필요한 건이 올라옵니다.
"종별(원본)" 칸에 근무상황 파일에 적힌 문자열을 그대로 보여주니 이를 보고 판단하세요.
유급이면 일급·식대를 모두 지급하고, 무급이면 둘 다 지급하지 않습니다(결근과 같은 처리). "주휴·연가 발생"을 "미발생"으로 두면 그 주 주휴수당과 그 달 연가가 발생하지 않습니다.
각 칸을 클릭하면 값이 바뀝니다. 두 칸을 모두 지정해야 다음으로 진행됩니다.</p>
      <table class="table">
        <thead><tr><th>성명</th><th>종별(원본)</th><th>기간</th><th>사유(원본)</th><th>비고(원본)</th><th>지급</th><th>주휴·연가 발생</th></tr></thead>
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
  let isHovering = false;
  const showPanel = () => { clearTimeout(hideTimer); panel.style.display = "block"; };
  const scheduleHide = () => { hideTimer = setTimeout(() => { panel.style.display = "none"; }, 150); };

  icon.addEventListener("mouseenter", async () => {
    isHovering = true;
    clearTimeout(hideTimer);
    const entries = await ensureGuideLoaded();
    if (!isHovering) return;
    panel.innerHTML = `<table class="table"><thead><tr><th>종별</th><th>세부</th><th>설명</th><th>공제여부</th><th>시간입력</th></tr></thead><tbody>${
      entries.map(e => `<tr><td>${escapeHtml(e.category)}</td><td>${escapeHtml(e.subtype)}${e.detail ? " · " + escapeHtml(e.detail) : ""}</td><td>${escapeHtml(e.description)}</td><td>${escapeHtml(e.deduction)}</td><td>${escapeHtml(e.time_entry)}${e.note ? "<br><span class=\"text-muted\">" + escapeHtml(e.note) + "</span>" : ""}</td></tr>`).join("")
    }</tbody></table>`;
    showPanel();
  });
  icon.addEventListener("mouseleave", () => { isHovering = false; scheduleHide(); });
  panel.addEventListener("mouseenter", () => { isHovering = true; showPanel(); });
  panel.addEventListener("mouseleave", () => { isHovering = false; scheduleHide(); });

  const tbody = container.querySelector("#rows");
  const nextBtn = container.querySelector("#next-btn");

  function renderRows() {
    tbody.innerHTML = groups.map((g, idx) => {
      const period = g.start === g.end ? g.start : `${g.start}~${g.end}`;
      const { paid, accrual } = decisions[idx];
      const paidCls = paid === true ? "paid" : paid === false ? "unpaid" : "";
      const accrualCls = accrual === true ? "paid" : accrual === false ? "unpaid" : "";
      return `<tr>
        <td>${escapeHtml(g.person_name)}</td>
        <td>${escapeHtml(g.raw_category || "")}</td>
        <td>${escapeHtml(period)}</td>
        <td>${escapeHtml(g.reason)}</td>
        <td>${escapeHtml(g.note)}</td>
        <td><span class="status-pill ${paidCls}" data-idx="${idx}" data-field="paid">${PAID_LABEL[paid]}</span></td>
        <td><span class="status-pill ${accrualCls}" data-idx="${idx}" data-field="accrual">${ACCRUAL_LABEL[accrual]}</span></td>
      </tr>`;
    }).join("");
    nextBtn.disabled = decisions.some(d => d.paid === null || d.accrual === null);
  }

  renderRows();

  tbody.addEventListener("click", (evt) => {
    const pill = evt.target.closest(".status-pill");
    if (!pill) return;
    const idx = Number(pill.dataset.idx);
    const field = pill.dataset.field;
    decisions[idx][field] = nextTri(decisions[idx][field]);
    renderRows();
  });

  nextBtn.addEventListener("click", async () => {
    if (decisions.some(d => d.paid === null || d.accrual === null)) {
      showWarning("모든 건에 지급 여부와 주휴·연가 발생 여부를 지정해야 진행할 수 있습니다.");
      return;
    }
    try {
      await api.confirmSpecialLeave(decisions);
      navigate("targets");
    } catch (e) {
      showError(e.message);
    }
  });
}
