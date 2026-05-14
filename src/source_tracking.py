from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from src.utils import file_sha256, iter_source_images, rel


def build_inventory(source_dir: Path, root: Path, now: datetime) -> dict[str, dict[str, Any]]:
    now_s = now.isoformat()
    inventory = {}
    for path in iter_source_images(source_dir):
        key = rel(path, root)
        stat = path.stat()
        inventory[key] = {
            "path": key,
            "sha256": file_sha256(path),
            "size_bytes": stat.st_size,
            "modified_time": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "last_seen": now_s,
            "status": "active",
        }
    return inventory


def diff_inventory(
    previous: dict[str, dict[str, Any]],
    current: dict[str, dict[str, Any]],
    run_id: str,
    now: datetime,
) -> list[dict[str, Any]]:
    events = []
    now_s = now.isoformat()
    previous_keys = set(previous)
    current_keys = set(current)

    for key in sorted(current_keys - previous_keys):
        events.append({"time": now_s, "run_id": run_id, "event": "source_added", "path": key})

    for key in sorted(previous_keys - current_keys):
        events.append({"time": now_s, "run_id": run_id, "event": "source_removed", "path": key})

    for key in sorted(previous_keys & current_keys):
        old = previous[key]
        new = current[key]
        if old.get("sha256") != new.get("sha256"):
            events.append({"time": now_s, "run_id": run_id, "event": "source_changed", "path": key})

    return events


def merge_inventory(
    previous: dict[str, dict[str, Any]],
    current: dict[str, dict[str, Any]],
    now: datetime,
) -> dict[str, dict[str, Any]]:
    merged = {}
    now_s = now.isoformat()
    for key, item in previous.items():
        if key not in current:
            old = dict(item)
            old["status"] = "removed"
            old["removed_at"] = old.get("removed_at", now_s)
            merged[key] = old
    for key, item in current.items():
        old = previous.get(key, {})
        new = dict(item)
        new["first_seen"] = old.get("first_seen", now_s)
        new["last_seen"] = now_s
        new["status"] = "active"
        merged[key] = new
    return dict(sorted(merged.items()))
