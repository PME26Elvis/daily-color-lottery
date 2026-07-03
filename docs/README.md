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
