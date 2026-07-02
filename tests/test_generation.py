from pathlib import Path

from PIL import Image

from src.grading import score_image
from src.image_ops import dominant_palette_hex, grade_image


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
