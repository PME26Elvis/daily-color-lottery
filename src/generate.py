from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from src.grading import score_image
from src.image_ops import grade_image, open_rgb
from src.randomness import numpy_seed, random_metadata, sample_ranges
from src.source_tracking import build_inventory, diff_inventory, merge_inventory
from src.utils import (
    append_jsonl,
    date_from_dt,
    ensure_dir,
    iter_source_images,
    load_jsonl,
    read_json,
    rel,
    run_id_from_dt,
    slugify,
    utc_now,
    write_json,
)

ROOT = Path.cwd()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/settings.json")
    parser.add_argument("--sources", default=None)
    parser.add_argument("--output", default=None)
    parser.add_argument("--logs", default=None)
    parser.add_argument("--docs-data", default=None)
    return parser.parse_args()


def load_config(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_jpeg(img, path: Path, quality: int) -> None:
    ensure_dir(path.parent)
    img.save(path, format="JPEG", quality=quality, optimize=True)


def update_leaderboard(existing: list[dict[str, Any]], outputs: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    rows = existing + outputs
    rows = sorted(rows, key=lambda x: float(x.get("score", {}).get("score", 0.0)), reverse=True)
    seen = set()
    unique = []
    for row in rows:
        key = row.get("output_path")
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
        if len(unique) >= limit:
            break
    return unique


def compact_runs(runs: list[dict[str, Any]], limit: int = 365) -> list[dict[str, Any]]:
    return runs[-limit:]


def main() -> int:
    args = parse_args()
    root = ROOT
    config = load_config(root / args.config)
    paths = config["paths"]
    sources_dir = root / (args.sources or paths["sources"])
    output_dir = root / (args.output or paths["output"])
    logs_dir = root / (args.logs or paths["logs"])
    docs_data_dir = root / (args.docs_data or paths["docs_data"])

    ensure_dir(sources_dir)
    ensure_dir(output_dir)
    ensure_dir(logs_dir)
    ensure_dir(docs_data_dir)

    now = utc_now()
    run_id = run_id_from_dt(now)
    run_date = date_from_dt(now)
    run_meta = random_metadata()
    quality = int(config.get("run", {}).get("output_quality", 92))
    styles = config["styles"]
    weights = config.get("scoring", {}).get("weights", {})
    leaderboard_limit = int(config.get("scoring", {}).get("leaderboard_limit", 100))

    previous_inventory_path = logs_dir / "source_inventory.json"
    previous_inventory = read_json(previous_inventory_path, {})
    active_previous = {
        key: value for key, value in previous_inventory.items() if value.get("status") == "active"
    }
    current_inventory = build_inventory(sources_dir, root, now)
    source_events = diff_inventory(active_previous, current_inventory, run_id, now)
    merged_inventory = merge_inventory(previous_inventory, current_inventory, now)
    write_json(previous_inventory_path, merged_inventory)
    for event in source_events:
        append_jsonl(logs_dir / "source_events.jsonl", event)

    source_paths = iter_source_images(sources_dir)
    latest_dir = output_dir / "latest"
    if latest_dir.exists():
        shutil.rmtree(latest_dir)
    ensure_dir(latest_dir)

    all_outputs = []
    errors = []
    for source_path in source_paths:
        source_rel = rel(source_path, root)
        source_slug = slugify(source_path.stem)
        source_latest_dir = latest_dir / source_slug
        source_archive_dir = output_dir / "archive" / run_date / source_slug
        ensure_dir(source_latest_dir)
        ensure_dir(source_archive_dir)

        try:
            original = open_rgb(source_path)
        except Exception as exc:
            errors.append({"source": source_rel, "error": repr(exc)})
            continue

        source_outputs = []
        for index, style in enumerate(styles[: int(config["run"].get("outputs_per_source", 5))], start=1):
            style_name = style["name"]
            params = sample_ranges(style["ranges"])
            seed = numpy_seed()
            try:
                out_img = grade_image(original, params, seed)
                score = score_image(out_img, weights)
                filename = f"{run_id}_{index:02d}_{style_name}.jpg"
                archive_path = source_archive_dir / filename
                latest_path = source_latest_dir / f"{index:02d}_{style_name}.jpg"
                save_jpeg(out_img, archive_path, quality)
                save_jpeg(out_img, latest_path, quality)
                row = {
                    "run_id": run_id,
                    "run_date": run_date,
                    "source_path": source_rel,
                    "source_name": source_path.name,
                    "source_slug": source_slug,
                    "source_sha256": current_inventory.get(source_rel, {}).get("sha256"),
                    "style": style_name,
                    "style_description": style.get("description", ""),
                    "index": index,
                    "params": {k: round(float(v), 6) for k, v in params.items()},
                    "grain_seed_hex": hex(seed),
                    "output_path": rel(archive_path, root),
                    "latest_path": rel(latest_path, root),
                    "score": score,
                    "width": original.width,
                    "height": original.height,
                }
                source_outputs.append(row)
                all_outputs.append(row)
            except Exception as exc:
                errors.append({"source": source_rel, "style": style_name, "error": repr(exc)})
        if source_outputs:
            best = max(source_outputs, key=lambda x: float(x["score"]["score"]))
            for row in source_outputs:
                row["best_for_source_today"] = row["output_path"] == best["output_path"]

    summary = {
        "run_id": run_id,
        "run_date": run_date,
        "created_at": now.isoformat(),
        "random": run_meta,
        "source_count": len(source_paths),
        "active_source_count": len(current_inventory),
        "outputs_generated": len(all_outputs),
        "styles": [style["name"] for style in styles],
        "average_score": round(
            sum(float(o["score"]["score"]) for o in all_outputs) / len(all_outputs), 2
        )
        if all_outputs
        else None,
        "best_output": max(all_outputs, key=lambda x: float(x["score"]["score"])) if all_outputs else None,
        "source_events": source_events,
        "errors": errors,
        "outputs": all_outputs,
    }

    append_jsonl(logs_dir / "runs.jsonl", summary)
    write_json(logs_dir / "latest_run.json", summary)

    runs = compact_runs(load_jsonl(logs_dir / "runs.jsonl"))
    leaderboard_path = logs_dir / "leaderboard.json"
    leaderboard = update_leaderboard(read_json(leaderboard_path, []), all_outputs, leaderboard_limit)
    write_json(leaderboard_path, leaderboard)

    write_json(docs_data_dir / "latest-run.json", summary)
    write_json(docs_data_dir / "runs.json", runs)
    write_json(docs_data_dir / "leaderboard.json", leaderboard)
    write_json(docs_data_dir / "source-inventory.json", merged_inventory)
    write_json(docs_data_dir / "source-events.json", load_jsonl(logs_dir / "source_events.jsonl")[-200:])

    print(f"run_id={run_id}")
    print(f"sources={len(source_paths)} outputs={len(all_outputs)} errors={len(errors)}")
    return 0 if not errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
