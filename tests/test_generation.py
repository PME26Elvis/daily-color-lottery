from pathlib import Path

from PIL import Image

from src.generate import load_replay_record, replay_outputs
from src.grading import score_image
from src.image_ops import dominant_palette_hex, grade_image, grade_image_with_algorithm
from src.utils import append_jsonl, read_json


def test_grade_image_preserves_size():
    img = Image.new("RGB", (64, 48), (120, 80, 40))
    params = {
        "exposure": 0.1,
        "brightness": 0.01,
        "contrast": 1.1,
        "saturation": 1.05,
        "vibrance": 0.1,
        "temperature": 0.05,
        "tint": 0.0,
        "shadows": 0.01,
        "highlights": -0.02,
        "gamma": 1.0,
        "fade": 0.01,
        "vignette": 0.05,
        "grain": 0.0,
    }
    out = grade_image(img, params, grain_seed=123)
    assert out.size == img.size


def test_grade_image_with_algorithm_defaults_to_classic():
    img = Image.new("RGB", (16, 16), (120, 80, 40))
    params = {"contrast": 1.1, "saturation": 1.05, "grain": 0.0}

    default = grade_image(img, params, grain_seed=123)
    explicit = grade_image_with_algorithm(img, params, grain_seed=123, algorithm="classic")

    assert default.tobytes() == explicit.tobytes()


def test_grade_image_with_algorithm_rejects_unknown_algorithm():
    img = Image.new("RGB", (16, 16), (120, 80, 40))

    try:
        grade_image_with_algorithm(img, {}, grain_seed=123, algorithm="unknown")
    except ValueError as exc:
        assert "Unknown grading algorithm 'unknown'" in str(exc)
        assert "classic" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unknown grading algorithm")


def test_score_image_range():
    img = Image.new("RGB", (32, 32), (128, 128, 128))
    score = score_image(img)
    assert 0 <= score["score"] <= 100


def test_score_image_returns_stable_component_keys():
    img = Image.new("RGB", (32, 32), (128, 128, 128))
    score = score_image(img)
    expected_keys = {
        "score",
        "contrast",
        "exposure_balance",
        "saturation_balance",
        "detail",
    }
    assert expected_keys <= score.keys()
    for key in expected_keys:
        assert 0 <= score[key] <= 100


def test_project_has_required_dirs():
    root = Path(__file__).resolve().parents[1]
    assert (root / "sources").exists()
    assert (root / "docs").exists()
    assert (root / "config" / "settings.json").exists()


def test_replay_outputs_use_replay_metadata_and_paths(tmp_path):
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    source_path = source_dir / "sample.png"
    Image.new("RGB", (8, 8), (120, 80, 40)).save(source_path)

    record = {
        "run_id": "2026-07-02T00-00-00Z",
        "outputs": [
            {
                "run_id": "2026-07-02T00-00-00Z",
                "source_path": "sources/sample.png",
                "source_name": "sample.png",
                "source_slug": "sample",
                "style": "fixed_style",
                "style_description": "Fixed replay style.",
                "index": 1,
                "params": {
                    "exposure": 0.0,
                    "brightness": 0.0,
                    "contrast": 1.0,
                    "saturation": 1.0,
                    "vibrance": 0.0,
                    "temperature": 0.0,
                    "tint": 0.0,
                    "shadows": 0.0,
                    "highlights": 0.0,
                    "gamma": 1.0,
                    "fade": 0.0,
                    "vignette": 0.0,
                    "grain": 0.0,
                },
                "grain_seed_hex": "0x7b",
                "score": {"score": 50.0},
            }
        ],
    }

    summary = replay_outputs(
        root=tmp_path,
        output_dir=tmp_path / "output",
        logs_dir=tmp_path / "logs",
        record=record,
        quality=90,
        weights={},
        created_at="2026-07-02T00:00:00+00:00",
    )

    assert summary["mode"] == "replay"
    assert summary["replay_of_run_id"] == "2026-07-02T00-00-00Z"
    assert summary["outputs_generated"] == 1
    output = summary["outputs"][0]
    assert output["mode"] == "replay"
    assert output["grain_seed_hex"] == "0x7b"
    assert output["algorithm"] == "classic"
    assert output["params"] == record["outputs"][0]["params"]
    assert output["latest_path"] is None
    assert output["output_path"] == (
        "output/replay/2026-07-02t00-00-00z/sample/"
        "2026-07-02T00-00-00Z_01_fixed_style.jpg"
    )
    assert (tmp_path / output["output_path"]).exists()
    assert read_json(tmp_path / "logs" / "latest_replay_run.json", {})["mode"] == "replay"


def test_load_replay_record_by_run_id(tmp_path):
    logs_dir = tmp_path / "logs"
    append_jsonl(logs_dir / "runs.jsonl", {"run_id": "first", "outputs": []})
    append_jsonl(logs_dir / "runs.jsonl", {"run_id": "wanted", "outputs": [{"style": "a"}]})

    record = load_replay_record(logs_dir, None, "wanted")

    assert record == {"run_id": "wanted", "outputs": [{"style": "a"}]}
def test_dominant_palette_hex_shape_and_format():
    img = Image.new("RGB", (20, 20), (255, 0, 0))
    for x in range(10, 20):
        for y in range(20):
            img.putpixel((x, y), (0, 128, 255))

    palette = dominant_palette_hex(img)

    assert len(palette) == 2
    assert all(isinstance(color, str) for color in palette)
    assert all(len(color) == 7 for color in palette)
    assert all(color.startswith("#") for color in palette)
    assert all(set(color[1:]) <= set("0123456789ABCDEF") for color in palette)


def test_dominant_palette_hex_limits_to_five_colors():
    img = Image.new("RGB", (50, 10))
    colors = [
        (255, 0, 0),
        (0, 255, 0),
        (0, 0, 255),
        (255, 255, 0),
        (255, 0, 255),
        (0, 255, 255),
    ]
    for index, color in enumerate(colors):
        for x in range(index * 8, min((index + 1) * 8, 50)):
            for y in range(10):
                img.putpixel((x, y), color)

    palette = dominant_palette_hex(img)

    assert len(palette) == 5
    assert all(color.startswith("#") and len(color) == 7 for color in palette)
