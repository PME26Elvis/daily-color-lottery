import json
from pathlib import Path

from src.analytics import build_algorithm_analytics, build_source_analytics, build_style_analytics
from src.recipes import build_recipe_analytics, validate_recipe
from src.utils import safe_rel


def test_docs_data_json_shapes_are_dashboard_safe():
    root = Path(__file__).resolve().parents[1]
    latest = json.loads((root / "docs/data/latest-run.json").read_text())
    assert isinstance(latest.get("outputs", []), list)
    for output in latest.get("outputs", []):
        assert isinstance(output.get("output_path"), str)
        assert isinstance(output.get("score", {}), dict)
        assert isinstance(output.get("palette", []), list)

    for filename, key in [
        ("algorithm-analytics.json", "algorithms"),
        ("style-analytics.json", "styles"),
        ("source-analytics.json", "sources"),
        ("recipes.json", None),
    ]:
        payload = json.loads((root / "docs/data" / filename).read_text())
        if key:
            assert isinstance(payload.get(key), list)
        else:
            assert isinstance(payload, list)


def test_backward_compatible_analytics_with_sparse_old_rows():
    old_output = {
        "run_id": "old",
        "run_date": "2026-01-01",
        "source_path": "sources/old.png",
        "source_name": "old.png",
        "style": "legacy",
        "score": {"score": 75},
        "output_path": "output/old.jpg",
    }
    runs = [{"run_id": "old", "run_date": "2026-01-01", "outputs": [old_output]}]

    assert build_algorithm_analytics(runs)["algorithms"][0]["algorithm"] == "style_range"
    assert build_algorithm_analytics(runs)["profile_buckets"][0]["profile_bucket"] == "unknown"
    assert build_style_analytics(runs)["styles"][0]["style"] == "legacy"
    assert build_source_analytics(runs)["sources"][0]["source_path"] == "sources/old.png"
    assert build_recipe_analytics(runs)["recipe_count"] == 0


def test_safe_rel_is_repo_relative_or_deterministic_external(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    local = root / "sources" / "a.png"
    local.parent.mkdir()
    local.write_bytes(b"x")
    external = tmp_path / "external" / "a.png"
    external.parent.mkdir()
    external.write_bytes(b"x")

    assert safe_rel(local, root) == "sources/a.png"
    first = safe_rel(external, root)
    second = safe_rel(external, root)
    assert first == second
    assert first.startswith("external/")
    assert first.endswith("/a.png")


def test_recipe_validation_rejects_invalid_payloads():
    for payload in [
        {},
        {"recipe_id": "x", "style": "warm"},
        {"recipe_id": "x", "params": {}, "style": ""},
        {"recipe_id": "x", "params": {}, "style": "warm", "grain_seed_policy": "fixed"},
        {"recipe_id": "x", "params": {}, "style": "warm", "grain_seed_policy": {"mode": "fixed"}},
    ]:
        try:
            validate_recipe(payload)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Expected invalid recipe: {payload}")
