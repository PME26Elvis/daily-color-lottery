from __future__ import annotations

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


def score_image(img: Image.Image, weights: dict[str, float] | None = None) -> dict[str, float]:
    weights = weights or {
        "exposure": 0.26,
        "contrast": 0.20,
        "saturation": 0.20,
        "clipping": 0.18,
        "sharpness": 0.10,
        "color_balance": 0.06,
    }
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

    parts = {
        "exposure": exposure_score,
        "contrast": contrast_score,
        "saturation": saturation_score,
        "clipping": clipping_score,
        "sharpness": sharpness_score,
        "color_balance": color_balance_score,
    }
    total_weight = sum(float(weights.get(k, 0.0)) for k in parts) or 1.0
    score = sum(parts[k] * float(weights.get(k, 0.0)) for k in parts) / total_weight
    return {
        "score": round(score * 100.0, 2),
        "exposure_score": round(exposure_score * 100.0, 2),
        "contrast_score": round(contrast_score * 100.0, 2),
        "saturation_score": round(saturation_score * 100.0, 2),
        "clipping_score": round(clipping_score * 100.0, 2),
        "sharpness_score": round(sharpness_score * 100.0, 2),
        "color_balance_score": round(color_balance_score * 100.0, 2),
        "mean_luminance": round(mean_y, 4),
        "luminance_std": round(std_y, 4),
        "mean_saturation": round(mean_sat, 4),
        "clip_ratio": round(clipping, 5),
        "sharpness_raw": round(sharp, 5),
    }
