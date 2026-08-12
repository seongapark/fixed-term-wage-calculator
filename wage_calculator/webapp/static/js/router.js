import { showError } from "./toast.js";

const routes = {};

export function registerRoute(name, renderFn) {
  routes[name] = renderFn;
}

export function navigate(name, params) {
  const container = document.getElementById("app");
  container.innerHTML = "";
  const renderFn = routes[name];
  if (!renderFn) {
    console.error(`알 수 없는 화면: ${name}`);
    return;
  }
  Promise.resolve(renderFn(container, params)).catch((e) => {
    console.error(e);
    showError(`화면을 불러오는 중 오류가 발생했습니다: ${e.message}`);
  });
}
