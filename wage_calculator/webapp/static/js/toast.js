export function showError(message) { show(message, "toast-error"); }
export function showWarning(message) { show(message, "toast-warning"); }
export function showSuccess(message) { show(message, "toast-success"); }

function show(message, cls) {
  const container = document.getElementById("toast-container");
  const el = document.createElement("div");
  el.className = `toast ${cls}`;
  el.textContent = message;
  el.title = "클릭하면 닫힙니다";
  el.addEventListener("click", () => el.remove());
  container.appendChild(el);
  // 근무상황 기간 부족처럼 사용자가 읽고 조치해야 하는 안내는 길다.
  // 5초면 다 읽기 전에 사라지므로 길이에 따라 표시 시간을 늘린다(최대 30초).
  const ms = Math.min(30000, Math.max(5000, String(message).length * 80));
  setTimeout(() => el.remove(), ms);
}
