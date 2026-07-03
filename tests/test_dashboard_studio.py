import json
from pathlib import Path


def test_latest_run_fixture_supports_static_experiment_studio():
    root = Path(__file__).resolve().parents[1]
    latest = json.loads((root / "docs" / "data" / "latest-run.json").read_text())
    outputs = latest.get("outputs", [])

    assert latest.get("run_id")
    assert outputs, "experiment studio needs at least one latest output fixture"

    for row in outputs:
        assert row.get("source_path")
        assert row.get("output_path") or row.get("latest_path")
        assert row.get("style")
        assert isinstance(row.get("params"), dict)
        assert isinstance(row.get("score"), dict)
        assert isinstance(row["score"].get("score"), (int, float))


def test_dashboard_declares_experiment_studio_static_hooks():
    root = Path(__file__).resolve().parents[1]
    index = (root / "docs" / "index.html").read_text()
    app = (root / "docs" / "app.js").read_text()

    assert 'id="experiment-studio"' in index
    assert 'id="experiment-studio-root"' in index
    assert "localStorage" in app
    assert "#studio?" in app
    assert "comparison-manifest.json" in app
    assert "python -m src.generate --replay-run-id" in app
