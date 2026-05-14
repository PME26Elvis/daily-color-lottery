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
- Creates a weekly release bundle

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
python -m src.generate
python -m src.build_site
```

Open `site/index.html` after running `python -m src.build_site`.

## Important folders

```text
sources/              Input images
output/latest/        Latest generated outputs
output/archive/       Historical generated outputs
logs/                 Run logs, source inventory, and event logs
docs/                 Dashboard source files
docs/data/            JSON data consumed by the dashboard
site/                 Local build output, ignored by git
src/                  Python implementation
tests/                Lightweight tests
```

## Configuration

Edit `config/settings.json` to adjust styles, scoring weights, output quality, and workflow behavior.

By default, the project keeps outputs in git history. Deleting files later will remove them from the current working tree, but normal git history will still retain old blobs unless history is rewritten.

## Manual controls

- Daily generation: **Actions → Daily Color Lottery → Run workflow**
- Weekly release: **Actions → Weekly Release Bundle → Run workflow**
- CI check: runs on push and pull request

## Notes

This project intentionally avoids AI models so it can run reliably on GitHub-hosted CPU runners. The score is a heuristic, not a real aesthetic judgment.
