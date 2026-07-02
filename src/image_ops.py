from __future__ import annotations

from typing import Any

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


def _tone_to_rgb(tone: Any) -> np.ndarray:
    if isinstance(tone, str):
        value = tone.lstrip("#")
        if len(value) != 6:
            raise ValueError("Tone hex colors must use RRGGBB format")
        return np.array([int(value[i : i + 2], 16) for i in (0, 2, 4)], dtype=np.float32) / 255.0

    rgb = np.asarray(tone, dtype=np.float32)
    if rgb.shape != (3,):
        raise ValueError("Tone colors must contain exactly three RGB channels")
    if np.any(rgb > 1.0):
        rgb = rgb / 255.0
    return np.clip(rgb, 0.0, 1.0)


def apply_split_tone(
    arr: np.ndarray,
    shadow_color: Any,
    highlight_color: Any,
    strength: float,
    balance: float,
) -> np.ndarray:
    """Tint shadows and highlights with smooth luminance-weighted masks.

    ``balance`` shifts the split point lower or higher: negative values give
    more room to highlights, while positive values give more room to shadows.
    """
    strength = float(np.clip(strength, 0.0, 1.0))
    if strength <= 0.0:
        return arr

    split_point = 0.5 + float(np.clip(balance, -1.0, 1.0)) * 0.25
    y = np.clip(luminance(arr), 0.0, 1.0)
    shadow_mask = np.clip((split_point - y) / max(split_point, 1e-6), 0.0, 1.0) ** 1.5
    highlight_mask = np.clip((y - split_point) / max(1.0 - split_point, 1e-6), 0.0, 1.0) ** 1.5

    shadow_rgb = _tone_to_rgb(shadow_color)
    highlight_rgb = _tone_to_rgb(highlight_color)
    toned = arr.copy()
    toned += (shadow_rgb - toned) * (shadow_mask[..., None] * strength)
    toned += (highlight_rgb - toned) * (highlight_mask[..., None] * strength)
    return toned


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


def grade_image(img: Image.Image, params: dict[str, Any], grain_seed: int) -> Image.Image:
    arr = to_array(img)
    arr = apply_exposure(arr, params.get("exposure", 0.0))
    arr = apply_brightness(arr, params.get("brightness", 0.0))
    arr = apply_contrast(arr, params.get("contrast", 1.0))
    arr = apply_temperature_tint(arr, params.get("temperature", 0.0), params.get("tint", 0.0))
    arr = apply_shadows_highlights(arr, params.get("shadows", 0.0), params.get("highlights", 0.0))
    arr = apply_split_tone(
        arr,
        params.get("shadow_tone", [0.0, 0.0, 0.0]),
        params.get("highlight_tone", [1.0, 1.0, 1.0]),
        params.get("split_strength", 0.0),
        params.get("split_balance", 0.0),
    )
    arr = apply_saturation(arr, params.get("saturation", 1.0))
    arr = apply_vibrance(arr, params.get("vibrance", 0.0))
    arr = apply_gamma(arr, params.get("gamma", 1.0))
    arr = apply_fade(arr, params.get("fade", 0.0))
    arr = apply_vignette(arr, params.get("vignette", 0.0))
    arr = apply_grain(arr, params.get("grain", 0.0), grain_seed)
    return to_image(arr)
