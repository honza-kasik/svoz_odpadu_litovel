#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from generator_svozu_odpadu import build


STATIC_ENTRIES = (
    "CNAME",
    "styles.css",
    "favicon.png",
    "js",
    "resources",
    "docs",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the deployable static site artifact.")
    parser.add_argument(
        "--output-dir",
        default="_site",
        help="Directory where the deployable site will be created.",
    )
    args = parser.parse_args()

    os.chdir(ROOT)

    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir
    if output_dir.resolve() == ROOT:
        raise SystemExit("Refusing to use the repository root as the artifact output directory.")

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    for entry in STATIC_ENTRIES:
        copy_static_entry(ROOT / entry, output_dir / entry)

    build(output_dir)
    return 0


def copy_static_entry(source: Path, destination: Path) -> None:
    if source.is_dir():
        shutil.copytree(source, destination, ignore=ignore_generated_social)
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def ignore_generated_social(directory: str, names: list[str]) -> set[str]:
    if Path(directory).resolve() == (ROOT / "resources").resolve():
        return {"social"} & set(names)
    return set()


if __name__ == "__main__":
    raise SystemExit(main())
