from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def run_id_from_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H-%M-%SZ")


def date_from_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def write_json(path: Path, data: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_jsonl(path: Path, item: Any) -> None:
    ensure_dir(path.parent)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")


def load_jsonl(path: Path) -> list[Any]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9._-]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "source"


def iter_source_images(source_dir: Path) -> list[Path]:
    if not source_dir.exists():
        return []
    return sorted(
        p for p in source_dir.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
    )


def rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def safe_rel(path: Path, root: Path, label: str | None = None) -> str:
    """Return a stable repo-relative or portable external path key."""
    resolved_path = path.resolve()
    resolved_root = root.resolve()
    try:
        return resolved_path.relative_to(resolved_root).as_posix()
    except ValueError:
        digest = hashlib.sha256(resolved_path.as_posix().encode("utf-8")).hexdigest()[:12]
        name = slugify(label or resolved_path.name)
        return f"external/{digest}/{name}"


def resolve_config_path(value: str | None, default: str, root: Path) -> Path:
    raw = Path(value or default).expanduser()
    return raw if raw.is_absolute() else root / raw


def downsample_image(img: Any, max_dimension: int | None):
    if not max_dimension or max_dimension <= 0 or max(img.size) <= max_dimension:
        return img.copy()
    sample = img.copy()
    sample.thumbnail((max_dimension, max_dimension))
    return sample
