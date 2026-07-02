const data = {
  latest: null,
  leaderboard: [],
  runs: [],
  events: [],
  styleAnalytics: {},
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


function paletteColors(row) {
  return Array.isArray(row?.palette) ? row.palette.filter((color) => /^#[0-9a-fA-F]{6}$/.test(color)) : [];
}

function paletteHtml(row, label = "Dominant palette") {
  const colors = paletteColors(row);
  if (!colors.length) return "";
  return `
    <div class="palette" aria-label="${escapeHtml(label)}">
      ${colors
        .map((color, index) => {
          const safeColor = escapeHtml(color);
          const chipLabel = `${label} color ${index + 1}: ${color}`;
          return `<span class="palette-chip" style="--chip-color: ${safeColor}" title="${escapeHtml(chipLabel)}"><span class="sr-only">${escapeHtml(chipLabel)}</span></span>`;
        })
        .join("")}
    </div>
  `;
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

function renderDailyWinner() {
  const bestOutput = data.latest?.best_output;
  const container = document.querySelector("#daily-winner");

  if (!container) return;

  if (!bestOutput) {
    container.innerHTML = `
      <div class="daily-winner-empty">
        <span class="winner-badge">Winner of today</span>
        <div>
          <p class="eyebrow">Daily showcase</p>
          <h2>No winning image yet</h2>
          <p class="muted">Run the workflow to crown today's highest-scoring output.</p>
        </div>
      </div>
    `;
    return;
  }

  const imagePath = bestOutput.latest_path || bestOutput.output_path;
  const linkPath = bestOutput.output_path || imagePath;
  const sourceName = bestOutput.source_name || bestOutput.source_path || "Unknown source";
  const styleName = bestOutput.style || "Unknown style";
  const runDate = bestOutput.run_date || data.latest?.run_date || "—";

  container.innerHTML = `
    <article class="winner-card">
      <a class="winner-image-link" href="${linkPath}" target="_blank" rel="noreferrer">
        <img src="${imagePath}" alt="Winning output for ${sourceName} in ${styleName} style" />
        <span class="winner-badge">Winner of today</span>
        <span class="winner-gradient" aria-hidden="true"></span>
      </a>
      <div class="winner-copy">
        <p class="eyebrow">Daily showcase</p>
        <h2>${styleName}</h2>
        <p class="winner-source">${sourceName}</p>
        ${paletteHtml(bestOutput, "Winning output palette")}
        <dl class="winner-stats">
          <div>
            <dt>Score</dt>
            <dd>${fmtScore(scoreValue(bestOutput))}</dd>
          </div>
          <div>
            <dt>Run date</dt>
            <dd>${runDate}</dd>
          </div>
        </dl>
      </div>
    </article>
  `;
}

function revealThumbHtml(output, isActive = false) {
  const imagePath = output?.latest_path || output?.output_path || output?.source_path || "";
  const sourceName = output?.source_name || output?.source_path || "Unknown source";
  const styleName = output?.style || "Unknown style";
  const activeClass = isActive ? " active" : "";

  return `
    <figure class="reveal-thumb${activeClass}">
      <img src="${imagePath}" alt="${sourceName} in ${styleName} style" />
      <figcaption>
        <strong>${styleName}</strong>
        <span>${fmtScore(scoreValue(output))}</span>
      </figcaption>
    </figure>
  `;
}

function renderRevealWinner(output, isFinal = false) {
  const container = document.querySelector("#daily-winner");
  if (!container || !output) return;

  const imagePath = output.latest_path || output.output_path;
  const linkPath = output.output_path || imagePath;
  const sourceName = output.source_name || output.source_path || "Unknown source";
  const styleName = output.style || "Unknown style";
  const runDate = output.run_date || data.latest?.run_date || "—";

  container.innerHTML = `
    <article class="winner-card reveal-card${isFinal ? " final" : ""}">
      <a class="winner-image-link" href="${linkPath}" target="_blank" rel="noreferrer">
        <img src="${imagePath}" alt="Winning output for ${sourceName} in ${styleName} style" />
        <span class="winner-badge">${isFinal ? "Winner of today" : "Revealing…"}</span>
        <span class="winner-gradient" aria-hidden="true"></span>
      </a>
      <div class="winner-copy">
        <p class="eyebrow">${isFinal ? "Daily showcase" : "Scoring contender"}</p>
        <h2>${styleName}</h2>
        <p class="winner-source">${sourceName}</p>
        ${paletteHtml(output, "Winning output palette")}
        <dl class="winner-stats">
          <div class="score-pulse">
            <dt>Score</dt>
            <dd>${fmtScore(scoreValue(output))}</dd>
          </div>
          <div>
            <dt>Run date</dt>
            <dd>${runDate}</dd>
          </div>
        </dl>
      </div>
    </article>
  `;
}

function setupWinnerReveal() {
  const reveal = document.querySelector("#winner-reveal");
  const button = document.querySelector("#reveal-winner-button");
  const carousel = document.querySelector("#reveal-carousel");
  const status = document.querySelector("#winner-reveal-status");
  const outputs = data.latest?.outputs || [];
  const bestOutput = data.latest?.best_output;

  if (!reveal || !button || !carousel || !status) return;

  if (!outputs.length || !bestOutput) {
    button.disabled = true;
    status.textContent = "No generated outputs are available to reveal yet.";
    carousel.innerHTML = "";
    return;
  }

  const contenders = [...outputs].sort((a, b) => Number(a.index || 0) - Number(b.index || 0));
  carousel.innerHTML = contenders.slice(0, 8).map((output) => revealThumbHtml(output)).join("");

  button.addEventListener("click", () => {
    button.disabled = true;
    reveal.classList.add("is-running");
    status.textContent = "Shuffling today's contenders…";

    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const sequence = prefersReducedMotion ? [bestOutput] : [...contenders, bestOutput];
    const interval = prefersReducedMotion ? 0 : 220;
    let step = 0;

    const tick = () => {
      const output = sequence[step] || bestOutput;
      const isFinal = step >= sequence.length - 1;
      renderRevealWinner(output, isFinal);
      carousel.innerHTML = contenders
        .slice(0, 8)
        .map((contender) => revealThumbHtml(contender, contender.output_path === output.output_path))
        .join("");

      if (isFinal) {
        reveal.classList.remove("is-running");
        reveal.classList.add("is-complete");
        status.textContent = `${output.style || "Winner"} wins with a ${fmtScore(scoreValue(output))} score.`;
        button.textContent = "Winner revealed";
        return;
      }

      step += 1;
      window.setTimeout(tick, interval);
    };

    tick();
  });
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
                  <div class="comparison" style="--comparison-position: 50%">
                    <img class="comparison-image comparison-image-base" src="${row.source_path || source}" alt="Original ${source}" />
                    <div class="comparison-overlay">
                      <img class="comparison-image" src="${row.latest_path}" alt="Graded ${row.style}" />
                    </div>
                    <div class="comparison-label comparison-label-original">Original</div>
                    <div class="comparison-label comparison-label-graded">Graded</div>
                    <div class="comparison-divider" aria-hidden="true"></div>
                    <input
                      class="comparison-slider"
                      type="range"
                      min="0"
                      max="100"
                      value="50"
                      aria-label="Compare original and graded image for ${row.style}"
                      oninput="this.parentElement.style.setProperty('--comparison-position', this.value + '%')"
                    />
                  </div>
                  <div class="output-body">
                    <div class="output-top">
                      <strong>${row.style}</strong>
                      <span class="score">${fmtScore(scoreValue(row))}</span>
                    </div>
                    <p class="muted">${row.best_for_source_today ? "Best for this source today" : row.style_description || ""}</p>
                    ${paletteHtml(row, `${row.style || "Output"} palette`)}
                    <a class="full-image-link" href="${row.output_path}" target="_blank" rel="noreferrer">Open full image</a>
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
          ${paletteHtml(row, `${row.style || "Leaderboard output"} palette`)}
        </div>
        <strong class="score">${fmtScore(scoreValue(row))}</strong>
      </a>
    `,
    )
    .join("");
}

function renderStyleAnalytics() {
  const container = document.querySelector("#style-analytics");
  const summary = data.styleAnalytics || {};
  const rows = (summary.styles || []).slice(0, 12);
  if (!rows.length) {
    container.innerHTML = `<div class="empty">No style analytics yet. Generate a run to build rankings.</div>`;
    return;
  }
  container.innerHTML = `
    <div class="analytics-summary muted">
      ${summary.output_count || 0} scored outputs across ${summary.run_count || 0} runs · latest run ${summary.latest_run_date || "—"}
    </div>
    <div class="style-rankings">
      ${rows
        .map(
          (row) => `
          <article class="style-row">
            <div class="rank">#${row.rank}</div>
            <div>
              <strong>${row.style}</strong>
              <p class="row-subtitle">${row.count} outputs · ${row.daily_wins} daily wins · ${row.source_wins} source wins</p>
            </div>
            <div class="trend-metrics">
              <span><small>Avg</small>${fmtScore(row.average_score)}</span>
              <span><small>Best</small>${fmtScore(row.best_score)}</span>
              <span><small>7-day</small>${fmtScore(row.recent_7_day_average)}</span>
            </div>
          </article>
        `,
        )
        .join("")}
    </div>
  `;
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
  data.styleAnalytics = await loadJson("data/style-analytics.json", {});

  renderMetrics();
  renderDailyWinner();
  setupWinnerReveal();
  renderToday();
  renderLeaderboardFilters();
  setupLeaderboardFilters();
  renderLeaderboard();
  renderStyleAnalytics();
  renderEvents();
  renderRuns();
}

init();
