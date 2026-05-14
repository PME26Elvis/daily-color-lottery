from pathlib import Path

from PIL import Image

from src.grading import score_image
from src.image_ops import grade_image


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


def test_score_image_range():
    img = Image.new("RGB", (32, 32), (128, 128, 128))
    score = score_image(img)
    assert 0 <= score["score"] <= 100


def test_project_has_required_dirs():
    root = Path(__file__).resolve().parents[1]
    assert (root / "sources").exists()
    assert (root / "docs").exists()
    assert (root / "config" / "settings.json").exists()
