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
