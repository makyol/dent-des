const state = { demand: 1, kits: 2, policy: "S0R1", summary: [], fairness: [] };
const policyInfo = {
  S0R0: { label: "FCFS", description: "Uniform appointment spacing with strict first-come-first-served dispatch." },
  S1R0: { label: "Spacing", description: "Duration-aware appointment spacing with strict first-come-first-served dispatch." },
  S0R1: { label: "Dispatch", description: "Uniform appointment spacing with bounded ready-kit dispatch." },
  S1R1: { label: "Both", description: "Duration-aware spacing with bounded ready-kit dispatch." },
};
const demandOptions = [{ value: 0.8, label: "22" }, { value: 1, label: "28" }, { value: 1.2, label: "34" }, { value: 1.5, label: "42" }];
const kitOptions = [1, 2, 4];
const metricLabels = { mean_wait: "mean_wait", p90_wait: "p90_wait", overtime: "overtime", attended: "attended" };

const $ = (id) => document.getElementById(id);
const number = (value, digits = 1) => Number(value).toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: digits });

function parseCsv(text) {
  const lines = text.trim().split(/\r?\n/);
  const headers = lines.shift().split(",");
  return lines.map((line) => {
    const cells = line.split(",");
    return Object.fromEntries(headers.map((h, i) => [h, cells[i]]));
  });
}

function buildControls() {
  $("demand-controls").innerHTML = demandOptions.map((item) => `<button class="segment ${item.value === state.demand ? "active" : ""}" data-demand="${item.value}">${item.label}</button>`).join("");
  $("kit-controls").innerHTML = kitOptions.map((item) => `<button class="segment ${item === state.kits ? "active" : ""}" data-kits="${item}">${item}</button>`).join("");
  $("policy-select").innerHTML = Object.entries(policyInfo).map(([key, value]) => `<option value="${key}" ${key === state.policy ? "selected" : ""}>${value.label}</option>`).join("");
  document.querySelectorAll("[data-demand]").forEach((button) => button.addEventListener("click", () => { state.demand = Number(button.dataset.demand); buildControls(); render(); }));
  document.querySelectorAll("[data-kits]").forEach((button) => button.addEventListener("click", () => { state.kits = Number(button.dataset.kits); buildControls(); render(); }));
  $("policy-select").addEventListener("change", (event) => { state.policy = event.target.value; render(); });
}

function rowsFor(demand, kits) {
  return state.summary.filter((row) => Number(row.demand) === demand && Number(row.kits) === kits);
}

function metricRow(policy, metric) {
  return state.summary.find((row) => Number(row.demand) === state.demand && Number(row.kits) === state.kits && row.policy === policy && row.metric === metric);
}

function renderChart(rows) {
  const values = Object.keys(policyInfo).map((policy) => ({ policy, row: rows.find((item) => item.policy === policy && item.metric === "mean_wait") }));
  const max = Math.max(...values.map((item) => Number(item.row?.mean || 0)), 1);
  $("policy-chart").innerHTML = values.map(({ policy, row }) => {
    const value = Number(row?.mean || 0);
    const height = `${Math.max(2, value / max * 100)}%`;
    return `<div class="bar-wrap"><div class="bar-value">${number(value)}</div><div class="bar ${policy === state.policy ? "selected" : ""}" style="height:${height}" title="${policyInfo[policy].label}: ${number(value)} minutes"></div><div class="bar-label">${policyInfo[policy].label}</div></div>`;
  }).join("");
  $("policy-chart").setAttribute("aria-label", `Mean waiting time by policy for ${Math.round(state.demand * 28)} requests per day and ${state.kits} kits per class`);
  $("policy-legend").innerHTML = values.map(({ policy }) => `<span class="legend-item"><i class="legend-dot ${policy === state.policy ? "selected" : ""}"></i>${policyInfo[policy].label}</span>`).join("");
}

function render() {
  const rows = rowsFor(state.demand, state.kits);
  const wait = metricRow(state.policy, "mean_wait");
  const p90 = metricRow(state.policy, "p90_wait");
  const overtime = metricRow(state.policy, "overtime");
  const attended = metricRow(state.policy, "attended");
  $("metric-wait").textContent = `${number(wait?.mean ?? 0)} min`;
  $("metric-p90").textContent = `${number(p90?.mean ?? 0)} min`;
  $("metric-overtime").textContent = `${number(overtime?.mean ?? 0)} min`;
  $("metric-attended").textContent = number(attended?.mean ?? 0);
  $("policy-title").textContent = policyInfo[state.policy].label;
  $("policy-description").textContent = policyInfo[state.policy].description;
  $("metric-ci").textContent = `${number(wait?.ci_low ?? 0)} to ${number(wait?.ci_high ?? 0)} min`;
  renderChart(rows);
  const fairnessCases = ["K2_B0", "K2_B1", "K2_B2", "K2_unlimited"];
  const fairnessLabels = ["0", "1", "2", "Unlimited"];
  const fairnessRows = fairnessCases.map((caseName, index) => {
    const waitRow = state.fairness.find((row) => Number(row.demand) === 1 && row.case === caseName && row.metric === "mean_wait");
    const worseRow = state.fairness.find((row) => Number(row.demand) === 1 && row.case === caseName && row.metric === "fraction_patients_worse_than_fifo");
    return [fairnessLabels[index], Number(waitRow?.mean || 0), Number(worseRow?.mean || 0) * 100];
  });
  $("fairness-grid").innerHTML = fairnessRows.map(([bound, waitValue, worse], index) => `<div class="fairness-item ${index === 2 ? "highlight" : ""}"><span>Bypass bound ${bound}</span><strong>${number(waitValue)} min</strong><span>${number(worse)}% worse than FCFS</span></div>`).join("");
}

async function init() {
  try {
    const [summaryText, pairedText, fairnessText] = await Promise.all([fetch("data/summary.csv").then((r) => r.text()), fetch("data/paired_effects.csv").then((r) => r.text()), fetch("data/diagnostic_summary.csv").then((r) => r.text())]);
    state.summary = parseCsv(summaryText);
    state.fairness = parseCsv(fairnessText);
    buildControls();
    render();
    $("load-status").textContent = "Verified results loaded";
    $("load-status").classList.add("ready");
  } catch (error) {
    console.error(error);
    $("load-status").textContent = "Results could not be loaded";
    $("load-status").classList.add("error");
  }
}
init();
