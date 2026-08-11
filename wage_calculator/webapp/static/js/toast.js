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
