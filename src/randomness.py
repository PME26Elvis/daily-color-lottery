from __future__ import annotations

import os
import secrets
from typing import Any

_rng = secrets.SystemRandom()


def uniform(low: float, high: float) -> float:
    return low + (_rng.random() * (high - low))


def token_hex(nbytes: int = 16) -> str:
    return secrets.token_hex(nbytes)


def numpy_seed() -> int:
    return int.from_bytes(os.urandom(8), "big", signed=False)


def sample_ranges(ranges: dict[str, Any]) -> dict[str, Any]:
    sampled = {}
    for key, value in ranges.items():
        if (
            isinstance(value, list)
            and len(value) == 2
            and all(isinstance(item, int | float) for item in value)
        ):
            sampled[key] = uniform(float(value[0]), float(value[1]))
        else:
            sampled[key] = value
    return sampled


def random_metadata(seed: int | None = None) -> dict[str, Any]:
    if seed is not None:
        return {
            "random_source": "deterministic_seed",
            "seed": seed,
            "deterministic": True,
        }
    return {
        "random_source": "os_entropy",
        "run_nonce": token_hex(16),
        "deterministic": False,
    }
