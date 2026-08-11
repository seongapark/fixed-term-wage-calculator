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
  renderFn(container, params);
}
