import { api } from "./api.js";
import { navigate } from "./router.js";
import { showError, showWarning } from "./toast.js";

export function render(container) {
  container.innerHTML = `
    <div class="card">
      <h1 class="screen-title">통계조사관 임금계산</h1>
      <p class="text-muted" style="margin: 0 0 var(--space-4);">※ G드라이브의 예시파일을 참고하셔서 A파일(성명, 주민번호, 은행, 계좌번호), B파일(e-사람 근무상황 추출)을 준비해주세요.</p>
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
      <div class="text-muted" style="margin: 0 0 var(--space-4) 176px;">
        <p style="margin: 0 0 var(--space-1);">※ 3번째 첨부파일(전월 임금내역)을 비워두면 소급계산을 하지 않습니다.</p>
        <p style="margin: 0 0 var(--space-1);">※ 3번째 첨부파일에는 본 프로그램으로 추출한 전월 임금결과 파일을 넣으시면 됩니다.</p>
        <p style="margin: 0;">※ 근무상황 파일(B)은 <strong>계약 전체 기간</strong>(계약 시작월~당월)을 추출해 첨부하세요. 연가 잔량이 계약 전체의 만근·사용 이력에 의존하므로, 일부 기간만 넣으면 연가·소급 계산이 부정확해질 수 있습니다.</p>
      </div>
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
