from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path
from typing import Any

from src.grading import score_image
from src.image_ops import dominant_palette_hex, grade_image, image_profile, open_rgb
from src.algorithms import generate_candidates, select_diverse_candidates
from src.randomness import numpy_seed, random_metadata
from src.analytics import write_style_analytics
from src.recipes import load_recipe, validate_recipe, write_recipe_catalog
from src.source_tracking import build_inventory, diff_inventory, merge_inventory
from src.utils import (
    append_jsonl,
    date_from_dt,
    ensure_dir,
    iter_source_images,
    load_jsonl,
    read_json,
    resolve_config_path,
    safe_rel,
    downsample_image,
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
    parser.add_argument(
        "--replay-run-log", default=None, help="Replay a run from a run summary JSON file"
    )
    parser.add_argument(
        "--replay-run-id", default=None, help="Replay a run_id from logs/runs.jsonl"
    )
    parser.add_argument(
        "--recipe", default=None, help="Apply a reusable recipe id to all current sources"
    )
    parser.add_argument(
        "--recipe-file",
        default=None,
        help="Recipe catalog JSON path (defaults to logs/recipes.json, then docs/data/recipes.json)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Deterministic seed for local reproducibility",
    )
    return parser.parse_args()


def load_config(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_jpeg(img, path: Path, quality: int) -> None:
    ensure_dir(path.parent)
    img.save(path, format="JPEG", quality=quality, optimize=True)


def update_leaderboard(
    existing: list[dict[str, Any]], outputs: list[dict[str, Any]], limit: int
) -> list[dict[str, Any]]:
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


def load_replay_record(
    logs_dir: Path, replay_run_log: str | None, replay_run_id: str | None
) -> dict[str, Any] | None:
    if replay_run_log and replay_run_id:
        raise ValueError("Use only one of --replay-run-log or --replay-run-id")
    if replay_run_log:
        record_path = Path(replay_run_log)
        if not record_path.is_absolute():
            record_path = ROOT / record_path
        record = read_json(record_path, None)
        if not isinstance(record, dict):
            raise ValueError(f"Replay run log is not a JSON object: {record_path}")
        return record
    if replay_run_id:
        matches = [
            row for row in load_jsonl(logs_dir / "runs.jsonl") if row.get("run_id") == replay_run_id
        ]
        if not matches:
            raise ValueError(f"No run_id found in {logs_dir / 'runs.jsonl'}: {replay_run_id}")
        return matches[-1]
    return None


def replay_outputs(
    *,
    root: Path,
    output_dir: Path,
    logs_dir: Path,
    record: dict[str, Any],
    quality: int,
    weights: dict[str, Any],
    created_at: str,
) -> dict[str, Any]:
    original_run_id = str(record.get("run_id") or "unknown-run")
    replay_root = output_dir / "replay" / slugify(original_run_id)
    if replay_root.exists():
        shutil.rmtree(replay_root)
    ensure_dir(replay_root)

    all_outputs: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    source_paths = sorted(
        {row.get("source_path") for row in record.get("outputs", []) if row.get("source_path")}
    )

    for index, row in enumerate(record.get("outputs", []), start=1):
        source_rel = row.get("source_path")
        style_name = row.get("style")
        params = row.get("params")
        grain_seed_hex = row.get("grain_seed_hex")
        if not source_rel or not style_name or not isinstance(params, dict) or not grain_seed_hex:
            errors.append(
                {
                    "output_index": index,
                    "error": "missing replay source_path, style, params, or grain_seed_hex",
                }
            )
            continue

        source_path = root / source_rel
        source_slug = str(row.get("source_slug") or slugify(source_path.stem))
        try:
            original = open_rgb(source_path)
            seed = int(str(grain_seed_hex), 16)
            out_img = grade_image(original, params, seed)
            score = score_image(out_img, weights)
            output_index = int(row.get("index") or index)
            filename = f"{original_run_id}_{output_index:02d}_{style_name}.jpg"
            output_path = replay_root / source_slug / filename
            save_jpeg(out_img, output_path, quality)
            replay_row = dict(row)
            replay_row.update(
                {
                    "mode": "replay",
                    "replay_of_run_id": original_run_id,
                    "output_path": safe_rel(output_path, root),
                    "latest_path": None,
                    "score": score,
                    "width": original.width,
                    "height": original.height,
                }
            )
            all_outputs.append(replay_row)
        except Exception as exc:
            errors.append({"source": source_rel, "style": style_name, "error": repr(exc)})

    summary = {
        "mode": "replay",
        "run_id": original_run_id,
        "replay_of_run_id": original_run_id,
        "created_at": created_at,
        "source_count": len(source_paths),
        "outputs_generated": len(all_outputs),
        "average_score": round(
            sum(float(o["score"]["score"]) for o in all_outputs) / len(all_outputs), 2
        )
        if all_outputs
        else None,
        "best_output": max(all_outputs, key=lambda x: float(x["score"]["score"]))
        if all_outputs
        else None,
        "errors": errors,
        "outputs": all_outputs,
    }
    append_jsonl(logs_dir / "replay_runs.jsonl", summary)
    write_json(logs_dir / "latest_replay_run.json", summary)
    print(f"mode=replay run_id={original_run_id}")
    print(f"sources={len(source_paths)} outputs={len(all_outputs)} errors={len(errors)}")
    return summary


def generate_recipe_outputs(
    *,
    root: Path,
    sources_dir: Path,
    output_dir: Path,
    logs_dir: Path,
    recipe: dict[str, Any],
    run_id: str,
    run_date: str,
    quality: int,
    weights: dict[str, Any],
    created_at: str,
    regenerate_grain: bool = True,
) -> dict[str, Any]:
    recipe = validate_recipe(recipe)
    latest_dir = output_dir / "latest"
    if latest_dir.exists():
        shutil.rmtree(latest_dir)
    ensure_dir(latest_dir)
    recipe_slug = slugify(str(recipe.get("recipe_id") or "recipe"))
    params = recipe.get("params") or {}
    style_name = str(recipe.get("style") or "recipe")
    source_seed_hex = (recipe.get("grain_seed_policy") or {}).get("source_seed_hex") or "0x0"
    all_outputs: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    source_paths = iter_source_images(sources_dir)
    for index, source_path in enumerate(source_paths, start=1):
        source_rel = safe_rel(source_path, root)
        source_slug = slugify(source_path.stem)
        source_latest_dir = latest_dir / source_slug
        source_archive_dir = output_dir / "recipes" / run_date / recipe_slug / source_slug
        ensure_dir(source_latest_dir)
        ensure_dir(source_archive_dir)
        try:
            original = open_rgb(source_path)
            source_profile = image_profile(original)
            seed = numpy_seed() if regenerate_grain else int(str(source_seed_hex), 16)
            out_img = grade_image(original, params, seed)
            score = score_image(out_img, weights)
            palette = dominant_palette_hex(out_img)
            filename = f"{run_id}_{index:02d}_{style_name}.jpg"
            archive_path = source_archive_dir / filename
            latest_path = source_latest_dir / f"recipe_{recipe_slug}_{style_name}.jpg"
            save_jpeg(out_img, archive_path, quality)
            save_jpeg(out_img, latest_path, quality)
            row = {
                "mode": "recipe",
                "recipe_id": recipe.get("recipe_id"),
                "recipe_name": recipe.get("name"),
                "run_id": run_id,
                "run_date": run_date,
                "source_path": source_rel,
                "source_name": source_path.name,
                "source_slug": source_slug,
                "style": style_name,
                "style_description": f"Applied recipe {recipe.get('name') or recipe.get('recipe_id')}",
                "algorithm": recipe.get("algorithm") or "style_range",
                "source_profile": source_profile,
                "source_profile_bucket": source_profile.get("profile_bucket"),
                "source_profile_tags": source_profile.get("profile_tags", []),
                "selection_reason": "Applied reusable recipe to current source image.",
                "candidate_rank": index,
                "index": index,
                "params": params,
                "grain_seed_hex": hex(seed),
                "grain_seed_policy": "regenerate" if regenerate_grain else "fixed",
                "output_path": safe_rel(archive_path, root),
                "latest_path": safe_rel(latest_path, root),
                "score": score,
                "palette": palette,
                "width": original.width,
                "height": original.height,
            }
            all_outputs.append(row)
        except Exception as exc:
            errors.append(
                {"source": source_rel, "recipe_id": recipe.get("recipe_id"), "error": repr(exc)}
            )
    if all_outputs:
        best = max(all_outputs, key=lambda x: float(x["score"]["score"]))
        for row in all_outputs:
            row["best_for_source_today"] = row["output_path"] == best["output_path"]
    summary = {
        "mode": "recipe",
        "recipe_id": recipe.get("recipe_id"),
        "recipe": recipe,
        "run_id": run_id,
        "run_date": run_date,
        "created_at": created_at,
        "source_count": len(source_paths),
        "outputs_generated": len(all_outputs),
        "average_score": round(
            sum(float(o["score"]["score"]) for o in all_outputs) / len(all_outputs), 2
        )
        if all_outputs
        else None,
        "best_output": max(all_outputs, key=lambda x: float(x["score"]["score"]))
        if all_outputs
        else None,
        "errors": errors,
        "outputs": all_outputs,
    }
    append_jsonl(logs_dir / "runs.jsonl", summary)
    write_json(logs_dir / "latest_run.json", summary)
    print(f"mode=recipe recipe_id={recipe.get('recipe_id')} run_id={run_id}")
    print(f"sources={len(source_paths)} outputs={len(all_outputs)} errors={len(errors)}")
    return summary


def main() -> int:
    args = parse_args()
    root = ROOT
    config = load_config(root / args.config)
    paths = config["paths"]
    sources_dir = resolve_config_path(args.sources, paths["sources"], root)
    output_dir = resolve_config_path(args.output, paths["output"], root)
    logs_dir = resolve_config_path(args.logs, paths["logs"], root)
    docs_data_dir = resolve_config_path(args.docs_data, paths["docs_data"], root)

    ensure_dir(sources_dir)
    ensure_dir(output_dir)
    ensure_dir(logs_dir)
    ensure_dir(docs_data_dir)

    now = utc_now()
    run_id = run_id_from_dt(now)
    run_date = date_from_dt(now)
    quality = int(config.get("run", {}).get("output_quality", 92))
    styles = config["styles"]
    weights = config.get("scoring", {}).get("weights", {})
    leaderboard_limit = int(config.get("scoring", {}).get("leaderboard_limit", 100))

    replay_record = load_replay_record(logs_dir, args.replay_run_log, args.replay_run_id)
    if replay_record is not None:
        replay_outputs(
            root=root,
            output_dir=output_dir,
            logs_dir=logs_dir,
            record=replay_record,
            quality=quality,
            weights=weights,
            created_at=now.isoformat(),
        )
        return 0

    if args.recipe:
        recipe_path = Path(args.recipe_file) if args.recipe_file else logs_dir / "recipes.json"
        if not recipe_path.is_absolute():
            recipe_path = root / recipe_path
        if not recipe_path.exists() and not args.recipe_file:
            recipe_path = docs_data_dir / "recipes.json"
        recipe = load_recipe(args.recipe, recipe_path)
        summary = generate_recipe_outputs(
            root=root,
            sources_dir=sources_dir,
            output_dir=output_dir,
            logs_dir=logs_dir,
            recipe=recipe,
            run_id=run_id,
            run_date=run_date,
            quality=quality,
            weights=weights,
            created_at=now.isoformat(),
            regenerate_grain=bool(config.get("recipes", {}).get("regenerate_grain", True)),
        )
        runs = compact_runs(load_jsonl(logs_dir / "runs.jsonl"))
        leaderboard_path = logs_dir / "leaderboard.json"
        leaderboard = update_leaderboard(
            read_json(leaderboard_path, []), summary["outputs"], leaderboard_limit
        )
        write_json(leaderboard_path, leaderboard)
        write_json(docs_data_dir / "latest-run.json", summary)
        write_json(docs_data_dir / "runs.json", runs)
        write_json(docs_data_dir / "leaderboard.json", leaderboard)
        write_style_analytics(logs_dir, docs_data_dir)
        return 0

    run_seed = args.seed if args.seed is not None else config.get("run", {}).get("seed")
    run_seed = int(run_seed) if run_seed is not None else None
    run_meta = random_metadata(run_seed)
    timings = {
        "source_profile_seconds": 0.0,
        "candidate_render_score_seconds": 0.0,
        "final_render_save_seconds": 0.0,
    }
    total_started = time.perf_counter()
    run_cfg = config.get("run", {})
    max_working_dimension = int(run_cfg.get("max_working_dimension", 0) or 0)
    profile_dimension = int(run_cfg.get("candidate_preview_dimension", max_working_dimension) or 0)
    scoring_dimension = int(run_cfg.get("candidate_scoring_dimension", max_working_dimension) or 0)
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
        source_rel = safe_rel(source_path, root)
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

        profile_started = time.perf_counter()
        profile_img = downsample_image(original, profile_dimension)
        source_profile = image_profile(profile_img)
        timings["source_profile_seconds"] += time.perf_counter() - profile_started
        scoring_img = downsample_image(original, scoring_dimension)
        candidate_pool = []
        algorithm_cfg = config.get("algorithms", {})
        for candidate in generate_candidates(styles, source_profile, algorithm_cfg, seed=run_seed):
            try:
                score_started = time.perf_counter()
                out_img = grade_image(
                    scoring_img, candidate["params"], int(candidate["grain_seed"])
                )
                score = score_image(out_img, weights)
                palette = dominant_palette_hex(out_img)
                timings["candidate_render_score_seconds"] += time.perf_counter() - score_started
                candidate.update({"score": score, "palette": palette})
                candidate_pool.append(candidate)
            except Exception as exc:
                errors.append(
                    {
                        "source": source_rel,
                        "style": candidate.get("style"),
                        "algorithm": candidate.get("algorithm"),
                        "error": repr(exc),
                    }
                )

        final_count = int(config["run"].get("outputs_per_source", 5))
        selected_candidates = select_diverse_candidates(candidate_pool, final_count)

        source_outputs = []
        for index, candidate in enumerate(selected_candidates, start=1):
            style_name = candidate["style"]
            params = candidate["params"]
            seed = int(candidate["grain_seed"])
            try:
                final_started = time.perf_counter()
                out_img = grade_image(original, params, seed)
                score = candidate.get("score") or score_image(out_img, weights)
                palette = candidate.get("palette") or dominant_palette_hex(out_img)
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
                    "style_description": candidate.get("explanation", ""),
                    "algorithm": candidate.get("algorithm"),
                    "algorithm_description": candidate.get("algorithm_description", ""),
                    "source_profile": source_profile,
                    "source_profile_bucket": source_profile.get("profile_bucket"),
                    "source_profile_tags": source_profile.get("profile_tags", []),
                    "selection_reason": candidate.get(
                        "selection_reason", "Selected by quality/diversity ranking"
                    ),
                    "candidate_rank": index,
                    "diversity_score": candidate.get("diversity_score", 0),
                    "overall_selection_score": candidate.get(
                        "overall_selection_score", score.get("score", 0)
                    ),
                    "badges": list(
                        dict.fromkeys(
                            candidate.get("tags", []) + (["Best for source"] if index == 1 else [])
                        )
                    ),
                    "index": index,
                    "params": {
                        k: round(float(v), 6) if isinstance(v, (int, float)) else v
                        for k, v in params.items()
                    },
                    "grain_seed_hex": hex(seed),
                    "output_path": safe_rel(archive_path, root),
                    "latest_path": safe_rel(latest_path, root),
                    "score": score,
                    "palette": palette,
                    "width": original.width,
                    "height": original.height,
                }
                timings["final_render_save_seconds"] += time.perf_counter() - final_started
                source_outputs.append(row)
                all_outputs.append(row)
            except Exception as exc:
                errors.append(
                    {
                        "source": source_rel,
                        "style": style_name,
                        "algorithm": candidate.get("algorithm"),
                        "error": repr(exc),
                    }
                )
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
        "algorithms": config.get("algorithms", {}),
        "source_profiles": {
            o["source_path"]: o.get("source_profile")
            for o in all_outputs
            if o.get("source_profile")
        },
        "average_score": round(
            sum(float(o["score"]["score"]) for o in all_outputs) / len(all_outputs), 2
        )
        if all_outputs
        else None,
        "best_output": max(all_outputs, key=lambda x: float(x["score"]["score"]))
        if all_outputs
        else None,
        "source_events": source_events,
        "errors": errors,
        "outputs": all_outputs,
    }

    timings["total_run_seconds"] = time.perf_counter() - total_started
    summary["timings"] = {key: round(value, 4) for key, value in timings.items()}

    append_jsonl(logs_dir / "runs.jsonl", summary)
    write_json(logs_dir / "latest_run.json", summary)

    runs = compact_runs(load_jsonl(logs_dir / "runs.jsonl"))
    leaderboard_path = logs_dir / "leaderboard.json"
    leaderboard = update_leaderboard(
        read_json(leaderboard_path, []), all_outputs, leaderboard_limit
    )
    write_json(leaderboard_path, leaderboard)

    write_json(docs_data_dir / "latest-run.json", summary)
    write_json(docs_data_dir / "runs.json", runs)
    write_json(docs_data_dir / "leaderboard.json", leaderboard)
    write_json(docs_data_dir / "source-inventory.json", merged_inventory)
    write_json(
        docs_data_dir / "source-events.json", load_jsonl(logs_dir / "source_events.jsonl")[-200:]
    )
    write_recipe_catalog(logs_dir, docs_data_dir, summary)
    write_style_analytics(logs_dir, docs_data_dir)

    print(f"run_id={run_id}")
    print(f"sources={len(source_paths)} outputs={len(all_outputs)} errors={len(errors)}")
    return 0 if not errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
