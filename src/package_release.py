from __future__ import annotations

import argparse
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path


def parse_date(name: str):
    try:
        return datetime.strptime(name, "%Y-%m-%d").date()
    except ValueError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="output")
    parser.add_argument("--logs", default="logs")
    parser.add_argument("--dist", default="dist")
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()

    root = Path.cwd()
    output = root / args.output / "archive"
    logs = root / args.logs
    dist = root / args.dist
    dist.mkdir(parents=True, exist_ok=True)

    today = datetime.now(timezone.utc).date()
    earliest = today - timedelta(days=args.days - 1)
    bundle_name = f"daily-color-lottery-week-{today.isoformat()}.zip"
    bundle_path = dist / bundle_name

    files = []
    if output.exists():
        for day_dir in sorted(output.iterdir()):
            if not day_dir.is_dir():
                continue
            day = parse_date(day_dir.name)
            if day is None or day < earliest or day > today:
                continue
            files.extend(p for p in day_dir.rglob("*") if p.is_file())
    if logs.exists():
        files.extend(p for p in logs.rglob("*") if p.is_file())

    if not files:
        print("No files to package.")
        return 78

    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file in files:
            zf.write(file, file.relative_to(root))
    print(bundle_path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
