# daily-color-lottery

A GitHub-powered daily color grading lottery.

Put one or more images in `sources/`. GitHub Actions will run once per day, generate five randomized color-graded versions for every source image, score them with a stable non-AI image-quality heuristic, commit the outputs and logs back to the repo, and publish a lab-style dashboard with GitHub Pages.

## What it does

- Processes every image in `sources/`
- Generates 5 outputs per source image, one for each style:
  - `cinematic_warm`
  - `moody_blue`
  - `film_faded`
  - `clean_bright`
  - `high_contrast_pop`
- Uses OS entropy through Python `secrets.SystemRandom()` for non-seeded random parameters
- Preserves original image dimensions
- Saves outputs under `output/archive/` and `output/latest/`
- Tracks source additions, removals, and content changes
- Writes machine-readable logs under `logs/`
- Builds dashboard data under `docs/data/`
- Publishes a GitHub Pages dashboard through Actions
- Shows interactive before/after comparison sliders for each generated output
- Highlights the highest-scoring output as a daily winner hero showcase
- Provides an all-time leaderboard with style, source, and run-date filters
- Builds style analytics with rankings, averages, win counts, recent trends, and best examples
- Creates a weekly release bundle plus per-source animated showcase assets

## Quick start

1. Create a new public GitHub repository named `daily-color-lottery`.
2. Upload this project into the repository root.
3. Go to **Settings → Actions → General** and allow GitHub Actions to read and write repository contents.
4. Go to **Settings → Pages** and set the source to **GitHub Actions**.
5. Replace or add images in `sources/`.
6. Run **Actions → Daily Color Lottery → Run workflow** once manually.

The workflow will commit generated files back into the repository and deploy the dashboard.

## Local run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# Weekly showcase video packaging also requires ffmpeg on PATH.
python -m src.generate
python -m src.build_site
```

Open `site/index.html` after running `python -m src.build_site`. The generated dashboard reads the JSON files in `docs/data/`, including `style-analytics.json` when one or more runs have been recorded.

## Important folders

```text
sources/              Input images
output/latest/        Latest generated outputs
output/archive/       Historical generated outputs
logs/                 Run logs, source inventory, and event logs
docs/                 Dashboard source files
docs/data/            JSON data consumed by the dashboard
site/                 Local build output, ignored by git
dist/                 Release zip output, ignored by git
src/                  Python implementation
tests/                Lightweight tests
```


## Dashboard features

The GitHub Pages dashboard in `docs/` is designed as a lightweight lab report for the latest run and historical results:

- **Daily winner hero**: the latest run's highest-scoring output is promoted above the metrics so the day's top color grade is visible first.
- **Before/after comparisons**: each generated result includes a draggable comparison slider between the original source image and the graded output.
- **Style analytics**: `src.generate` writes `logs/style_analytics.json` and `docs/data/style-analytics.json` from the compacted run log. The dashboard ranks styles by average score and displays output counts, best scores, daily wins, source wins, recent 7-day averages, and each style's best example.
- **Filtered leaderboard**: the all-time leaderboard can be narrowed by style, source image, or run date without rebuilding the site.

## Weekly releases

The weekly release workflow creates multiple GitHub Release assets:

- `daily-color-lottery-week-YYYY-MM-DD.zip`: recent generated outputs from `output/archive/` for the last 7 UTC days, plus repository logs.
- `daily-color-lottery-week-YYYY-MM-DD-showcase-SOURCE-HASH.zip`: one zip per source image, so large source sets stay split across smaller assets. Each source showcase zip contains:
  - `showcase/weekly-showcase.mp4` — a 16:9 MP4 recap of that source's weekly top 5 scored outputs.
  - `showcase/weekly-showcase.html` — a single-file HTML report with the MP4 embedded as base64, top-5 cards, scores, metadata, and an inline manifest.
  - `showcase/manifest.json` — machine-readable source, week, video, and selected-output metadata.
  - `showcase/build.log` — full build details, including frame selection and the ffmpeg command/stdout/stderr.

The showcase selection is based on `logs/runs.jsonl`: for each source, the workflow filters outputs to the same weekly UTC window, sorts by `score.score`, and picks up to 5 existing output files.

## Configuration

Edit `config/settings.json` to adjust styles, scoring weights, output quality, and workflow behavior.

By default, the project keeps outputs in git history. Deleting files later will remove them from the current working tree, but normal git history will still retain old blobs unless history is rewritten.

## Manual controls

- Daily generation: **Actions → Daily Color Lottery → Run workflow**
- Weekly release: **Actions → Weekly Release Bundle → Run workflow**
- CI check: runs on push and pull request

## Notes

This project intentionally avoids AI models so it can run reliably on GitHub-hosted CPU runners. The score is a heuristic, not a real aesthetic judgment.


## Adaptive multi-algorithm color lab

Daily Color Lottery now profiles every source image before rendering variants. The source profile records mean luminance, luminance standard deviation, clipping ratio, mean saturation, dominant palette, hue spread, temperature bias, and local contrast/sharpness tags. These metrics are stored with selected outputs in `logs/latest_run.json`, `logs/runs.jsonl`, and `docs/data/latest-run.json`.

Generation is no longer limited to the first configured style ranges. A candidate pipeline builds many looks from multiple algorithms: the backward-compatible `style_range` sampler, `adaptive_auto_enhance`, `palette_cinematic`, `diversity_explorer`, and `monochrome_editorial`. Candidates are rendered, scored, and selected using quality plus diversity across algorithms, palettes, and exposure/contrast/saturation choices.

Replay compatibility is preserved: run records still store `style`, `params`, and `grain_seed_hex`, so `--replay-run-log` and `--replay-run-id` can regenerate outputs from historical records. New metadata such as `algorithm`, `source_profile`, `selection_reason`, `candidate_rank`, `diversity_score`, and `overall_selection_score` is additive for existing JSON consumers.

Analytics now include style, source, algorithm, and source-profile-bucket summaries. In addition to existing `style-analytics.json` and `source-analytics.json`, the site writes `docs/data/algorithm-analytics.json` with rankings, average scores, best outputs, daily/source wins, recent 7-day averages, and usage counts.

## Experiment Studio

The GitHub Pages dashboard now includes an **Experiment Studio** section that turns the static report into a client-side lab for the adaptive multi-algorithm pipeline. It remains static-site friendly: all controls read from JSON already published under `docs/data/`, and no backend service or external chart library is required.

Studio capabilities include:

- **Shareable state**: selected source, output, comparison baseline, and comparison mode are encoded in URL hashes such as `#studio?source=...&output=...&compare=...`.
- **Persistent preferences**: comparison mode, favorite algorithms, visible score components, and compact card mode are stored in browser `localStorage`.
- **Comparison modes**: before/after slider, side-by-side comparison, grid-by-algorithm review, winner-vs-nearest-competitor, and same-source latest-run inspection.
- **Candidate explanations**: algorithm label/description, selection reason, rank, diversity score, overall selection score, profile tags, palette, score components, and full replay params are shown for the selected output. Missing newer adaptive fields degrade to sensible fallback text.
- **Score explorer**: selected metrics render as vanilla SVG bars with tooltips for exposure, contrast, saturation, clipping, sharpness, palette harmony, dynamic range, mood distinctiveness, and artifact risk.
- **Replay and export tools**: each selected result shows a copyable local replay command (`python -m src.generate --replay-run-id <run_id>`), a JSON replay snippet, downloadable output metadata, downloadable comparison manifests, and a permalink copy action.

The leaderboard has also been expanded with min-score, badge, source-profile-tag, and sort controls while preserving the existing style/source/date/algorithm/profile filters.

### Dashboard data expectations

For full Studio fidelity, rows in `docs/data/latest-run.json` should include the stable fields already emitted by generation (`run_id`, `source_path`, `output_path` or `latest_path`, `style`, `params`, and `score.score`) plus any available adaptive metadata (`algorithm`, `algorithm_description`, `selection_reason`, `candidate_rank`, `diversity_score`, `overall_selection_score`, `palette`, `source_profile`, and `source_profile_tags`). Older rows remain usable; the dashboard treats adaptive fields as optional.

## Reusable color recipes

High-performing generated outputs are promoted into reusable recipe presets. A recipe captures the stable recipe id, source output path and run id, algorithm/style metadata, exact grade params, grain seed policy, source profile bucket, score summary, palette, tags, and creation date. Catalogs are written to `logs/recipes.json` for local history and `docs/data/recipes.json` for the static dashboard.

Recipe ids are deterministic hashes of the normalized params, style, algorithm, and source profile bucket. This keeps repeated promotions deduplicated while allowing the same look to be bucketed separately for different source profiles.

### Applying a recipe

Normal daily generation remains the default. Recipe mode is opt-in:

```bash
python -m src.generate --recipe recipe-abc123
python -m src.generate --recipe recipe-abc123 --recipe-file docs/data/recipes.json
```

When a recipe is selected, its params are applied to every current source image, outputs are scored normally, and run rows include `mode: "recipe"` and `recipe_id`. Set `recipes.regenerate_grain` in `config/settings.json` to control whether grain seeds are regenerated or fixed from the promoted source output.

### Dashboard marketplace

The GitHub Pages dashboard includes a Presets / Recipes marketplace. Cards show a preview image, recipe name, algorithm/style, score, tags, palette, profile compatibility, analytics when reuse data exists, and the replay command. Filters support tag, algorithm, style, profile bucket, minimum score, and favorites. Favorites are stored in browser `localStorage` only.

Each recipe card can export a single JSON file, copy an apply command, or copy a compact recipe snippet. The section also supports downloading the full recipe catalog JSON.
