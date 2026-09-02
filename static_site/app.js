const els = {
  main: document.getElementById("app-main"),
  loading: document.getElementById("loading-state"),
  seedRunBtn: document.getElementById("seed-run-btn"),
  statAtRisk: document.getElementById("stat-at-risk"),
  statRecovered: document.getElementById("stat-recovered"),
  statRate: document.getElementById("stat-rate"),
  statEscalated: document.getElementById("stat-escalated"),
  categoryChart: document.getElementById("category-chart"),
  statusChart: document.getElementById("status-chart"),
  tableBody: document.getElementById("case-table-body"),
  emptyState: document.getElementById("empty-state"),
  search: document.getElementById("search"),
  filterCategory: document.getElementById("filter-category"),
  filterStatus: document.getElementById("filter-status"),
  sortBy: document.getElementById("sort-by"),
  runForm: document.getElementById("run-form"),
  runBtn: document.getElementById("run-btn"),
  drawerOverlay: document.getElementById("drawer-overlay"),
  drawer: document.getElementById("drawer"),
  drawerContent: document.getElementById("drawer-content"),
  drawerClose: document.getElementById("drawer-close"),
};

const STATUS_COLORS = {
  recovered: "var(--good)",
  escalated: "var(--bad)",
  skipped: "var(--text-muted)",
};

let state = { summary: null, audit: [], cases: [] };

// Static-export mode: set window.RECLAIM_STATIC = true (see static_site/index.html)
// to read pre-baked summary.json/audit.json instead of hitting a live FastAPI
// backend, and hide the "run new batch" control (no server to run it on).
const STATIC_MODE = window.RECLAIM_STATIC === true;
const SUMMARY_URL = STATIC_MODE ? "summary.json" : "/api/summary";
const AUDIT_URL = STATIC_MODE ? "audit.json" : "/api/audit";

function inr(n) {
  return "₹" + Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

async function fetchJSON(url, options) {
  const res = await fetch(url, options);
  if (!res.ok) throw new Error(`${url} -> ${res.status}`);
  return res.json();
}

function groupCases(audit) {
  const byCase = new Map();
  for (const ev of audit) {
    if (!byCase.has(ev.case_id)) byCase.set(ev.case_id, []);
    byCase.get(ev.case_id).push(ev);
  }
  const cases = [];
  for (const [caseId, events] of byCase) {
    events.sort((a, b) => a.timestamp.localeCompare(b.timestamp));
    const last = events[events.length - 1];
    cases.push({
      id: caseId,
      category: last.category,
      amount: last.amount_inr,
      root_cause: last.root_cause,
      intervention: last.intervention,
      source: last.decision_source,
      status: last.status_after,
      events,
    });
  }
  return cases;
}

function renderStats(summary) {
  els.statAtRisk.textContent = inr(summary.total_at_risk_inr);
  els.statRecovered.textContent = inr(summary.total_recovered_inr);
  els.statRate.textContent = summary.recovery_rate_pct.toFixed(1) + "%";
  const escalated = summary.status_breakdown.escalated || 0;
  const skipped = summary.status_breakdown.skipped || 0;
  els.statEscalated.textContent = `${escalated} / ${skipped}`;
}

function renderCategoryChart(summary) {
  const entries = Object.entries(summary.category_breakdown);
  const maxAmount = Math.max(...entries.map(([, v]) => v.at_risk_inr), 1);
  els.categoryChart.innerHTML = entries
    .map(([cat, v]) => {
      const pct = (v.at_risk_inr / maxAmount) * 100;
      return `
        <div class="chart-row">
          <div class="chart-label">${cat.replace(/_/g, " ")}</div>
          <div class="bar-track"><div class="bar-fill" data-width="${pct}"></div></div>
          <div class="chart-value">${v.recovery_rate_pct.toFixed(0)}%</div>
        </div>`;
    })
    .join("");
  requestAnimationFrame(() => {
    els.categoryChart.querySelectorAll(".bar-fill").forEach((el) => {
      el.style.width = el.dataset.width + "%";
    });
  });
}

function renderStatusChart(summary) {
  const total = Object.values(summary.status_breakdown).reduce((a, b) => a + b, 0) || 1;
  const segs = Object.entries(summary.status_breakdown)
    .map(([status, count]) => {
      const pct = (count / total) * 100;
      const color = STATUS_COLORS[status] || "var(--accent)";
      return { status, count, pct, color };
    });

  const track = segs
    .map((s) => `<div class="status-seg" data-width="${s.pct}" style="background:${s.color}"></div>`)
    .join("");

  const legend = segs
    .map(
      (s) => `
      <div class="legend-row">
        <span><span class="legend-dot" style="background:${s.color}"></span>${s.status}</span>
        <span class="legend-count">${s.count}</span>
      </div>`
    )
    .join("");

  els.statusChart.innerHTML = `<div class="status-seg-track">${track}</div><div class="status-legend">${legend}</div>`;
  requestAnimationFrame(() => {
    els.statusChart.querySelectorAll(".status-seg").forEach((el) => {
      el.style.width = el.dataset.width + "%";
    });
  });
}

function statusBadge(status) {
  return `<span class="badge badge-${status}">${status.replace(/_/g, " ")}</span>`;
}

function sourceTag(source) {
  const isLLM = source === "groq" || source === "claude";
  return `<span class="source-tag ${isLLM ? "" : "fallback"}">${source.replace(/_/g, " ")}</span>`;
}

function populateFilters(cases) {
  const categories = [...new Set(cases.map((c) => c.category))].sort();
  const statuses = [...new Set(cases.map((c) => c.status))].sort();
  els.filterCategory.innerHTML =
    `<option value="">All categories</option>` +
    categories.map((c) => `<option value="${c}">${c.replace(/_/g, " ")}</option>`).join("");
  els.filterStatus.innerHTML =
    `<option value="">All statuses</option>` +
    statuses.map((s) => `<option value="${s}">${s.replace(/_/g, " ")}</option>`).join("");
}

function applyFiltersAndRender() {
  const q = els.search.value.trim().toLowerCase();
  const catFilter = els.filterCategory.value;
  const statusFilter = els.filterStatus.value;
  const sortMode = els.sortBy.value;

  let rows = state.cases.filter((c) => {
    if (catFilter && c.category !== catFilter) return false;
    if (statusFilter && c.status !== statusFilter) return false;
    if (q && !(c.id.toLowerCase().includes(q) || c.root_cause.toLowerCase().includes(q))) return false;
    return true;
  });

  if (sortMode === "amount_desc") rows.sort((a, b) => b.amount - a.amount);
  else if (sortMode === "amount_asc") rows.sort((a, b) => a.amount - b.amount);
  else rows.sort((a, b) => a.id.localeCompare(b.id));

  els.emptyState.hidden = rows.length > 0;
  els.tableBody.innerHTML = rows
    .map(
      (c) => `
      <tr data-case-id="${c.id}">
        <td>${c.id}</td>
        <td>${c.category.replace(/_/g, " ")}</td>
        <td>${inr(c.amount)}</td>
        <td>${c.root_cause.replace(/_/g, " ")}</td>
        <td>${c.intervention.replace(/_/g, " ")}</td>
        <td>${sourceTag(c.source)}</td>
        <td>${statusBadge(c.status)}</td>
      </tr>`
    )
    .join("");

  els.tableBody.querySelectorAll("tr").forEach((tr) => {
    tr.addEventListener("click", () => openDrawer(tr.dataset.caseId));
  });
}

function openDrawer(caseId) {
  const c = state.cases.find((x) => x.id === caseId);
  if (!c) return;

  const timeline = c.events
    .map((ev, i) => {
      const time = new Date(ev.timestamp).toLocaleString();
      const gate = !ev.gate_allowed
        ? `<div class="gate-box">Blocked by policy: ${ev.gate_reason}</div>`
        : "";
      const msg = ev.message_sent
        ? `<div class="message-box">"${ev.message_sent}"</div>`
        : "";
      return `
        <div class="timeline-item">
          <div class="timeline-time">${time} &middot; attempt ${ev.attempt_number}</div>
          <div class="timeline-title">${ev.intervention.replace(/_/g, " ")} ${sourceTag(ev.decision_source)}</div>
          <div class="timeline-body">
            <strong>Root cause:</strong> ${ev.root_cause.replace(/_/g, " ")} (${ev.diagnosis_confidence} confidence)<br/>
            <strong>Rationale:</strong> ${ev.rationale}<br/>
            <strong>Outcome:</strong> ${ev.outcome.replace(/_/g, " ")} &rarr; ${statusBadge(ev.status_after)}
          </div>
          ${gate}
          ${msg}
        </div>`;
    })
    .join("");

  els.drawerContent.innerHTML = `
    <h3>${c.id}</h3>
    <div class="drawer-sub">${c.category.replace(/_/g, " ")} &middot; ${inr(c.amount)} &middot; final status ${statusBadge(c.status)}</div>
    <div class="timeline">${timeline}</div>
  `;
  els.drawerOverlay.hidden = false;
}

function closeDrawer() {
  els.drawerOverlay.hidden = true;
}

els.drawerClose.addEventListener("click", closeDrawer);
els.drawerOverlay.addEventListener("click", (e) => {
  if (e.target === els.drawerOverlay) closeDrawer();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeDrawer();
});

[els.search, els.filterCategory, els.filterStatus, els.sortBy].forEach((el) =>
  el.addEventListener("input", applyFiltersAndRender)
);

async function loadResults() {
  const [summary, audit] = await Promise.all([
    fetchJSON(SUMMARY_URL),
    fetchJSON(AUDIT_URL),
  ]);
  state.summary = summary;
  state.audit = audit;
  state.cases = groupCases(audit);

  renderStats(summary);
  renderCategoryChart(summary);
  renderStatusChart(summary);
  populateFilters(state.cases);
  applyFiltersAndRender();

  els.loading.hidden = true;
  els.main.hidden = false;
}

async function boot() {
  if (STATIC_MODE) {
    els.runForm.hidden = true;
  }
  try {
    await loadResults();
  } catch (err) {
    els.loading.querySelector("p").textContent = STATIC_MODE
      ? "Couldn't load the pre-baked batch results (summary.json/audit.json missing)."
      : "No batch results yet — run one to get started.";
    if (!STATIC_MODE) {
      els.seedRunBtn.hidden = false;
      els.seedRunBtn.addEventListener("click", async () => {
        els.seedRunBtn.disabled = true;
        els.seedRunBtn.textContent = "Running…";
        await fetchJSON("/api/run", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ n: 80, seed: 42 }),
        });
        await loadResults();
      });
    }
  }
}

if (!STATIC_MODE) {
  els.runForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const n = parseInt(document.getElementById("run-n").value, 10);
    const seed = parseInt(document.getElementById("run-seed").value, 10);
    els.runBtn.disabled = true;
    els.runBtn.querySelector(".btn-label").textContent = "Running…";
    els.runBtn.querySelector(".btn-spinner").hidden = false;
    try {
      await fetchJSON("/api/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ n, seed }),
      });
      await loadResults();
    } finally {
      els.runBtn.disabled = false;
      els.runBtn.querySelector(".btn-label").textContent = "Run new batch";
      els.runBtn.querySelector(".btn-spinner").hidden = true;
    }
  });
}

boot();
