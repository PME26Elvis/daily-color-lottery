from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.utils import read_json, write_json


def _score_value(row: dict[str, Any]) -> float:
    score = row.get("score")
    if isinstance(score, dict):
        score = score.get("score")
    try:
        return float(score)
    except (TypeError, ValueError):
        return 0.0


def profile_bucket(row: dict[str, Any]) -> str:
    return str(
        row.get("source_profile_bucket")
        or (row.get("source_profile") or {}).get("profile_bucket")
        or "unknown"
    )


def canonical_params(params: dict[str, Any] | None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in sorted((params or {}).items()):
        if isinstance(value, float):
            out[key] = round(value, 6)
        elif isinstance(value, int):
            out[key] = value
        else:
            out[key] = value
    return out


def stable_recipe_id(
    params: dict[str, Any] | None,
    style: str | None,
    algorithm: str | None,
    source_profile_bucket: str | None,
) -> str:
    payload = {
        "algorithm": algorithm or "style_range",
        "params": canonical_params(params),
        "source_profile_bucket": source_profile_bucket or "unknown",
        "style": style or "unknown",
    }
    digest = hashlib.sha256(repr(payload).encode("utf-8")).hexdigest()[:16]
    return f"recipe-{digest}"


def infer_tags(row: dict[str, Any]) -> list[str]:
    params = row.get("params") or {}
    style = str(row.get("style") or "").replace("_", " ").lower()
    alg = str(row.get("algorithm") or "style_range").lower()
    bucket = profile_bucket(row).lower()
    palette = row.get("palette") or []
    tags: list[str] = []
    text = f"{style} {alg} {bucket}"
    if "cinematic" in text or "teal" in text or "orange" in text:
        tags.append("cinematic")
    if "clean" in text or float(params.get("grain", 0) or 0) <= 0.012:
        tags.append("clean")
    if "mono" in text or float(params.get("saturation", 1) or 1) <= 0.08:
        tags.append("monochrome")
    if float(params.get("contrast", 1) or 1) >= 1.18:
        tags.append("high contrast")
    if float(params.get("saturation", 1) or 1) <= 0.85 or float(params.get("fade", 0) or 0) >= 0.08:
        tags.append("muted")
    if float(params.get("temperature", 0) or 0) > 0.04 or "warm" in text:
        tags.append("warm")
    if float(params.get("temperature", 0) or 0) < -0.04 or "cool" in text or "blue" in text:
        tags.append("cool")
    if "low" in bucket or float(params.get("shadows", 0) or 0) > 0.03:
        tags.append("low-light friendly")
    if "color" in bucket or len(palette) >= 4 or "palette" in alg:
        tags.append("colorful-source friendly")
    return list(dict.fromkeys(tags))


def recipe_from_output(row: dict[str, Any], created_at: str | None = None) -> dict[str, Any]:
    bucket = profile_bucket(row)
    rid = stable_recipe_id(row.get("params"), row.get("style"), row.get("algorithm"), bucket)
    score = row.get("score") if isinstance(row.get("score"), dict) else {"score": _score_value(row)}
    return {
        "recipe_id": rid,
        "name": f"{str(row.get('style') or 'Color recipe').replace('_', ' ').title()} · {bucket}",
        "source_output_path": row.get("output_path"),
        "source_run_id": row.get("run_id"),
        "algorithm": row.get("algorithm") or "style_range",
        "style": row.get("style") or "unknown",
        "params": canonical_params(row.get("params")),
        "grain_seed_policy": {"mode": "regenerate", "source_seed_hex": row.get("grain_seed_hex")},
        "source_profile": row.get("source_profile")
        or {"profile_bucket": bucket, "profile_tags": row.get("source_profile_tags", [])},
        "source_profile_bucket": bucket,
        "score_summary": {"score": round(_score_value(row), 2), "components": score},
        "palette": row.get("palette") or [],
        "tags": infer_tags(row),
        "created_date": (created_at or datetime.now(timezone.utc).isoformat())[:10],
        "replay_command": f"python -m src.generate --recipe {rid}",
    }


def promote_recipes_from_run(
    summary: dict[str, Any],
    existing: list[dict[str, Any]] | None = None,
    created_at: str | None = None,
) -> list[dict[str, Any]]:
    outputs = [o for o in summary.get("outputs", []) if isinstance(o, dict)]
    picks: list[dict[str, Any]] = []
    if summary.get("best_output"):
        picks.append(summary["best_output"])
    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_algorithm: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_bucket: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in outputs:
        by_source[str(row.get("source_path") or row.get("source_name") or "unknown")].append(row)
        by_algorithm[str(row.get("algorithm") or "style_range")].append(row)
        by_bucket[profile_bucket(row)].append(row)
    for group in list(by_source.values()) + list(by_algorithm.values()) + list(by_bucket.values()):
        picks.append(max(group, key=_score_value))
    if outputs:
        picks.append(max(outputs, key=lambda r: float(r.get("diversity_score") or 0)))
    recipes = {
        r.get("recipe_id"): r
        for r in (existing or [])
        if isinstance(r, dict) and r.get("recipe_id")
    }
    for row in picks:
        recipe = recipe_from_output(row, created_at=created_at or summary.get("created_at"))
        recipes.setdefault(recipe["recipe_id"], recipe)
    return sorted(
        recipes.values(),
        key=lambda r: (
            float((r.get("score_summary") or {}).get("score") or 0),
            r.get("created_date") or "",
        ),
        reverse=True,
    )


def write_recipe_catalog(
    logs_dir: Path, docs_data_dir: Path, summary: dict[str, Any]
) -> list[dict[str, Any]]:
    existing = read_json(logs_dir / "recipes.json", [])
    recipes = promote_recipes_from_run(summary, existing if isinstance(existing, list) else [])
    write_json(logs_dir / "recipes.json", recipes)
    write_json(docs_data_dir / "recipes.json", recipes)
    return recipes


def validate_recipe(recipe: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(recipe, dict):
        raise ValueError("Recipe payload must be a JSON object")
    recipe_id = recipe.get("recipe_id")
    if not isinstance(recipe_id, str) or not recipe_id.strip():
        raise ValueError("Recipe payload requires a non-empty recipe_id")
    params = recipe.get("params")
    if not isinstance(params, dict):
        raise ValueError(f"Recipe {recipe_id} requires a params object")
    style = recipe.get("style")
    if not isinstance(style, str) or not style.strip():
        raise ValueError(f"Recipe {recipe_id} requires a non-empty style string")
    grain_policy = recipe.get("grain_seed_policy", {"mode": "regenerate"})
    if not isinstance(grain_policy, dict):
        raise ValueError(f"Recipe {recipe_id} grain_seed_policy must be an object")
    mode = grain_policy.get("mode", "regenerate")
    if mode not in {"regenerate", "fixed"}:
        raise ValueError(f"Recipe {recipe_id} grain_seed_policy.mode must be regenerate or fixed")
    seed = grain_policy.get("source_seed_hex")
    if mode == "fixed" and not isinstance(seed, str):
        raise ValueError(f"Recipe {recipe_id} fixed grain policy requires source_seed_hex")
    return recipe


def load_recipe(recipe_id: str, recipe_file: Path) -> dict[str, Any]:
    payload = read_json(recipe_file, [])
    recipes = (
        payload
        if isinstance(payload, list)
        else payload.get("recipes", [])
        if isinstance(payload, dict)
        else []
    )
    for recipe in recipes:
        if isinstance(recipe, dict) and recipe.get("recipe_id") == recipe_id:
            return validate_recipe(recipe)
    raise ValueError(f"Recipe id not found in {recipe_file}: {recipe_id}")


def build_recipe_analytics(runs: list[dict[str, Any]]) -> dict[str, Any]:
    by_recipe: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for run in runs:
        for output in run.get("outputs") or []:
            rid = output.get("recipe_id") or run.get("recipe_id")
            if rid:
                by_recipe[str(rid)].append(output)
    rows = []
    for rid, items in by_recipe.items():
        scores = [_score_value(i) for i in items]
        buckets = [profile_bucket(i) for i in items]
        best_bucket = max(set(buckets), key=buckets.count) if buckets else "unknown"
        rows.append(
            {
                "recipe_id": rid,
                "usage_count": len(items),
                "average_score_when_reused": round(sum(scores) / len(scores), 2)
                if scores
                else None,
                "best_source_profile_match": best_bucket,
                "recipe_drift": len(set(buckets)),
            }
        )
    rows.sort(key=lambda r: (r["usage_count"], r["average_score_when_reused"] or 0), reverse=True)
    return {"recipe_count": len(rows), "recipes": rows}
