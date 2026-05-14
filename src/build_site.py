from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def copytree(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--docs", default="docs")
    parser.add_argument("--output", default="output")
    parser.add_argument("--sources", default="sources")
    parser.add_argument("--site", default="site")
    args = parser.parse_args()

    root = Path.cwd()
    docs = root / args.docs
    output = root / args.output
    sources = root / args.sources
    site = root / args.site

    if site.exists():
        shutil.rmtree(site)
    shutil.copytree(docs, site)
    copytree(output, site / "output")
    copytree(sources, site / "sources")
    print(f"built {site}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
