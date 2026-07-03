const data = {
  latest: null,
  leaderboard: [],
  runs: [],
  events: [],
  styleAnalytics: {},
  sourceAnalytics: {},
  algorithmAnalytics: {},
  recipeAnalytics: {},
  recipes: [],
};

const recipeFilters = { tag: "all", algorithm: "all", style: "all", profile: "all", minScore: "", favorites: "all" };

const leaderboardFilters = {
  style: "all",
  source: "all",
  runDate: "all",
  algorithm: "all",
  profileBucket: "all",
  minScore: "",
  badge: "all",
  profileTag: "all",
  sort: "score",
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

function profileTagsForFilter(output) {
  return output?.source_profile_tags || output?.source_profile?.profile_tags || output?.source_profile?.tags || [];
}

function renderDataHealth() {
  const container = document.querySelector("#data-health");
  if (!container) return;
  const warnings = [];
  if (!data.latest || !Array.isArray(data.latest.outputs)) warnings.push("latest-run.json is missing or has no outputs array");
  if (!Array.isArray(data.leaderboard)) warnings.push("leaderboard.json is missing or not an array");
  if (!Array.isArray(data.runs)) warnings.push("runs.json is missing or not an array");
  if (!data.styleAnalytics?.styles) warnings.push("style-analytics.json is missing style rows");
  if (!data.sourceAnalytics?.sources) warnings.push("source-analytics.json is missing source rows");
  if (!data.algorithmAnalytics?.algorithms) warnings.push("algorithm-analytics.json is missing algorithm rows");
  container.innerHTML = warnings.length
    ? `<p class="eyebrow">Data health</p><h2>Dashboard fallback mode</h2><p class="muted">${warnings.map(escapeHtml).join("; ")}.</p>`
    : `<p class="eyebrow">Data health</p><h2>All dashboard data files loaded</h2><p class="muted">Static JSON contracts are present; optional recipe data is handled gracefully.</p>`;
}

function collectLeaderboardFilterOptions() {
  const styles = new Set();
  const sources = new Map();
  const runDates = new Set();
  const algorithms = new Set();
  const profileBuckets = new Set();
  const badges = new Set();
  const profileTags = new Set();

  const collectOutput = (output) => {
    if (!output) return;
    if (output.style) styles.add(output.style);
    const key = sourceKey(output);
    sources.set(key, sourceLabel(output));
    if (output.run_date) runDates.add(output.run_date);
    if (output.algorithm) algorithms.add(output.algorithm);
    if (output.source_profile_bucket || output.source_profile?.profile_bucket) profileBuckets.add(output.source_profile_bucket || output.source_profile.profile_bucket);
    for (const badge of output.badges || []) badges.add(badge);
    for (const tag of profileTagsForFilter(output)) profileTags.add(tag);
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
    algorithms: [...algorithms].sort((a, b) => a.localeCompare(b)),
    profileBuckets: [...profileBuckets].sort((a, b) => a.localeCompare(b)),
    badges: [...badges].sort((a, b) => a.localeCompare(b)),
    profileTags: [...profileTags].sort((a, b) => a.localeCompare(b)),
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
  const { styles, sources, runDates, algorithms, profileBuckets, badges, profileTags } = collectLeaderboardFilterOptions();
  populateSelect("#filter-style", styles.map((style) => optionHtml(style, style)), "All styles");
  populateSelect("#filter-source", sources.map(([value, label]) => optionHtml(value, label)), "All sources");
  populateSelect("#filter-run-date", runDates.map((date) => optionHtml(date, date)), "All dates");
  populateSelect("#filter-algorithm", algorithms.map((algorithm) => optionHtml(algorithm, algorithm)), "All algorithms");
  populateSelect("#filter-profile", profileBuckets.map((bucket) => optionHtml(bucket, bucket)), "All profiles");
  populateSelect("#filter-badge", badges.map((badge) => optionHtml(badge, badge)), "All badges");
  populateSelect("#filter-profile-tag", profileTags.map((tag) => optionHtml(tag, tag)), "All tags");
}

function setupLeaderboardFilters() {
  document.querySelector("#leaderboard-filters")?.addEventListener("submit", (event) => event.preventDefault());

  const controls = [
    ["#filter-style", "style"],
    ["#filter-source", "source"],
    ["#filter-run-date", "runDate"],
    ["#filter-algorithm", "algorithm"],
    ["#filter-profile", "profileBucket"],
    ["#filter-badge", "badge"],
    ["#filter-profile-tag", "profileTag"],
    ["#filter-sort", "sort"],
  ];

  const minScore = document.querySelector("#filter-min-score");
  if (minScore) {
    minScore.value = leaderboardFilters.minScore;
    minScore.addEventListener("input", (event) => { leaderboardFilters.minScore = event.target.value; renderLeaderboard(); });
  }
  document.querySelector("#filter-reset")?.addEventListener("click", () => {
    Object.assign(leaderboardFilters, { style: "all", source: "all", runDate: "all", algorithm: "all", profileBucket: "all", minScore: "", badge: "all", profileTag: "all", sort: "score" });
    renderLeaderboardFilters(); setupLeaderboardFilters(); renderLeaderboard();
  });

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

function scoreBreakdownHtml(row) {
  const components = [
    ["contrast", "Contrast"],
    ["exposure_balance", "Exposure"],
    ["saturation_balance", "Saturation"],
    ["detail", "Detail"],
    ["composition_safety_score", "Composition"],
    ["palette_harmony_score", "Harmony"],
    ["dynamic_range_score", "Dynamic range"],
    ["mood_distinctiveness_score", "Mood"],
    ["artifact_risk_score", "Artifact risk"],
  ];
  const bars = components
    .map(([key, label]) => {
      const rawValue = row?.score?.[key];
      if (rawValue === null || rawValue === undefined || Number.isNaN(Number(rawValue))) return "";
      const value = Math.max(0, Math.min(100, Number(rawValue)));
      return `
        <div class="score-component" title="${label}: ${fmtScore(value)}">
          <span class="score-component-label">${label}</span>
          <span class="score-component-track" aria-hidden="true">
            <span class="score-component-fill" style="width: ${value}%"></span>
          </span>
          <span class="score-component-value">${fmtScore(value)}</span>
        </div>
      `;
    })
    .filter(Boolean)
    .join("");

  if (!bars) return "";
  return `<div class="score-breakdown" aria-label="Score component breakdown">${bars}</div>`;
}

const SCORE_COMPONENTS = [
  ["exposure_score", "Exposure", "How close exposure is to a balanced target."],
  ["contrast_score", "Contrast", "Global tonal separation and punch."],
  ["saturation_score", "Saturation", "Color intensity without oversaturation."],
  ["clipping_score", "Clipping", "Penalty when shadows/highlights are crushed."],
  ["sharpness_score", "Sharpness", "Perceived detail retention."],
  ["palette_harmony_score", "Palette harmony", "How cohesive the dominant colors are."],
  ["dynamic_range_score", "Dynamic range", "Spread of useful luminance values."],
  ["mood_distinctiveness_score", "Mood distinctiveness", "How distinct the look is from neutral grading."],
  ["artifact_risk_score", "Artifact risk", "Lower risk of generated artifacts or harsh edits."],
];

const ALGORITHM_DESCRIPTIONS = {
  style_range: "Baseline style sampler using configured parameter ranges.",
  adaptive_auto_enhance: "Source-aware auto enhancement tuned from luminance, saturation, clipping, and contrast profile signals.",
  palette_cinematic: "Palette-aware cinematic grading that leans into source dominant colors.",
  diversity_explorer: "Exploratory candidate sampler that favors distinct looks across the run.",
  monochrome_editorial: "Editorial monochrome or low-color treatment for graphic contrast and mood.",
};

const studioState = {
  source: "",
  output: "",
  compare: "",
  mode: "slider",
  algorithms: [],
  components: ["exposure_score", "contrast_score", "saturation_score", "clipping_score", "sharpness_score"],
  compact: false,
};

function outputId(row) {
  return row?.output_path || row?.latest_path || `${sourceKey(row)}::${row?.style || "unknown"}::${row?.index || 0}`;
}

function latestOutputs() {
  return data.latest?.outputs || [];
}

function loadStudioPreferences() {
  try {
    const prefs = JSON.parse(localStorage.getItem("experimentStudioPrefs") || "{}");
    if (prefs.mode) studioState.mode = prefs.mode;
    if (Array.isArray(prefs.algorithms)) studioState.algorithms = prefs.algorithms;
    if (Array.isArray(prefs.components)) studioState.components = prefs.components;
    if (typeof prefs.compact === "boolean") studioState.compact = prefs.compact;
  } catch {}
}

function saveStudioPreferences() {
  localStorage.setItem("experimentStudioPrefs", JSON.stringify({
    mode: studioState.mode,
    algorithms: studioState.algorithms,
    components: studioState.components,
    compact: studioState.compact,
  }));
}

function parseStudioHash() {
  if (!location.hash.startsWith("#studio")) return;
  const query = location.hash.split("?")[1] || "";
  const params = new URLSearchParams(query);
  for (const key of ["source", "output", "compare", "mode"]) {
    if (params.has(key)) studioState[key] = params.get(key) || "";
  }
}

function writeStudioHash() {
  const params = new URLSearchParams();
  for (const key of ["source", "output", "compare", "mode"]) if (studioState[key]) params.set(key, studioState[key]);
  history.replaceState(null, "", `#studio?${params.toString()}`);
}

function selectedStudioRows() {
  const rows = latestOutputs();
  const sourceRows = rows.filter((row) => !studioState.source || sourceKey(row) === studioState.source);
  const selected = sourceRows.find((row) => outputId(row) === studioState.output) || sourceRows[0] || rows[0] || {};
  const compare = sourceRows.find((row) => outputId(row) === studioState.compare) || nearestCompetitor(selected, sourceRows) || sourceRows[1] || selected;
  return { rows, sourceRows, selected, compare };
}

function nearestCompetitor(selected, rows) {
  if (!selected) return null;
  const selectedScore = Number(scoreValue(selected) || 0);
  return (rows || [])
    .filter((row) => outputId(row) !== outputId(selected))
    .sort((a, b) => Math.abs(Number(scoreValue(a) || 0) - selectedScore) - Math.abs(Number(scoreValue(b) || 0) - selectedScore))[0] || null;
}

function profileTags(row) {
  return row?.source_profile_tags || row?.source_profile?.tags || [];
}

function scoreComponentValue(row, key) {
  const score = row?.score || {};
  const aliases = { exposure_score: "exposure_balance", contrast_score: "contrast", saturation_score: "saturation_balance", sharpness_score: "detail" };
  return score[key] ?? score[aliases[key]];
}

function componentChartHtml(row) {
  const selected = SCORE_COMPONENTS.filter(([key]) => studioState.components.includes(key));
  const bars = selected.map(([key, label, tip]) => {
    const value = Number(scoreComponentValue(row, key));
    if (!Number.isFinite(value)) return "";
    const width = Math.max(0, Math.min(100, value));
    return `<div class="studio-bar" title="${escapeHtml(tip)}"><span>${escapeHtml(label)}</span><svg viewBox="0 0 100 8" preserveAspectRatio="none"><rect width="100" height="8" rx="4"></rect><rect width="${width}" height="8" rx="4" class="fill"></rect></svg><b>${fmtScore(value)}</b></div>`;
  }).filter(Boolean).join("");
  return bars ? `<div class="studio-chart" aria-label="Selected score components">${bars}</div>` : `<p class="muted">No selected score components are available for this output.</p>`;
}

function replaySnippet(row) {
  return JSON.stringify({ params: row?.params || {}, style: row?.style, grain_seed_hex: row?.grain_seed_hex, source_path: row?.source_path, algorithm: row?.algorithm || "style_range" }, null, 2);
}

function renderStudioComparison(selected, compare, sourceRows) {
  const mode = studioState.mode;
  if (mode === "grid") {
    const gridRows = studioState.algorithms.length ? sourceRows.filter((row) => studioState.algorithms.includes(row.algorithm || "style_range")) : sourceRows;
    return `<div class="studio-grid-compare">${(gridRows.length ? gridRows : sourceRows).map((row) => `<figure><img src="${row.latest_path || row.output_path}" alt="${escapeHtml(row.style || "Output")}"><figcaption>${escapeHtml(row.algorithm || row.style || "Output")} · ${fmtScore(scoreValue(row))}</figcaption></figure>`).join("")}</div>`;
  }
  if (mode === "side-by-side" || mode === "winner" || mode === "same-source") {
    return `<div class="studio-side-by-side"><figure><img src="${selected.latest_path || selected.output_path}" alt="Selected output"><figcaption>Selected · ${escapeHtml(selected.style || "Output")}</figcaption></figure><figure><img src="${compare.latest_path || compare.output_path}" alt="Comparison output"><figcaption>Compare · ${escapeHtml(compare.style || "Output")}</figcaption></figure></div>`;
  }
  return `<div class="comparison studio-slider" style="--comparison-position: 50%"><img class="comparison-image comparison-image-base" src="${selected.source_path || sourceKey(selected)}" alt="Original source"><div class="comparison-overlay"><img class="comparison-image" src="${selected.latest_path || selected.output_path}" alt="Selected output"></div><div class="comparison-label comparison-label-original">Original</div><div class="comparison-label comparison-label-graded">Selected</div><div class="comparison-divider" aria-hidden="true"></div><input class="comparison-slider" type="range" min="0" max="100" value="50" aria-label="Compare original and selected output" oninput="this.parentElement.style.setProperty('--comparison-position', this.value + '%')" /></div>`;
}

function renderExperimentStudio() {
  const root = document.querySelector("#experiment-studio-root");
  if (!root) return;
  const { rows, sourceRows, selected, compare } = selectedStudioRows();
  if (!rows.length) { root.innerHTML = `<div class="empty">No latest run outputs are available for the studio yet.</div>`; return; }
  if (!studioState.source) studioState.source = sourceKey(selected);
  if (!studioState.output) studioState.output = outputId(selected);
  const sources = bySource(rows);
  const algorithms = [...new Set(rows.map((row) => row.algorithm || "style_range"))].sort();
  const selectedAlgorithm = selected.algorithm || "style_range";
  root.innerHTML = `<div class="studio-layout ${studioState.compact ? "compact" : ""}"><aside class="studio-controls"><label><span>Source</span><select id="studio-source">${sources.map(([key, group]) => optionHtml(key, sourceLabel(group[0]))).join("")}</select></label><label><span>Selected output</span><select id="studio-output">${sourceRows.map((row) => optionHtml(outputId(row), `${row.style || "Output"} · ${row.algorithm || "style_range"} · ${fmtScore(scoreValue(row))}`)).join("")}</select></label><label><span>Compare baseline</span><select id="studio-compare">${sourceRows.map((row) => optionHtml(outputId(row), `${row.style || "Output"} · ${fmtScore(scoreValue(row))}`)).join("")}</select></label><label><span>Mode</span><select id="studio-mode"><option value="slider">Before/after slider</option><option value="side-by-side">Side by side</option><option value="grid">Grid by algorithm</option><option value="winner">Winner vs nearest competitor</option><option value="same-source">Same source latest run</option></select></label><fieldset><legend>Favorite algorithms</legend>${algorithms.map((alg) => `<label class="check"><input type="checkbox" data-studio-algorithm="${escapeHtml(alg)}" ${studioState.algorithms.includes(alg) ? "checked" : ""}>${escapeHtml(alg)}</label>`).join("")}</fieldset><fieldset><legend>Score components</legend>${SCORE_COMPONENTS.map(([key, label, tip]) => `<label class="check" title="${escapeHtml(tip)}"><input type="checkbox" data-studio-component="${key}" ${studioState.components.includes(key) ? "checked" : ""}>${escapeHtml(label)}</label>`).join("")}</fieldset><label class="check"><input id="studio-compact" type="checkbox" ${studioState.compact ? "checked" : ""}>Compact cards</label></aside><div class="studio-workspace">${renderStudioComparison(selected, compare, sourceRows)}<section class="studio-inspector"><div><p class="eyebrow">Candidate explanation</p><h3>${escapeHtml(selected.style || "Selected output")}</h3><p>${escapeHtml(ALGORITHM_DESCRIPTIONS[selectedAlgorithm] || selected.algorithm_description || "Generated candidate from the adaptive color pipeline.")}</p></div><dl class="studio-meta"><div><dt>Algorithm</dt><dd>${escapeHtml(selectedAlgorithm)}</dd></div><div><dt>Selection reason</dt><dd>${escapeHtml(selected.selection_reason || (selected.best_for_source_today ? "Best-scoring output for this source today." : "Candidate retained in the latest generated set."))}</dd></div><div><dt>Candidate rank</dt><dd>${escapeHtml(selected.candidate_rank ?? "—")}</dd></div><div><dt>Diversity score</dt><dd>${fmtScore(selected.diversity_score)}</dd></div><div><dt>Selection score</dt><dd>${fmtScore(selected.overall_selection_score ?? scoreValue(selected))}</dd></div><div><dt>Profile tags</dt><dd>${escapeHtml(profileTags(selected).join(", ") || selected.source_profile_bucket || "—")}</dd></div></dl>${paletteHtml(selected, "Selected output dominant palette")}${componentChartHtml(selected)}<div class="studio-replay"><p class="eyebrow">Replay locally</p><code>python -m src.generate --replay-run-id ${escapeHtml(selected.run_id || data.latest?.run_id || "RUN_ID")}</code><pre>${escapeHtml(replaySnippet(selected))}</pre></div></section></div></div>`;
  for (const [id, value] of [["#studio-source", studioState.source], ["#studio-output", studioState.output], ["#studio-compare", studioState.compare], ["#studio-mode", studioState.mode]]) { const el = document.querySelector(id); if (el) el.value = value; }
  attachStudioEvents();
}

function attachStudioEvents() {
  const rerender = () => { saveStudioPreferences(); writeStudioHash(); renderExperimentStudio(); };
  document.querySelector("#studio-source")?.addEventListener("change", (e) => { studioState.source = e.target.value; studioState.output = ""; studioState.compare = ""; rerender(); });
  document.querySelector("#studio-output")?.addEventListener("change", (e) => { studioState.output = e.target.value; rerender(); });
  document.querySelector("#studio-compare")?.addEventListener("change", (e) => { studioState.compare = e.target.value; rerender(); });
  document.querySelector("#studio-mode")?.addEventListener("change", (e) => { studioState.mode = e.target.value; rerender(); });
  document.querySelector("#studio-compact")?.addEventListener("change", (e) => { studioState.compact = e.target.checked; rerender(); });
  document.querySelectorAll("[data-studio-algorithm]").forEach((el) => el.addEventListener("change", () => { studioState.algorithms = [...document.querySelectorAll("[data-studio-algorithm]:checked")].map((x) => x.dataset.studioAlgorithm); rerender(); }));
  document.querySelectorAll("[data-studio-component]").forEach((el) => el.addEventListener("change", () => { studioState.components = [...document.querySelectorAll("[data-studio-component]:checked")].map((x) => x.dataset.studioComponent); rerender(); }));
}

function downloadJson(name, payload) {
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a"); link.href = url; link.download = name; link.click(); URL.revokeObjectURL(url);
}

function setupStudioActions() {
  document.querySelector("#studio-copy-link")?.addEventListener("click", async () => { writeStudioHash(); await navigator.clipboard?.writeText(location.href); });
  document.querySelector("#studio-download-json")?.addEventListener("click", () => downloadJson("experiment-output.json", selectedStudioRows().selected));
  document.querySelector("#studio-download-manifest")?.addEventListener("click", () => { const s = selectedStudioRows(); downloadJson("comparison-manifest.json", { run_id: data.latest?.run_id, state: studioState, selected: s.selected, compare: s.compare, outputs: s.sourceRows }); });
}


function recipeScore(recipe) { return recipe?.score_summary?.score ?? recipe?.score?.score ?? null; }
function recipeFavoriteIds() { try { return new Set(JSON.parse(localStorage.getItem("favoriteRecipes") || "[]")); } catch { return new Set(); } }
function saveRecipeFavoriteIds(ids) { localStorage.setItem("favoriteRecipes", JSON.stringify([...ids])); }
function recipeCommand(recipe) { return recipe?.replay_command || `python -m src.generate --recipe ${recipe?.recipe_id || "RECIPE_ID"}`; }
function recipePreview(recipe) { return recipe?.source_output_path || recipe?.latest_path || recipe?.output_path || ""; }
function compactRecipeSnippet(recipe) { return JSON.stringify({ recipe_id: recipe.recipe_id, style: recipe.style, algorithm: recipe.algorithm, params: recipe.params, grain_seed_policy: recipe.grain_seed_policy }); }
function collectRecipeOptions() {
  const tags = new Set(), algorithms = new Set(), styles = new Set(), profiles = new Set();
  for (const recipe of data.recipes || []) {
    for (const tag of recipe.tags || []) tags.add(tag);
    if (recipe.algorithm) algorithms.add(recipe.algorithm);
    if (recipe.style) styles.add(recipe.style);
    if (recipe.source_profile_bucket || recipe.source_profile?.profile_bucket) profiles.add(recipe.source_profile_bucket || recipe.source_profile.profile_bucket);
  }
  return { tags: [...tags].sort(), algorithms: [...algorithms].sort(), styles: [...styles].sort(), profiles: [...profiles].sort() };
}
function renderRecipeFilters() {
  const opts = collectRecipeOptions();
  populateSelect("#recipe-filter-tag", opts.tags.map((x) => optionHtml(x, x)), "All tags");
  populateSelect("#recipe-filter-algorithm", opts.algorithms.map((x) => optionHtml(x, x)), "All algorithms");
  populateSelect("#recipe-filter-style", opts.styles.map((x) => optionHtml(x, x)), "All styles");
  populateSelect("#recipe-filter-profile", opts.profiles.map((x) => optionHtml(x, x)), "All profiles");
}
function setupRecipeFilters() {
  document.querySelector("#recipe-filters")?.addEventListener("submit", (event) => event.preventDefault());
  const controls = [["#recipe-filter-tag", "tag"], ["#recipe-filter-algorithm", "algorithm"], ["#recipe-filter-style", "style"], ["#recipe-filter-profile", "profile"], ["#recipe-filter-favorites", "favorites"]];
  for (const [selector, key] of controls) {
    const el = document.querySelector(selector); if (!el) continue; el.value = recipeFilters[key];
    el.addEventListener("change", (event) => { recipeFilters[key] = event.target.value; renderRecipes(); });
  }
  const min = document.querySelector("#recipe-filter-score");
  if (min) { min.value = recipeFilters.minScore; min.addEventListener("input", (event) => { recipeFilters.minScore = event.target.value; renderRecipes(); }); }
  document.querySelector("#recipe-download-all")?.addEventListener("click", () => downloadJson("recipes.json", data.recipes || []));
}
function renderRecipes() {
  const container = document.querySelector("#recipes"); if (!container) return;
  const favorites = recipeFavoriteIds();
  const minScore = Number(recipeFilters.minScore);
  const rows = (data.recipes || [])
    .filter((r) => recipeFilters.tag === "all" || (r.tags || []).includes(recipeFilters.tag))
    .filter((r) => recipeFilters.algorithm === "all" || r.algorithm === recipeFilters.algorithm)
    .filter((r) => recipeFilters.style === "all" || r.style === recipeFilters.style)
    .filter((r) => recipeFilters.profile === "all" || (r.source_profile_bucket || r.source_profile?.profile_bucket) === recipeFilters.profile)
    .filter((r) => !Number.isFinite(minScore) || Number(recipeScore(r) || 0) >= minScore)
    .filter((r) => recipeFilters.favorites !== "favorites" || favorites.has(r.recipe_id))
    .sort((a, b) => Number(recipeScore(b) || 0) - Number(recipeScore(a) || 0));
  if (!rows.length) { container.innerHTML = `<div class="empty">No recipes match the current filters yet.</div>`; return; }
  container.innerHTML = rows.map((recipe) => {
    const command = recipeCommand(recipe);
    const analytics = (data.recipeAnalytics?.recipes || []).find((row) => row.recipe_id === recipe.recipe_id) || {};
    return `<article class="recipe-card ${favorites.has(recipe.recipe_id) ? "favorite" : ""}">
      ${recipePreview(recipe) ? `<img class="recipe-preview" src="${escapeHtml(recipePreview(recipe))}" alt="Preview for ${escapeHtml(recipe.name || recipe.recipe_id)}">` : ""}
      <div class="recipe-body"><div class="recipe-top"><div><h3>${escapeHtml(recipe.name || recipe.recipe_id)}</h3><p class="row-subtitle">${escapeHtml(recipe.algorithm || "style_range")} · ${escapeHtml(recipe.style || "unknown")} · ${escapeHtml(recipe.source_profile_bucket || recipe.source_profile?.profile_bucket || "unknown profile")}</p></div><strong class="score">${fmtScore(recipeScore(recipe))}</strong></div>
      ${paletteHtml(recipe, "Recipe palette")}
      <div class="recipe-tags">${(recipe.tags || []).map((tag) => `<span class="recipe-tag">${escapeHtml(tag)}</span>`).join("")}</div>
      <code class="recipe-command">${escapeHtml(command)}</code>
      <details class="recipe-inspector"><summary>Inspect recipe JSON</summary><pre>${escapeHtml(JSON.stringify(recipe, null, 2))}</pre><p class="muted">Uses: ${analytics.usage_count || 0} · reused avg ${fmtScore(analytics.average_score_when_reused)} · best profile ${escapeHtml(analytics.best_source_profile_match || "—")} · drift ${escapeHtml(analytics.recipe_drift ?? "—")}</p></details>
      <div class="recipe-card-actions"><button type="button" data-recipe-favorite="${escapeHtml(recipe.recipe_id)}">${favorites.has(recipe.recipe_id) ? "Unfavorite" : "Favorite"}</button><button type="button" data-recipe-copy="${escapeHtml(recipe.recipe_id)}">Copy command</button><button type="button" data-recipe-snippet="${escapeHtml(recipe.recipe_id)}">Copy snippet</button><button type="button" data-recipe-download="${escapeHtml(recipe.recipe_id)}">Export JSON</button></div></div>
    </article>`;
  }).join("");
  document.querySelectorAll("[data-recipe-favorite]").forEach((el) => el.addEventListener("click", () => { const ids = recipeFavoriteIds(); const id = el.dataset.recipeFavorite; ids.has(id) ? ids.delete(id) : ids.add(id); saveRecipeFavoriteIds(ids); renderRecipes(); }));
  document.querySelectorAll("[data-recipe-copy]").forEach((el) => el.addEventListener("click", async () => { const r = data.recipes.find((x) => x.recipe_id === el.dataset.recipeCopy); await navigator.clipboard?.writeText(recipeCommand(r)); }));
  document.querySelectorAll("[data-recipe-snippet]").forEach((el) => el.addEventListener("click", async () => { const r = data.recipes.find((x) => x.recipe_id === el.dataset.recipeSnippet); await navigator.clipboard?.writeText(compactRecipeSnippet(r)); }));
  document.querySelectorAll("[data-recipe-download]").forEach((el) => el.addEventListener("click", () => { const r = data.recipes.find((x) => x.recipe_id === el.dataset.recipeDownload); downloadJson(`${r.recipe_id}.json`, r); }));
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
        ${scoreBreakdownHtml(bestOutput)}
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
        ${scoreBreakdownHtml(output)}
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

function styleBattleOptionHtml(row, index, selectedIndex = 0) {
  const styleName = row?.style || `Output ${index + 1}`;
  const score = fmtScore(scoreValue(row));
  const imagePath = row?.latest_path || row?.output_path || "";
  const outputPath = row?.output_path || imagePath;
  return `
    <option
      value="${index}"${index === selectedIndex ? " selected" : ""}
      data-image="${escapeHtml(imagePath)}"
      data-output="${escapeHtml(outputPath)}"
      data-style="${escapeHtml(styleName)}"
      data-score="${escapeHtml(score)}"
    >${escapeHtml(styleName)} · ${escapeHtml(score)}</option>
  `;
}

function updateBattleComparison(sourceIndex) {
  const battle = document.querySelector(`[data-battle-index="${sourceIndex}"]`);
  if (!battle) return;

  const leftOption = battle.querySelector('[data-battle-select="left"]')?.selectedOptions?.[0];
  const rightOption = battle.querySelector('[data-battle-select="right"]')?.selectedOptions?.[0];
  const leftImage = battle.querySelector('[data-battle-image="left"]');
  const rightImage = battle.querySelector('[data-battle-image="right"]');
  const leftLabel = battle.querySelector('[data-battle-label="left"]');
  const rightLabel = battle.querySelector('[data-battle-label="right"]');
  const leftLink = battle.querySelector('[data-battle-link="left"]');
  const rightLink = battle.querySelector('[data-battle-link="right"]');

  const applyOption = (option, image, label, link, side) => {
    if (!option || !image || !label) return;
    const styleName = option.dataset.style || `${side} style`;
    const imagePath = option.dataset.image || "";
    const outputPath = option.dataset.output || imagePath;
    const score = option.dataset.score || "—";

    image.src = imagePath;
    image.alt = `${side} battle image: ${styleName}`;
    label.textContent = styleName;
    label.title = `${styleName} · ${score}`;
    if (link) {
      link.href = outputPath;
      link.textContent = `${styleName} (${score})`;
    }
  };

  applyOption(leftOption, leftImage, leftLabel, leftLink, "Left");
  applyOption(rightOption, rightImage, rightLabel, rightLink, "Right");
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
    .map(([source, rows], sourceIndex) => {
      const sourceThumb = source;
      rows.sort((a, b) => Number(a.index || 0) - Number(b.index || 0));
      const battleLeft = rows[0] || {};
      const battleRight = rows[1] || rows[0] || {};
      const battleLeftOptions = rows.map((row, index) => styleBattleOptionHtml(row, index, 0)).join("");
      const battleRightOptions = rows.map((row, index) => styleBattleOptionHtml(row, index, rows.length > 1 ? 1 : 0)).join("");
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
          <div class="style-battle" data-battle-index="${sourceIndex}">
            <div class="style-battle-copy">
              <p class="eyebrow">Style battle</p>
              <h4>Compare generated outputs</h4>
              <p class="muted">Pick any two styles from this source and drag the slider to compare them head-to-head.</p>
            </div>
            <div class="battle-controls" aria-label="Style battle controls for ${escapeHtml(source)}">
              <label>
                <span>Left style</span>
                <select data-battle-select="left" onchange="updateBattleComparison(${sourceIndex})">
                  ${battleLeftOptions}
                </select>
              </label>
              <label>
                <span>Right style</span>
                <select data-battle-select="right" onchange="updateBattleComparison(${sourceIndex})">
                  ${battleRightOptions}
                </select>
              </label>
            </div>
            <div class="battle-panel">
              <div class="comparison battle-comparison" style="--comparison-position: 50%">
                <img class="comparison-image comparison-image-base" data-battle-image="left" src="${battleLeft.latest_path || battleLeft.output_path || ""}" alt="Left battle image: ${battleLeft.style || "Generated output"}" />
                <div class="comparison-overlay">
                  <img class="comparison-image" data-battle-image="right" src="${battleRight.latest_path || battleRight.output_path || ""}" alt="Right battle image: ${battleRight.style || "Generated output"}" />
                </div>
                <div class="comparison-label comparison-label-original" data-battle-label="left" title="${battleLeft.style || "Left style"} · ${fmtScore(scoreValue(battleLeft))}">${battleLeft.style || "Left"}</div>
                <div class="comparison-label comparison-label-graded" data-battle-label="right" title="${battleRight.style || "Right style"} · ${fmtScore(scoreValue(battleRight))}">${battleRight.style || "Right"}</div>
                <div class="comparison-divider" aria-hidden="true"></div>
                <input
                  class="comparison-slider"
                  type="range"
                  min="0"
                  max="100"
                  value="50"
                  aria-label="Compare two generated style outputs"
                  oninput="this.parentElement.style.setProperty('--comparison-position', this.value + '%')"
                />
              </div>
              <div class="battle-links">
                <a data-battle-link="left" href="${battleLeft.output_path || battleLeft.latest_path || ""}" target="_blank" rel="noreferrer">${battleLeft.style || "Left"} (${fmtScore(scoreValue(battleLeft))})</a>
                <a data-battle-link="right" href="${battleRight.output_path || battleRight.latest_path || ""}" target="_blank" rel="noreferrer">${battleRight.style || "Right"} (${fmtScore(scoreValue(battleRight))})</a>
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
                    <div class="badges">${(row.badges || [row.algorithm]).filter(Boolean).map((badge) => `<span class="badge">${escapeHtml(badge)}</span>`).join("")}</div>
                    <p class="row-subtitle">${escapeHtml(row.algorithm || "style_range")} · ${escapeHtml((row.source_profile_tags || []).join(", "))}</p>
                    <p class="muted">${escapeHtml(row.selection_reason || "")}</p>
                    ${scoreBreakdownHtml(row)}
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

function sortLeaderboardRows(a, b) {
  if (leaderboardFilters.sort === "diversity") return Number(b.diversity_score || 0) - Number(a.diversity_score || 0);
  if (leaderboardFilters.sort === "selection") return Number((b.overall_selection_score ?? scoreValue(b)) || 0) - Number((a.overall_selection_score ?? scoreValue(a)) || 0);
  if (leaderboardFilters.sort === "newest") return String(b.run_date || "").localeCompare(String(a.run_date || ""));
  if (leaderboardFilters.sort === "algorithm") return String(a.algorithm || "style_range").localeCompare(String(b.algorithm || "style_range"));
  return Number(scoreValue(b) || 0) - Number(scoreValue(a) || 0);
}

function renderLeaderboardFilterChips() {
  const chips = document.querySelector("#leaderboard-filter-chips");
  if (!chips) return;
  const active = Object.entries(leaderboardFilters).filter(([key, value]) => value && value !== "all" && !(key === "sort" && value === "score"));
  chips.innerHTML = active.length ? active.map(([key, value]) => `<span>${escapeHtml(key)}: ${escapeHtml(value)}</span>`).join("") : `<span>No active filters</span>`;
}

function renderLeaderboard() {
  const container = document.querySelector("#leaderboard");
  const minScore = Number(leaderboardFilters.minScore);
  const rows = (data.leaderboard || [])
    .filter((row) => leaderboardFilters.style === "all" || row.style === leaderboardFilters.style)
    .filter((row) => leaderboardFilters.source === "all" || sourceKey(row) === leaderboardFilters.source)
    .filter((row) => leaderboardFilters.runDate === "all" || row.run_date === leaderboardFilters.runDate)
    .filter((row) => leaderboardFilters.algorithm === "all" || row.algorithm === leaderboardFilters.algorithm)
    .filter((row) => leaderboardFilters.profileBucket === "all" || (row.source_profile_bucket || row.source_profile?.profile_bucket) === leaderboardFilters.profileBucket)
    .filter((row) => !Number.isFinite(minScore) || Number(scoreValue(row) || 0) >= minScore)
    .filter((row) => leaderboardFilters.badge === "all" || (row.badges || []).includes(leaderboardFilters.badge))
    .filter((row) => leaderboardFilters.profileTag === "all" || profileTagsForFilter(row).includes(leaderboardFilters.profileTag))
    .sort((a, b) => sortLeaderboardRows(a, b))
    .slice(0, 20);
  renderLeaderboardFilterChips();
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
          ${scoreBreakdownHtml(row)}
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

function sourceEventLabel(eventName) {
  return String(eventName || "source_changed")
    .replace(/^source_/, "")
    .replaceAll("_", " ");
}

function sourceEventClass(eventName) {
  const normalized = String(eventName || "changed").replace(/^source_/, "");
  if (["added", "changed", "removed", "reactivated"].includes(normalized)) return normalized;
  return "changed";
}

function sourceEventHashEntries(event) {
  return Object.entries(event || {})
    .filter(([key, value]) => key.toLowerCase().includes("hash") && value !== null && value !== undefined && value !== "")
    .sort(([left], [right]) => left.localeCompare(right));
}

function renderSourceEvent(event) {
  const eventClass = sourceEventClass(event.event);
  const hashEntries = sourceEventHashEntries(event);

  return `
    <li class="source-timeline-event event-${eventClass}">
      <div class="source-event-marker" aria-hidden="true"></div>
      <div class="source-event-card">
        <div class="source-event-topline">
          <span class="source-event-badge">${escapeHtml(sourceEventLabel(event.event))}</span>
          <time>${escapeHtml(event.time || "Time unknown")}</time>
        </div>
        <p class="row-subtitle"><code>${escapeHtml(event.path || "unknown source")}</code></p>
        ${
          hashEntries.length
            ? `<dl class="source-event-hashes">
                ${hashEntries
                  .map(
                    ([key, value]) => `
                      <div>
                        <dt>${escapeHtml(key)}</dt>
                        <dd><code>${escapeHtml(value)}</code></dd>
                      </div>
                    `,
                  )
                  .join("")}
              </dl>`
            : ""
        }
      </div>
    </li>
  `;
}

function renderAlgorithmAnalytics() {
  const container = document.querySelector("#algorithm-analytics");
  if (!container) return;
  const summary = data.algorithmAnalytics || {};
  const rows = (summary.algorithms || []).slice(0, 12);
  if (!rows.length) { container.innerHTML = `<div class="empty">No algorithm analytics yet.</div>`; return; }
  container.innerHTML = `
    <div class="analytics-summary muted">${summary.output_count || 0} outputs · latest run ${summary.latest_run_date || "—"}</div>
    <div class="style-rankings">${rows.map((row) => `
      <article class="style-row"><div class="rank">#${row.rank}</div><div><strong>${escapeHtml(row.algorithm)}</strong><p class="row-subtitle">${row.usage_count} uses · ${row.daily_wins} daily wins · ${row.source_wins} source wins</p></div><div class="trend-metrics"><span><small>Avg</small>${fmtScore(row.average_score)}</span><span><small>Best</small>${fmtScore(row.best_score)}</span><span><small>7-day</small>${fmtScore(row.recent_7_day_average)}</span></div></article>`).join("")}</div>`;
}

function renderSourceAnalytics() {
  const container = document.querySelector("#source-analytics");
  const summary = data.sourceAnalytics || {};
  const rows = (summary.sources || []).slice(0, 12);
  if (!container) return;
  if (!rows.length) {
    container.innerHTML = `<div class="empty">No source analytics yet. Generate a run to build source rankings.</div>`;
    return;
  }

  container.innerHTML = `
    <div class="analytics-summary muted">
      ${summary.output_count || 0} scored outputs across ${summary.run_count || 0} runs · latest run ${summary.latest_run_date || "—"}
    </div>
    <div class="source-rankings">
      ${rows
        .map((row) => {
          const bestOutput = row.best_output || {};
          const imagePath = bestOutput.latest_path || bestOutput.output_path || row.source_path || "";
          const linkPath = bestOutput.output_path || imagePath;
          const sourceName = row.source_name || row.source_path || row.source_sha256 || "Unknown source";
          return `
            <article class="source-rank-card">
              <a class="source-rank-image" href="${linkPath}" target="_blank" rel="noreferrer">
                <img src="${imagePath}" alt="Best output for ${sourceName}" />
                <span class="rank">#${row.rank}</span>
              </a>
              <div class="source-rank-body">
                <div>
                  <strong>${sourceName}</strong>
                  <p class="row-subtitle">Best style: ${row.best_style || "—"}</p>
                </div>
                <div class="source-rank-stats">
                  <span><small>Outputs</small>${row.count || 0}</span>
                  <span><small>Avg</small>${fmtScore(row.average_score)}</span>
                  <span><small>Best</small>${fmtScore(row.best_score)}</span>
                  <span><small>Daily wins</small>${row.daily_wins || 0}</span>
                  <span><small>Source wins</small>${row.source_wins || 0}</span>
                </div>
              </div>
            </article>
          `;
        })
        .join("")}
    </div>
  `;
}

function renderEvents() {
  const container = document.querySelector("#source-events");
  const rows = data.events || [];
  if (!rows.length) {
    container.innerHTML = `<div class="empty">No source changes recorded yet.</div>`;
    return;
  }

  const groupedEvents = new Map();
  for (const event of rows) {
    const path = event.path || "unknown source";
    if (!groupedEvents.has(path)) groupedEvents.set(path, []);
    groupedEvents.get(path).push(event);
  }

  const timelines = [...groupedEvents.entries()]
    .map(([path, events]) => ({
      path,
      events: events.sort((a, b) => String(b.time || "").localeCompare(String(a.time || ""))),
    }))
    .sort((a, b) => String(b.events[0]?.time || "").localeCompare(String(a.events[0]?.time || "")));

  container.innerHTML = timelines
    .map(
      ({ path, events }) => `
        <article class="source-timeline">
          <header class="source-timeline-header">
            <div>
              <p class="eyebrow">Source timeline</p>
              <h3><code>${escapeHtml(path)}</code></h3>
            </div>
            <span>${events.length} ${events.length === 1 ? "event" : "events"}</span>
          </header>
          <ol class="source-timeline-events">
            ${events.map(renderSourceEvent).join("")}
          </ol>
        </article>
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
  data.sourceAnalytics = await loadJson("data/source-analytics.json", {});
  data.algorithmAnalytics = await loadJson("data/algorithm-analytics.json", {});
  data.recipeAnalytics = await loadJson("data/recipe-analytics.json", {});
  data.recipes = await loadJson("data/recipes.json", []);

  loadStudioPreferences();
  parseStudioHash();

  renderDataHealth();
  renderMetrics();
  renderDailyWinner();
  setupWinnerReveal();
  renderToday();
  renderRecipeFilters();
  setupRecipeFilters();
  renderRecipes();
  renderExperimentStudio();
  setupStudioActions();
  renderLeaderboardFilters();
  setupLeaderboardFilters();
  renderLeaderboard();
  renderStyleAnalytics();
  renderAlgorithmAnalytics();
  renderSourceAnalytics();
  renderEvents();
  renderRuns();
}

init();
