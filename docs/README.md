This folder contains the static dashboard source. GitHub Actions builds a deployable `site/` folder by combining this folder with `output/` and `sources/`.


## Adaptive dashboard data

The dashboard consumes additive metadata from the adaptive color lab. `latest-run.json` output rows may include algorithm labels, algorithm descriptions, source profile metrics/tags, selection reasons, candidate ranks, diversity scores, and expanded score components. Existing fields such as `style`, `params`, `score`, `palette`, `output_path`, and `latest_path` remain available for compatibility.

`algorithm-analytics.json` powers the Algorithm Ranking section and complements `style-analytics.json` and `source-analytics.json`. Leaderboard filters can now narrow results by style, source, run date, algorithm, and source profile bucket.

## Experiment Studio

`index.html` includes a static **Experiment Studio** mounted at `#experiment-studio`. The browser reads `data/latest-run.json` and related analytics files directly, so the feature works on GitHub Pages without server-side code.

Supported interactions:

- Select a source, selected output, and comparison baseline.
- Switch between before/after slider, side-by-side, algorithm grid, winner-vs-nearest-competitor, and same-source latest-run comparison modes.
- Share a Studio view with `#studio?source=...&output=...&compare=...&mode=...` hash state.
- Persist lightweight preferences in `localStorage` for favorite algorithms, visible score components, comparison mode, and compact display.
- Inspect candidate explanations, dominant palettes, score components, full params, and replay snippets.
- Copy permalinks or download selected-output metadata and comparison manifests as client-generated JSON blobs.

Rows in `data/latest-run.json` should always provide `source_path`, `style`, `params`, a numeric `score.score`, and either `output_path` or `latest_path`. Optional adaptive fields such as `algorithm`, `selection_reason`, `candidate_rank`, `diversity_score`, `overall_selection_score`, `palette`, and `source_profile_tags` make the Studio richer but are not required for compatibility with older generated JSON.

## Preset marketplace data

The static dashboard reads reusable color presets from `docs/data/recipes.json` and optional reuse statistics from `docs/data/recipe-analytics.json`. Favorites are client-side only and are persisted in `localStorage` under `favoriteRecipes`.

Recipe cards expose preview images, tags, palette chips, source profile compatibility, score summaries, copyable `python -m src.generate --recipe <recipe-id>` commands, single-recipe JSON export, compact snippet copy, and full-catalog download.

## Dashboard data contracts and fallbacks

The static dashboard is dependency-free and loads JSON files from `docs/data/`. Required files are `latest-run.json`, `runs.json`, `leaderboard.json`, `style-analytics.json`, `source-analytics.json`, and `algorithm-analytics.json`; recipe files are optional but enabled when `recipes.json` or `recipe-analytics.json` exists.

Output rows are backward compatible with older runs. The UI tolerates missing `algorithm`, `source_profile_tags`, `selection_reason`, `badges`, `palette`, `recipe_id`, and profile-bucket metadata by displaying empty filters, `unknown` labels, or compact fallback text instead of throwing errors. A data health panel appears near the top of the page and reports absent or malformed JSON files.

Recipe catalog entries should include `recipe_id`, `style`, `params`, optional `tags`, optional `palette`, optional `score_summary`, and a copyable `replay_command` such as `python -m src.generate --recipe <recipe-id>`.
