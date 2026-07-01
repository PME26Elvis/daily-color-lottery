const data = {
  latest: null,
  leaderboard: [],
  runs: [],
  events: [],
};

const leaderboardFilters = {
  style: "all",
  source: "all",
  runDate: "all",
};

async function loadJson(path, fallback) {
  try {
    const response = await fetch(path, { cache: "no-store" });
    if (!response.ok) return fallback;
    return await response.json();
  } catch {
    return fallback;
  }
}

function scoreValue(item) {
  return item?.score?.score ?? item?.score ?? null;
}

function sourceKey(item) {
  return item?.source_path || item?.source_name || "unknown";
}

function sourceLabel(item) {
  return item?.source_name || item?.source_path || "Unknown source";
}

function collectLeaderboardFilterOptions() {
  const styles = new Set();
  const sources = new Map();
  const runDates = new Set();

  const collectOutput = (output) => {
    if (!output) return;
    if (output.style) styles.add(output.style);
    const key = sourceKey(output);
    sources.set(key, sourceLabel(output));
    if (output.run_date) runDates.add(output.run_date);
  };

  for (const row of data.leaderboard || []) collectOutput(row);
  for (const run of data.runs || []) {
    if (run.run_date) runDates.add(run.run_date);
    for (const style of run.styles || []) styles.add(style);
    for (const output of run.outputs || []) collectOutput(output);
    collectOutput(run.best_output);
  }
  for (const output of data.latest?.outputs || []) collectOutput(output);
  collectOutput(data.latest?.best_output);

  return {
    styles: [...styles].sort((a, b) => a.localeCompare(b)),
    sources: [...sources.entries()].sort((a, b) => a[1].localeCompare(b[1])),
    runDates: [...runDates].sort((a, b) => b.localeCompare(a)),
  };
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function optionHtml(value, label) {
  return `<option value="${escapeHtml(value)}">${escapeHtml(label)}</option>`;
}

function populateSelect(selector, options, allLabel) {
  const select = document.querySelector(selector);
  if (!select) return;
  select.innerHTML = [optionHtml("all", allLabel), ...options].join("");
}

function renderLeaderboardFilters() {
  const { styles, sources, runDates } = collectLeaderboardFilterOptions();
  populateSelect("#filter-style", styles.map((style) => optionHtml(style, style)), "All styles");
  populateSelect("#filter-source", sources.map(([value, label]) => optionHtml(value, label)), "All sources");
  populateSelect("#filter-run-date", runDates.map((date) => optionHtml(date, date)), "All dates");
}

function setupLeaderboardFilters() {
  document.querySelector("#leaderboard-filters")?.addEventListener("submit", (event) => event.preventDefault());

  const controls = [
    ["#filter-style", "style"],
    ["#filter-source", "source"],
    ["#filter-run-date", "runDate"],
  ];

  for (const [selector, key] of controls) {
    const select = document.querySelector(selector);
    if (!select) continue;
    select.value = leaderboardFilters[key];
    select.addEventListener("change", (event) => {
      leaderboardFilters[key] = event.target.value;
      renderLeaderboard();
    });
  }
}

function bySource(outputs) {
  const groups = new Map();
  for (const output of outputs || []) {
    const key = output.source_path || output.source_name || "unknown";
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(output);
  }
  return [...groups.entries()];
}

function fmtScore(value) {
  if (value === null || value === undefined) return "—";
  return Number(value).toFixed(2);
}

function paramLines(params) {
  return Object.entries(params || {})
    .map(([key, value]) => `${key}: ${Number(value).toFixed(3)}`)
    .join("\n");
}

function renderMetrics() {
  const latest = data.latest || {};
  const metrics = [
    ["Run date", latest.run_date || "—"],
    ["Sources", latest.source_count ?? "—"],
    ["Outputs", latest.outputs_generated ?? "—"],
    ["Average score", fmtScore(latest.average_score)],
    ["Best score", fmtScore(scoreValue(latest.best_output))],
  ];

  document.querySelector("#metrics").innerHTML = metrics
    .map(([label, value]) => `
      <article class="metric">
        <span class="label">${label}</span>
        <span class="value">${value}</span>
      </article>
    `)
    .join("");
}

function renderToday() {
  const latest = data.latest || {};
  const outputs = latest.outputs || [];
  const container = document.querySelector("#today-results");
  document.querySelector("#run-status").textContent = latest.run_id ? "Latest run loaded" : "No run yet";
  document.querySelector("#run-meta").textContent = latest.run_id
    ? `${latest.run_id} · ${latest.random?.random_source || "random"}`
    : "Run the workflow to generate the first batch.";

  if (!outputs.length) {
    container.innerHTML = `<div class="empty">No generated outputs yet. Add images to <code>sources/</code> and run the workflow.</div>`;
    return;
  }

  container.innerHTML = bySource(outputs)
    .map(([source, rows]) => {
      const sourceThumb = source;
      rows.sort((a, b) => Number(a.index || 0) - Number(b.index || 0));
      return `
        <section class="source-block">
          <div class="source-head">
            <div class="source-title">
              <img src="${sourceThumb}" alt="${source}" onerror="this.style.display='none'" />
              <div>
                <h3>${source}</h3>
                <p class="muted">${rows.length} randomized style outputs · original size ${rows[0]?.width || "?"}×${rows[0]?.height || "?"}</p>
              </div>
            </div>
          </div>
          <div class="outputs">
            ${rows
              .map(
                (row) => `
                <article class="output-card ${row.best_for_source_today ? "best" : ""}">
                  <a href="${row.output_path}" target="_blank" rel="noreferrer"><img src="${row.latest_path}" alt="${row.style}" /></a>
                  <div class="output-body">
                    <div class="output-top">
                      <strong>${row.style}</strong>
                      <span class="score">${fmtScore(scoreValue(row))}</span>
                    </div>
                    <p class="muted">${row.best_for_source_today ? "Best for this source today" : row.style_description || ""}</p>
                    <pre class="params">${paramLines(row.params)}</pre>
                  </div>
                </article>
              `,
              )
              .join("")}
          </div>
        </section>
      `;
    })
    .join("");
}

function renderLeaderboard() {
  const container = document.querySelector("#leaderboard");
  const rows = (data.leaderboard || [])
    .filter((row) => leaderboardFilters.style === "all" || row.style === leaderboardFilters.style)
    .filter((row) => leaderboardFilters.source === "all" || sourceKey(row) === leaderboardFilters.source)
    .filter((row) => leaderboardFilters.runDate === "all" || row.run_date === leaderboardFilters.runDate)
    .slice(0, 20);
  if (!rows.length) {
    container.innerHTML = `<div class="empty">No leaderboard entries yet.</div>`;
    return;
  }
  container.innerHTML = rows
    .map(
      (row, index) => `
      <a class="leader-row" href="${row.output_path}" target="_blank" rel="noreferrer">
        <img src="${row.output_path}" alt="${row.style}" />
        <div>
          <div class="row-title">#${index + 1} · ${row.style}</div>
          <div class="row-subtitle">${row.source_name || row.source_path} · ${row.run_date}</div>
        </div>
        <strong class="score">${fmtScore(scoreValue(row))}</strong>
      </a>
    `,
    )
    .join("");
}

function renderEvents() {
  const container = document.querySelector("#source-events");
  const rows = (data.events || []).slice(-20).reverse();
  if (!rows.length) {
    container.innerHTML = `<div class="empty">No source changes recorded yet.</div>`;
    return;
  }
  container.innerHTML = rows
    .map(
      (event) => `
      <div class="event">
        <strong>${event.event}</strong>
        <p class="row-subtitle"><code>${event.path}</code></p>
        <p class="row-subtitle">${event.time || ""}</p>
      </div>
    `,
    )
    .join("");
}

function renderRuns() {
  const container = document.querySelector("#runs");
  const rows = (data.runs || []).slice(-30).reverse();
  if (!rows.length) {
    container.innerHTML = `<div class="empty">No runs recorded yet.</div>`;
    return;
  }
  container.innerHTML = rows
    .map(
      (run) => `
      <div class="run-row">
        <strong>${run.run_date || "—"}</strong>
        <p class="row-subtitle"><code>${run.run_id || "—"}</code> · ${run.outputs_generated || 0} outputs · avg ${fmtScore(run.average_score)} · errors ${(run.errors || []).length}</p>
      </div>
    `,
    )
    .join("");
}

async function init() {
  data.latest = await loadJson("data/latest-run.json", {});
  data.leaderboard = await loadJson("data/leaderboard.json", []);
  data.runs = await loadJson("data/runs.json", []);
  data.events = await loadJson("data/source-events.json", []);

  renderMetrics();
  renderToday();
  renderLeaderboardFilters();
  setupLeaderboardFilters();
  renderLeaderboard();
  renderEvents();
  renderRuns();
}

init();
