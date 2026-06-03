from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import shutil
import subprocess
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps

from src.utils import ensure_dir, load_jsonl, slugify, write_json

EXIT_NO_FILES = 78


@dataclass(frozen=True)
class WeekWindow:
    today: date
    earliest: date

    @property
    def label(self) -> str:
        return f"{self.earliest.isoformat()}..{self.today.isoformat()}"


def parse_iso_date(value: str) -> date | None:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def score_value(row: dict[str, Any]) -> float:
    try:
        return float(row.get("score", {}).get("score", 0.0))
    except (TypeError, ValueError):
        return 0.0


def make_week_window(days: int, today: date | None = None) -> WeekWindow:
    if days < 1:
        raise ValueError("--days must be at least 1")
    resolved_today = today or datetime.now(timezone.utc).date()
    return WeekWindow(today=resolved_today, earliest=resolved_today - timedelta(days=days - 1))


def select_weekly_top_outputs(
    runs_path: Path,
    root: Path,
    window: WeekWindow,
    max_per_source: int,
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for run in load_jsonl(runs_path):
        run_date = parse_iso_date(str(run.get("run_date", "")))
        if run_date is None or run_date < window.earliest or run_date > window.today:
            continue
        for output in run.get("outputs", []):
            output_path = root / str(output.get("output_path", ""))
            if not output_path.is_file():
                continue
            source_key = str(output.get("source_path") or output.get("source_slug") or "source")
            grouped[source_key].append(output)

    selected: dict[str, list[dict[str, Any]]] = {}
    for source_key, rows in sorted(grouped.items()):
        rows = sorted(
            rows,
            key=lambda row: (
                score_value(row),
                str(row.get("run_id", "")),
                str(row.get("output_path", "")),
            ),
            reverse=True,
        )
        selected[source_key] = rows[:max_per_source]
    return selected


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(path.as_posix(), size=size)
    return ImageFont.load_default()


def text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def draw_centered(
    draw: ImageDraw.ImageDraw,
    text: str,
    y: int,
    width: int,
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int],
) -> None:
    tw, _ = text_size(draw, text, font)
    draw.text(((width - tw) // 2, y), text, font=font, fill=fill)


def fit_cover(img: Image.Image, size: tuple[int, int], zoom: float, pan_x: float, pan_y: float) -> Image.Image:
    target_w, target_h = size
    scale = max(target_w / img.width, target_h / img.height) * zoom
    resized = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.Resampling.LANCZOS)
    extra_x = max(0, resized.width - target_w)
    extra_y = max(0, resized.height - target_h)
    left = int(extra_x * (0.5 + pan_x * 0.5))
    top = int(extra_y * (0.5 + pan_y * 0.5))
    return resized.crop((left, top, left + target_w, top + target_h))


def dark_gradient(size: tuple[int, int]) -> Image.Image:
    width, height = size
    gradient = Image.new("RGB", (1, height))
    px = gradient.load()
    for y in range(height):
        ratio = y / max(1, height - 1)
        shade = int(13 + 18 * ratio)
        px[0, y] = (max(5, shade - 5), max(8, shade - 4), max(13, shade + 5))
    return gradient.resize((width, height), Image.Resampling.BICUBIC)


def draw_badge(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, font: ImageFont.ImageFont) -> None:
    x, y = xy
    tw, th = text_size(draw, text, font)
    pad_x, pad_y = 18, 10
    rect = (x, y, x + tw + pad_x * 2, y + th + pad_y * 2)
    draw.rounded_rectangle(rect, radius=16, fill=(250, 204, 21))
    draw.text((x + pad_x, y + pad_y - 2), text, font=font, fill=(17, 24, 39))


def draw_overlay(frame: Image.Image, row: dict[str, Any], rank: int) -> None:
    overlay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    width, height = frame.size
    draw.rectangle((0, height - 230, width, height), fill=(0, 0, 0, 160))
    draw.rectangle((0, 0, width, 130), fill=(0, 0, 0, 100))

    title_font = load_font(42, bold=True)
    meta_font = load_font(27)
    small_font = load_font(24)
    badge_font = load_font(32, bold=True)

    source_name = str(row.get("source_name") or row.get("source_slug") or "Source")
    style = str(row.get("style") or "unknown style")
    run_date = str(row.get("run_date") or "unknown date")
    score = score_value(row)

    draw_badge(draw, (54, 42), f"#{rank}", badge_font)
    draw.text((160, 40), source_name, font=title_font, fill=(248, 250, 252))
    draw.text((160, 90), f"Weekly top color grade · {run_date}", font=small_font, fill=(203, 213, 225))

    draw.text((64, height - 178), f"Score {score:.2f}", font=title_font, fill=(248, 250, 252))
    draw.text((64, height - 120), f"Style: {style}", font=meta_font, fill=(226, 232, 240))
    draw.text((64, height - 78), f"Output: {row.get('output_path', '')}", font=small_font, fill=(148, 163, 184))

    frame.alpha_composite(overlay)


def title_card(source_name: str, window: WeekWindow, size: tuple[int, int]) -> Image.Image:
    card = dark_gradient(size).convert("RGBA")
    draw = ImageDraw.Draw(card)
    width, height = size
    title_font = load_font(68, bold=True)
    subtitle_font = load_font(34)
    tiny_font = load_font(26)
    draw_centered(draw, "Daily Color Lottery", height // 2 - 130, width, subtitle_font, (148, 163, 184))
    draw_centered(draw, source_name, height // 2 - 55, width, title_font, (248, 250, 252))
    draw_centered(draw, "Weekly Top 5 Showcase", height // 2 + 45, width, subtitle_font, (250, 204, 21))
    draw_centered(draw, window.label, height // 2 + 98, width, tiny_font, (203, 213, 225))
    return card


def image_frame(row: dict[str, Any], rank: int, root: Path, size: tuple[int, int], progress: float) -> Image.Image:
    path = root / str(row["output_path"])
    with Image.open(path) as src:
        src = ImageOps.exif_transpose(src).convert("RGB")
        direction = -1 if rank % 2 == 0 else 1
        zoom = 1.04 + 0.035 * progress
        pan_x = direction * (-0.28 + 0.56 * progress)
        pan_y = -direction * (-0.14 + 0.28 * progress)
        fitted = fit_cover(src, size, zoom, pan_x, pan_y).convert("RGBA")
    draw_overlay(fitted, row, rank)
    return fitted


def save_frames(
    selected_rows: list[dict[str, Any]],
    root: Path,
    frames_dir: Path,
    source_name: str,
    window: WeekWindow,
    width: int,
    height: int,
    fps: int,
    seconds_per_image: float,
    title_seconds: float,
    crossfade_seconds: float,
    log_lines: list[str],
) -> int:
    ensure_dir(frames_dir)
    size = (width, height)
    frame_index = 0
    title_count = max(1, int(round(title_seconds * fps)))
    image_count = max(1, int(round(seconds_per_image * fps)))
    fade_count = max(0, int(round(crossfade_seconds * fps)))

    previous: Image.Image | None = None
    title = title_card(source_name, window, size)
    for _ in range(title_count):
        title.convert("RGB").save(frames_dir / f"frame_{frame_index:06d}.jpg", quality=90)
        frame_index += 1
    previous = title

    for rank, row in enumerate(selected_rows, start=1):
        current_first = image_frame(row, rank, root, size, 0.0)
        if fade_count and previous is not None:
            for fade_idx in range(1, fade_count + 1):
                alpha = fade_idx / fade_count
                blended = Image.blend(previous.convert("RGBA"), current_first, alpha)
                blended.convert("RGB").save(frames_dir / f"frame_{frame_index:06d}.jpg", quality=90)
                frame_index += 1
        for img_idx in range(image_count):
            progress = img_idx / max(1, image_count - 1)
            frame = image_frame(row, rank, root, size, progress)
            frame.convert("RGB").save(frames_dir / f"frame_{frame_index:06d}.jpg", quality=90)
            frame_index += 1
        previous = image_frame(row, rank, root, size, 1.0)
        log_lines.append(f"frame source={source_name} rank={rank} path={row.get('output_path')} score={score_value(row):.2f}")

    return frame_index


def run_ffmpeg(frames_dir: Path, mp4_path: Path, fps: int, log_lines: list[str]) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg was not found on PATH")

    version = subprocess.run([ffmpeg, "-version"], text=True, capture_output=True, check=False)
    log_lines.append(f"ffmpeg_path={ffmpeg}")
    log_lines.append("ffmpeg_version_stdout:")
    log_lines.append(version.stdout.strip())
    log_lines.append("ffmpeg_version_stderr:")
    log_lines.append(version.stderr.strip())

    cmd = [
        ffmpeg,
        "-y",
        "-framerate",
        str(fps),
        "-i",
        str(frames_dir / "frame_%06d.jpg"),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(mp4_path),
    ]
    log_lines.append("ffmpeg_command=" + json.dumps(cmd))
    result = subprocess.run(cmd, text=True, capture_output=True, check=False)
    log_lines.append(f"ffmpeg_returncode={result.returncode}")
    log_lines.append("ffmpeg_stdout:")
    log_lines.append(result.stdout.strip())
    log_lines.append("ffmpeg_stderr:")
    log_lines.append(result.stderr.strip())
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed with exit code {result.returncode}")


def build_manifest(source_key: str, selected_rows: list[dict[str, Any]], window: WeekWindow, args: argparse.Namespace) -> dict[str, Any]:
    source_name = str(selected_rows[0].get("source_name") or source_key)
    source_slug = str(selected_rows[0].get("source_slug") or slugify(Path(source_key).stem))
    return {
        "type": "daily-color-lottery-weekly-source-showcase",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "week": {
            "earliest": window.earliest.isoformat(),
            "today": window.today.isoformat(),
            "days": args.days,
        },
        "source": {
            "key": source_key,
            "name": source_name,
            "slug": source_slug,
            "path": selected_rows[0].get("source_path"),
            "sha256": selected_rows[0].get("source_sha256"),
        },
        "video": {
            "filename": "weekly-showcase.mp4",
            "width": args.width,
            "height": args.height,
            "fps": args.fps,
            "seconds_per_image": args.seconds_per_image,
            "title_seconds": args.title_seconds,
            "crossfade_seconds": args.crossfade_seconds,
        },
        "outputs": [
            {
                "rank": rank,
                "score": score_value(row),
                "style": row.get("style"),
                "style_description": row.get("style_description"),
                "run_date": row.get("run_date"),
                "run_id": row.get("run_id"),
                "output_path": row.get("output_path"),
                "latest_path": row.get("latest_path"),
                "width": row.get("width"),
                "height": row.get("height"),
                "params": row.get("params"),
                "grain_seed_hex": row.get("grain_seed_hex"),
            }
            for rank, row in enumerate(selected_rows, start=1)
        ],
    }


def generate_html(manifest: dict[str, Any], mp4_path: Path) -> str:
    mp4_b64 = base64.b64encode(mp4_path.read_bytes()).decode("ascii")
    manifest_json = json.dumps(manifest, ensure_ascii=False, indent=2)
    source_name = html.escape(str(manifest["source"]["name"]))
    week = html.escape(f"{manifest['week']['earliest']} → {manifest['week']['today']}")
    cards = []
    for output in manifest["outputs"]:
        params = html.escape(json.dumps(output.get("params") or {}, ensure_ascii=False, sort_keys=True))
        cards.append(
            f"""
            <article class=\"card\">
              <div class=\"rank\">#{output['rank']}</div>
              <div>
                <h3>{html.escape(str(output.get('style') or 'unknown style'))}</h3>
                <p class=\"score\">Score {float(output.get('score') or 0):.2f}</p>
                <p>{html.escape(str(output.get('run_date') or 'unknown date'))} · {html.escape(str(output.get('run_id') or ''))}</p>
                <p><code>{html.escape(str(output.get('output_path') or ''))}</code></p>
                <details><summary>Parameters</summary><pre>{params}</pre></details>
              </div>
            </article>
            """
        )
    safe_manifest_json = manifest_json.replace("</", "<\\/")
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>Weekly Showcase · {source_name}</title>
  <style>
    :root {{ color-scheme: dark; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #0d1117; color: #e5e7eb; }}
    body {{ margin: 0; padding: 32px; background: radial-gradient(circle at top, #1f2937 0, #0d1117 45%, #05070a 100%); }}
    main {{ max-width: 1180px; margin: 0 auto; }}
    header {{ margin-bottom: 28px; }}
    h1 {{ margin: 0 0 8px; font-size: clamp(2rem, 5vw, 4rem); }}
    .muted {{ color: #94a3b8; }}
    video {{ width: 100%; border-radius: 24px; background: #000; box-shadow: 0 22px 70px rgba(0,0,0,.45); }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 18px; margin-top: 28px; }}
    .card {{ display: grid; grid-template-columns: auto 1fr; gap: 16px; padding: 18px; border: 1px solid rgba(148,163,184,.22); border-radius: 20px; background: rgba(15, 23, 42, .72); }}
    .rank {{ display: grid; place-items: center; width: 56px; height: 56px; border-radius: 16px; background: #facc15; color: #111827; font-weight: 800; font-size: 1.25rem; }}
    h2, h3 {{ margin: 0 0 8px; }}
    p {{ margin: 0 0 8px; color: #cbd5e1; }}
    .score {{ color: #f8fafc; font-size: 1.35rem; font-weight: 800; }}
    code, pre {{ white-space: pre-wrap; overflow-wrap: anywhere; color: #bae6fd; }}
    details {{ margin-top: 10px; }}
    script[type=\"application/json\"] {{ display: none; }}
  </style>
</head>
<body>
  <main>
    <header>
      <p class=\"muted\">Daily Color Lottery · Weekly Top 5 Source Showcase</p>
      <h1>{source_name}</h1>
      <p class=\"muted\">{week}</p>
    </header>
    <video controls preload=\"metadata\" src=\"data:video/mp4;base64,{mp4_b64}\"></video>
    <section>
      <h2>Top 5 outputs</h2>
      <div class=\"grid\">
        {''.join(cards)}
      </div>
    </section>
    <script id=\"weekly-showcase-manifest\" type=\"application/json\">{safe_manifest_json}</script>
  </main>
</body>
</html>
"""


def zip_showcase(package_dir: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for filename in ["weekly-showcase.mp4", "weekly-showcase.html", "build.log", "manifest.json"]:
            zf.write(package_dir / filename, f"showcase/{filename}")


def package_source_showcase(
    source_key: str,
    selected_rows: list[dict[str, Any]],
    root: Path,
    dist: Path,
    work_root: Path,
    window: WeekWindow,
    args: argparse.Namespace,
) -> Path:
    source_name = str(selected_rows[0].get("source_name") or source_key)
    source_slug = slugify(str(selected_rows[0].get("source_slug") or Path(source_key).stem or source_key))
    source_hash = hashlib.sha256(source_key.encode("utf-8")).hexdigest()[:8]
    asset_slug = f"{source_slug}-{source_hash}"
    asset_stem = f"daily-color-lottery-week-{window.today.isoformat()}-showcase-{asset_slug}"
    package_dir = work_root / asset_slug / "package"
    frames_dir = work_root / asset_slug / "frames"
    if package_dir.exists():
        shutil.rmtree(package_dir)
    if frames_dir.exists():
        shutil.rmtree(frames_dir)
    ensure_dir(package_dir)

    log_lines = [
        "Daily Color Lottery weekly per-source showcase build log",
        f"source_key={source_key}",
        f"source_name={source_name}",
        f"week={window.label}",
        f"selected_count={len(selected_rows)}",
    ]
    manifest = build_manifest(source_key, selected_rows, window, args)
    manifest_path = package_dir / "manifest.json"
    write_json(manifest_path, manifest)

    frame_count = save_frames(
        selected_rows,
        root,
        frames_dir,
        source_name,
        window,
        args.width,
        args.height,
        args.fps,
        args.seconds_per_image,
        args.title_seconds,
        args.crossfade_seconds,
        log_lines,
    )
    log_lines.append(f"frame_count={frame_count}")

    mp4_path = package_dir / "weekly-showcase.mp4"
    try:
        run_ffmpeg(frames_dir, mp4_path, args.fps, log_lines)
        html_path = package_dir / "weekly-showcase.html"
        html_path.write_text(generate_html(manifest, mp4_path), encoding="utf-8")
        zip_path = dist / f"{asset_stem}.zip"
        log_lines.append(f"mp4_path={mp4_path}")
        log_lines.append(f"html_path={html_path}")
        log_lines.append(f"zip_path={zip_path}")
        (package_dir / "build.log").write_text("\n".join(log_lines) + "\n", encoding="utf-8")
        zip_showcase(package_dir, zip_path)
        return zip_path
    except Exception as exc:
        log_lines.append(f"error={exc!r}")
        (package_dir / "build.log").write_text("\n".join(log_lines) + "\n", encoding="utf-8")
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--logs", default="logs")
    parser.add_argument("--dist", default="dist")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--today", default=None, help="UTC date override in YYYY-MM-DD format, useful for tests")
    parser.add_argument("--max-per-source", type=int, default=5)
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--seconds-per-image", type=float, default=2.0)
    parser.add_argument("--title-seconds", type=float, default=1.5)
    parser.add_argument("--crossfade-seconds", type=float, default=0.4)
    parser.add_argument("--keep-work", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path.cwd()
    dist = root / args.dist
    ensure_dir(dist)
    today = parse_iso_date(args.today) if args.today else None
    if args.today and today is None:
        raise ValueError("--today must be in YYYY-MM-DD format")
    window = make_week_window(args.days, today)
    selected = select_weekly_top_outputs(root / args.logs / "runs.jsonl", root, window, args.max_per_source)
    selected = {source: rows for source, rows in selected.items() if rows}
    if not selected:
        print("No weekly showcase candidates found.")
        return EXIT_NO_FILES

    work_root = dist / "weekly-showcase-work"
    if work_root.exists():
        shutil.rmtree(work_root)
    ensure_dir(work_root)

    created = []
    try:
        for source_key, rows in selected.items():
            created.append(package_source_showcase(source_key, rows, root, dist, work_root, window, args))
    finally:
        if not args.keep_work and work_root.exists():
            shutil.rmtree(work_root)

    for path in created:
        print(path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
