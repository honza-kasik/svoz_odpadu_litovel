#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from generator_svozu_odpadu import generate_release_data, refresh_release_data


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate deterministic CSV, canonical ICS and bio JSON release data."
    )
    parser.add_argument("--output-dir", default=str(ROOT))
    args = parser.parse_args()
    os.chdir(ROOT)
    output_dir = Path(args.output_dir).resolve()
    if output_dir == ROOT.resolve():
        refresh_release_data(output_dir)
    else:
        generate_release_data(output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
