from __future__ import annotations

import colorsys
import math

import numpy as np
from PIL import Image

from src.image_ops import luminance, to_array


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def gaussian_score(value: float, target: float, spread: float) -> float:
    if spread <= 0:
        return 0.0
    return math.exp(-((value - target) ** 2) / (2.0 * spread * spread))


def gradient_sharpness(y: np.ndarray) -> float:
    if y.shape[0] < 2 or y.shape[1] < 2:
        return 0.0
    gy = np.diff(y, axis=0)
    gx = np.diff(y, axis=1)
    mag = np.mean(np.abs(gx[:, :-1])) + np.mean(np.abs(gy[:-1, :]))
    return float(mag)


DEFAULT_WEIGHTS = {
    "exposure": 0.22,
    "contrast": 0.17,
    "saturation": 0.16,
    "clipping": 0.14,
    "sharpness": 0.08,
    "color_balance": 0.05,
    "palette_diversity": 0.07,
    "local_contrast": 0.06,
    "highlight_rolloff": 0.03,
    "distinctiveness": 0.02,
}


def palette_hue_spread(arr: np.ndarray, sat: np.ndarray) -> float:
    pixels = arr.reshape(-1, 3)
    sat_flat = sat.reshape(-1)
    colorful = pixels[sat_flat > 0.05]
    if len(colorful) < 2:
        return 0.0
    hues = np.array([colorsys.rgb_to_hsv(float(r), float(g), float(b))[0] for r, g, b in colorful])
    angles = hues * 2.0 * math.pi
    resultant = math.hypot(float(np.cos(angles).mean()), float(np.sin(angles).mean()))
    circular_spread = clamp01(1.0 - resultant)
    sat_presence = clamp01(float((sat_flat > 0.08).mean()) / 0.55)
    return circular_spread * sat_presence


def local_contrast(y: np.ndarray) -> float:
    if y.shape[0] < 2 or y.shape[1] < 2:
        return 0.0
    horizontal = np.abs(np.diff(y, axis=1))
    vertical = np.abs(np.diff(y, axis=0))
    return float((horizontal.mean() + vertical.mean()) / 2.0)


def score_image(img: Image.Image, weights: dict[str, float] | None = None) -> dict[str, float]:
    weights = DEFAULT_WEIGHTS if weights is None else weights
    arr = to_array(img)
    y = luminance(arr)
    mean_y = float(y.mean())
    std_y = float(y.std())
    maxc = arr.max(axis=2)
    minc = arr.min(axis=2)
    sat = maxc - minc
    mean_sat = float(sat.mean())
    low_clip = float((arr <= 0.015).mean())
    high_clip = float((arr >= 0.985).mean())
    clipping = low_clip + high_clip
    channel_means = arr.reshape(-1, 3).mean(axis=0)
    balance_spread = float(channel_means.max() - channel_means.min())
    sharp = gradient_sharpness(y)

    exposure_score = gaussian_score(mean_y, 0.50, 0.20)
    contrast_score = gaussian_score(std_y, 0.22, 0.12)
    saturation_score = gaussian_score(mean_sat, 0.22, 0.16)
    clipping_score = clamp01(1.0 - clipping * 5.0)
    sharpness_score = clamp01(sharp / 0.055)
    color_balance_score = clamp01(1.0 - balance_spread * 2.2)
    palette_diversity_score = gaussian_score(palette_hue_spread(arr, sat), 0.45, 0.28)
    local_contrast_score = gaussian_score(local_contrast(y), 0.055, 0.035)
    highlight_tail = float(np.clip((y - 0.86) / 0.14, 0.0, 1.0).mean())
    highlight_rolloff_score = clamp01(1.0 - (high_clip * 7.0 + highlight_tail * 1.8))
    neutral_distance = math.sqrt(
        (mean_y - 0.50) ** 2
        + (std_y - 0.16) ** 2
        + (mean_sat - 0.10) ** 2
        + balance_spread**2
    )
    distinctiveness_score = gaussian_score(neutral_distance, 0.24, 0.18)

    parts = {
        "exposure": exposure_score,
        "contrast": contrast_score,
        "saturation": saturation_score,
        "clipping": clipping_score,
        "sharpness": sharpness_score,
        "color_balance": color_balance_score,
        "palette_diversity": palette_diversity_score,
        "local_contrast": local_contrast_score,
        "highlight_rolloff": highlight_rolloff_score,
        "distinctiveness": distinctiveness_score,
    }
    total_weight = sum(float(weights.get(k, 0.0)) for k in parts) or 1.0
    score = sum(parts[k] * float(weights.get(k, 0.0)) for k in parts) / total_weight
    exposure_balance = exposure_score * clipping_score
    saturation_balance = saturation_score * color_balance_score
    detail_score = sharpness_score

    return {
        "score": round(score * 100.0, 2),
        "contrast": round(contrast_score * 100.0, 2),
        "exposure_balance": round(exposure_balance * 100.0, 2),
        "saturation_balance": round(saturation_balance * 100.0, 2),
        "detail": round(detail_score * 100.0, 2),
        "exposure_score": round(exposure_score * 100.0, 2),
        "contrast_score": round(contrast_score * 100.0, 2),
        "saturation_score": round(saturation_score * 100.0, 2),
        "clipping_score": round(clipping_score * 100.0, 2),
        "sharpness_score": round(sharpness_score * 100.0, 2),
        "color_balance_score": round(color_balance_score * 100.0, 2),
        "palette_diversity_score": round(palette_diversity_score * 100.0, 2),
        "local_contrast_score": round(local_contrast_score * 100.0, 2),
        "highlight_rolloff_score": round(highlight_rolloff_score * 100.0, 2),
        "distinctiveness_score": round(distinctiveness_score * 100.0, 2),
        "mean_luminance": round(mean_y, 4),
        "luminance_std": round(std_y, 4),
        "mean_saturation": round(mean_sat, 4),
        "clip_ratio": round(clipping, 5),
        "sharpness_raw": round(sharp, 5),
    }
