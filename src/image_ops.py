from __future__ import annotations

import numpy as np
from PIL import Image


def open_rgb(path):
    with Image.open(path) as img:
        return img.convert("RGB")


def to_array(img: Image.Image) -> np.ndarray:
    return np.asarray(img).astype(np.float32) / 255.0


def to_image(arr: np.ndarray) -> Image.Image:
    arr = np.clip(arr, 0.0, 1.0)
    return Image.fromarray((arr * 255.0 + 0.5).astype(np.uint8), mode="RGB")


def dominant_palette_hex(img: Image.Image, colors: int = 5, sample_size: int = 96) -> list[str]:
    """Return up to ``colors`` dominant image colors as uppercase hex strings.

    The image is copied, converted to RGB, and downsampled before quantization so
    palette extraction stays inexpensive for large generated outputs.
    """
    if colors <= 0:
        return []

    sample = img.convert("RGB")
    sample.thumbnail((sample_size, sample_size), Image.Resampling.LANCZOS)
    quantized = sample.quantize(colors=colors, method=Image.Quantize.MEDIANCUT)
    palette = quantized.getpalette() or []
    color_counts = quantized.getcolors(maxcolors=sample.width * sample.height) or []
    ranked_indexes = [index for _count, index in sorted(color_counts, reverse=True)]

    result = []
    for index in ranked_indexes:
        offset = index * 3
        rgb = palette[offset : offset + 3]
        if len(rgb) != 3:
            continue
        hex_color = "#{:02X}{:02X}{:02X}".format(*rgb)
        if hex_color not in result:
            result.append(hex_color)
        if len(result) >= colors:
            break

    return result


def luminance(arr: np.ndarray) -> np.ndarray:
    return arr[..., 0] * 0.2126 + arr[..., 1] * 0.7152 + arr[..., 2] * 0.0722


def apply_exposure(arr: np.ndarray, ev: float) -> np.ndarray:
    return arr * (2.0 ** ev)


def apply_brightness(arr: np.ndarray, value: float) -> np.ndarray:
    return arr + value


def apply_contrast(arr: np.ndarray, value: float) -> np.ndarray:
    return (arr - 0.5) * value + 0.5


def apply_saturation(arr: np.ndarray, value: float) -> np.ndarray:
    gray = luminance(arr)[..., None]
    return gray + (arr - gray) * value


def apply_vibrance(arr: np.ndarray, value: float) -> np.ndarray:
    maxc = arr.max(axis=2)
    minc = arr.min(axis=2)
    sat = maxc - minc
    local_boost = (1.0 - np.clip(sat * 2.0, 0.0, 1.0))[..., None] * value
    gray = luminance(arr)[..., None]
    return gray + (arr - gray) * (1.0 + local_boost)


def apply_temperature_tint(arr: np.ndarray, temperature: float, tint: float) -> np.ndarray:
    out = arr.copy()
    out[..., 0] *= 1.0 + temperature
    out[..., 2] *= 1.0 - temperature
    out[..., 1] *= 1.0 + tint
    out[..., 0] *= 1.0 - tint * 0.25
    out[..., 2] *= 1.0 - tint * 0.25
    return out


def apply_shadows_highlights(arr: np.ndarray, shadows: float, highlights: float) -> np.ndarray:
    y = luminance(arr)
    shadow_mask = np.clip((0.55 - y) / 0.55, 0.0, 1.0)[..., None]
    highlight_mask = np.clip((y - 0.45) / 0.55, 0.0, 1.0)[..., None]
    return arr + shadow_mask * shadows + highlight_mask * highlights


def apply_gamma(arr: np.ndarray, gamma: float) -> np.ndarray:
    gamma = max(gamma, 0.05)
    return np.power(np.clip(arr, 0.0, 1.0), gamma)


def apply_fade(arr: np.ndarray, value: float) -> np.ndarray:
    return arr * (1.0 - value) + value


def apply_vignette(arr: np.ndarray, value: float) -> np.ndarray:
    if value <= 0:
        return arr
    h, w, _ = arr.shape
    y = np.linspace(-1.0, 1.0, h, dtype=np.float32)[:, None]
    x = np.linspace(-1.0, 1.0, w, dtype=np.float32)[None, :]
    dist = np.sqrt(x * x + y * y)
    mask = 1.0 - value * np.clip((dist - 0.18) / 1.20, 0.0, 1.0) ** 1.6
    return arr * mask[..., None]


def apply_grain(arr: np.ndarray, value: float, seed: int) -> np.ndarray:
    if value <= 0:
        return arr
    rng = np.random.default_rng(seed)
    noise = rng.normal(0.0, value, arr.shape).astype(np.float32)
    return arr + noise


def _param(params: dict[str, object], key: str, default: float) -> float:
    return float(params.get(key, default))


def apply_filmic_toe_shoulder(
    arr: np.ndarray, toe_strength: float, shoulder_strength: float
) -> np.ndarray:
    """Compress shadows/highlights with a smooth filmic S-curve."""
    toe_strength = max(float(toe_strength), 0.0)
    shoulder_strength = max(float(shoulder_strength), 0.0)
    safe = np.clip(arr, 0.0, None)
    toe_gamma = 1.0 + toe_strength
    shoulder = 1.0 + shoulder_strength * 4.0
    toe = np.power(safe, toe_gamma)
    return toe / (toe + np.power(np.clip(1.0 - safe, 0.0, None), shoulder) + 1e-6)


def apply_midtone_contrast(arr: np.ndarray, value: float, pivot: float = 0.5) -> np.ndarray:
    """Adjust contrast most strongly around the midtones."""
    value = float(value)
    pivot = float(pivot)
    contrast = (arr - pivot) * value + pivot
    mid_mask = 1.0 - np.clip(np.abs(arr - pivot) / max(pivot, 1.0 - pivot), 0.0, 1.0)
    return arr + (contrast - arr) * mid_mask


def apply_highlight_rolloff(arr: np.ndarray, value: float, threshold: float = 0.72) -> np.ndarray:
    """Roll values above ``threshold`` toward white instead of clipping harshly."""
    value = max(float(value), 0.0)
    threshold = float(np.clip(threshold, 0.0, 0.98))
    if value <= 0:
        return arr
    headroom = 1.0 - threshold
    highlights = np.clip((arr - threshold) / headroom, 0.0, None)
    compressed = threshold + headroom * (1.0 - np.exp(-highlights * (1.0 + value * 3.0)))
    blend = np.clip(highlights, 0.0, 1.0)
    return arr * (1.0 - blend) + compressed * blend


def apply_black_lift(arr: np.ndarray, value: float) -> np.ndarray:
    value = max(float(value), 0.0)
    if value <= 0:
        return arr
    shadow_weight = np.clip(1.0 - arr / 0.5, 0.0, 1.0)
    return arr + value * shadow_weight


def grade_image_classic(img: Image.Image, params: dict[str, object], grain_seed: int) -> Image.Image:
    arr = to_array(img)
    arr = apply_exposure(arr, _param(params, "exposure", 0.0))
    arr = apply_brightness(arr, _param(params, "brightness", 0.0))
    arr = apply_contrast(arr, _param(params, "contrast", 1.0))
    arr = apply_temperature_tint(arr, _param(params, "temperature", 0.0), _param(params, "tint", 0.0))
    arr = apply_shadows_highlights(arr, _param(params, "shadows", 0.0), _param(params, "highlights", 0.0))
    arr = apply_saturation(arr, _param(params, "saturation", 1.0))
    arr = apply_vibrance(arr, _param(params, "vibrance", 0.0))
    arr = apply_gamma(arr, _param(params, "gamma", 1.0))
    arr = apply_fade(arr, _param(params, "fade", 0.0))
    arr = apply_vignette(arr, _param(params, "vignette", 0.0))
    arr = apply_grain(arr, _param(params, "grain", 0.0), grain_seed)
    return to_image(arr)


def grade_image_filmic_curve(img: Image.Image, params: dict[str, object], grain_seed: int) -> Image.Image:
    arr = to_array(img)
    arr = apply_exposure(arr, _param(params, "exposure", 0.0))
    arr = apply_temperature_tint(arr, _param(params, "temperature", 0.0), _param(params, "tint", 0.0))
    arr = apply_black_lift(arr, _param(params, "black_lift", 0.0))
    arr = apply_filmic_toe_shoulder(
        arr, _param(params, "toe_strength", 0.25), _param(params, "shoulder_strength", 0.35)
    )
    arr = apply_midtone_contrast(arr, _param(params, "midtone_contrast", 1.08))
    arr = apply_highlight_rolloff(
        arr, _param(params, "highlight_rolloff", 0.45), _param(params, "rolloff_threshold", 0.72)
    )
    arr = apply_brightness(arr, _param(params, "brightness", 0.0))
    arr = apply_shadows_highlights(arr, _param(params, "shadows", 0.0), _param(params, "highlights", 0.0))
    arr = apply_saturation(arr, _param(params, "saturation", 1.0))
    arr = apply_vibrance(arr, _param(params, "vibrance", 0.0))
    arr = apply_gamma(arr, _param(params, "gamma", 1.0))
    arr = apply_fade(arr, _param(params, "fade", 0.0))
    arr = apply_vignette(arr, _param(params, "vignette", 0.0))
    arr = apply_grain(arr, _param(params, "grain", 0.0), grain_seed)
    return to_image(arr)


GRADING_ALGORITHMS = {
    "classic": grade_image_classic,
    "filmic_curve": grade_image_filmic_curve,
}


def grade_image(img: Image.Image, params: dict[str, object], grain_seed: int) -> Image.Image:
    algorithm = str(params.get("algorithm", "classic"))
    try:
        grade = GRADING_ALGORITHMS[algorithm]
    except KeyError as exc:
        available = ", ".join(sorted(GRADING_ALGORITHMS))
        raise ValueError(f"Unknown grading algorithm {algorithm!r}; expected one of: {available}") from exc
    return grade(img, params, grain_seed)
