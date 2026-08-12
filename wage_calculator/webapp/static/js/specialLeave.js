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
      const status = statuses[idx];
      const cls = status === "유급특별휴가" ? "paid" : status === "무급특별휴가" ? "unpaid" : "";
      return `<tr>
        <td>${escapeHtml(g.person_name)}</td>
        <td>${escapeHtml(period)}</td>
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
