async function request(method, path, body) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const resp = await fetch(path, opts);
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    throw new Error(data.detail || `요청 실패 (${resp.status})`);
  }
  return data;
}

export const api = {
  upload: (aPath, bPath, prevPath) => request("POST", "/api/upload", { a_path: aPath, b_path: bPath, prev_path: prevPath || null }),
  reset: () => request("POST", "/api/reset"),
  getSpecialLeave: () => request("GET", "/api/special-leave"),
  confirmSpecialLeave: (decisions) => request("POST", "/api/special-leave/confirm", { decisions }),
  getTargets: () => request("GET", "/api/targets"),
  batchAssign: (keys, surveyName) => request("POST", "/api/targets/batch-assign", { keys, survey_name: surveyName }),
  editContract: (key, start, end) => request("POST", "/api/targets/contract-edit", { key, start, end }),
  proceed: (year, month) => request("POST", "/api/targets/proceed", { year, month }),
  getConfirmInfo: () => request("GET", "/api/confirm-info"),
  calculate: () => request("POST", "/api/calculate"),
  getResults: () => request("GET", "/api/results"),
  download: () => request("POST", "/api/download"),
  getEvidence: (key) => request("GET", `/api/evidence?key=${encodeURIComponent(key)}`),
  getSettings: () => request("GET", "/api/settings"),
  addSurvey: (name, start, end) => request("POST", "/api/settings/survey", { name, start, end }),
  deleteSurvey: (name) => request("DELETE", `/api/settings/survey/${encodeURIComponent(name)}`),
  addRate: (year, dailyWage, mealAllowance) => request("POST", "/api/settings/rate", { year, daily_wage: dailyWage, meal_allowance: mealAllowance }),
  deleteRate: (year) => request("DELETE", `/api/settings/rate/${year}`),
  addHoliday: (date) => request("POST", "/api/settings/holiday", { date }),
  deleteHoliday: (date) => request("DELETE", `/api/settings/holiday/${encodeURIComponent(date)}`),
  getLeaveGuide: () => request("GET", "/api/reference/leave-guide"),
};
