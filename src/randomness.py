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


def sample_ranges(ranges: dict[str, list[float]]) -> dict[str, float]:
    return {key: uniform(float(value[0]), float(value[1])) for key, value in ranges.items()}


def random_metadata() -> dict[str, Any]:
    return {
        "random_source": "os_entropy",
        "run_nonce": token_hex(16),
    }
