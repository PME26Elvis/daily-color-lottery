from pathlib import Path

from PIL import Image

from src.generate import generate_recipe_outputs
from src.recipes import promote_recipes_from_run, stable_recipe_id
from src.utils import read_json


def sample_output(path="out/a.jpg", score=91, algorithm="palette_cinematic", bucket="colorful"):
    return {
        "run_id": "run-1",
        "run_date": "2026-07-03",
        "output_path": path,
        "source_path": "sources/a.png",
        "source_name": "a.png",
        "style": "teal_orange_split",
        "algorithm": algorithm,
        "params": {"contrast": 1.2, "saturation": 1.05, "temperature": 0.06, "grain": 0.01},
        "grain_seed_hex": "0x7b",
        "source_profile_bucket": bucket,
        "source_profile": {"profile_bucket": bucket, "profile_tags": [bucket]},
        "score": {"score": score},
        "palette": ["#112233", "#DDAA66", "#336699", "#FFFFFF"],
        "diversity_score": 50,
        "best_for_source_today": True,
    }


def test_recipe_id_stability_ignores_param_order():
    a = stable_recipe_id({"contrast": 1.2, "grain": 0.01}, "warm", "style_range", "low-light")
    b = stable_recipe_id({"grain": 0.01, "contrast": 1.2}, "warm", "style_range", "low-light")
    c = stable_recipe_id({"grain": 0.01, "contrast": 1.2}, "warm", "style_range", "colorful")
    assert a == b
    assert a != c


def test_recipe_promotion_and_deduplication_from_synthetic_run():
    first = sample_output("out/a.jpg", 95, "palette_cinematic", "colorful")
    duplicate = dict(first)
    duplicate["output_path"] = "out/duplicate.jpg"
    other = sample_output("out/b.jpg", 88, "monochrome_editorial", "low-light")
    other["source_path"] = "sources/b.png"
    summary = {"created_at": "2026-07-03T00:00:00+00:00", "best_output": first, "outputs": [first, duplicate, other]}

    recipes = promote_recipes_from_run(summary)
    recipe_ids = [recipe["recipe_id"] for recipe in recipes]

    assert len(recipe_ids) == len(set(recipe_ids))
    assert any("cinematic" in recipe["tags"] for recipe in recipes)
    assert any(recipe["algorithm"] == "monochrome_editorial" for recipe in recipes)


def test_recipe_application_mode_with_tiny_fixture_image(tmp_path):
    sources = tmp_path / "sources"
    sources.mkdir()
    Image.new("RGB", (8, 8), (120, 80, 40)).save(sources / "tiny.png")
    recipe = promote_recipes_from_run({"best_output": sample_output(), "outputs": [sample_output()]})[0]

    summary = generate_recipe_outputs(
        root=tmp_path,
        sources_dir=sources,
        output_dir=tmp_path / "output",
        logs_dir=tmp_path / "logs",
        recipe=recipe,
        run_id="recipe-run",
        run_date="2026-07-03",
        quality=90,
        weights={},
        created_at="2026-07-03T00:00:00+00:00",
        regenerate_grain=False,
    )

    assert summary["mode"] == "recipe"
    assert summary["outputs_generated"] == 1
    assert summary["outputs"][0]["recipe_id"] == recipe["recipe_id"]
    assert summary["outputs"][0]["params"] == recipe["params"]
    assert Path(tmp_path / summary["outputs"][0]["output_path"]).exists()
    assert read_json(tmp_path / "logs" / "latest_run.json", {})["mode"] == "recipe"


def test_old_run_rows_without_algorithm_metadata_promote_with_fallbacks():
    old = sample_output()
    old.pop("algorithm")
    old.pop("source_profile_bucket")
    old.pop("source_profile")
    recipes = promote_recipes_from_run({"best_output": old, "outputs": [old]})
    assert recipes[0]["algorithm"] == "style_range"
    assert recipes[0]["source_profile_bucket"] == "unknown"
