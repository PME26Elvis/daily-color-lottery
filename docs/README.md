This folder contains the static dashboard source. GitHub Actions builds a deployable `site/` folder by combining this folder with `output/` and `sources/`.


## Adaptive dashboard data

The dashboard consumes additive metadata from the adaptive color lab. `latest-run.json` output rows may include algorithm labels, algorithm descriptions, source profile metrics/tags, selection reasons, candidate ranks, diversity scores, and expanded score components. Existing fields such as `style`, `params`, `score`, `palette`, `output_path`, and `latest_path` remain available for compatibility.

`algorithm-analytics.json` powers the Algorithm Ranking section and complements `style-analytics.json` and `source-analytics.json`. Leaderboard filters can now narrow results by style, source, run date, algorithm, and source profile bucket.
