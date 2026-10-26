#!/usr/bin/env python3
"""Generate square Facebook posts from the canonical schedule exceptions."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from social_post import find_exception, render_post, save_post
from svoz_exceptions import load_svoz_exceptions


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--event", metavar="EVENT_ID", help="Render one exception by ID")
    choice.add_argument("--all", action="store_true", help="Render all reschedule exceptions")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "_social")
    args = parser.parse_args()

    try:
        exceptions = load_svoz_exceptions()
        if args.event:
            selected = (find_exception(args.event, exceptions),)
        else:
            selected = tuple(sorted(
                (item for item in exceptions if item.action == "reschedule"),
                key=lambda item: item.id,
            ))
            skipped = len(exceptions) - len(selected)
            if skipped:
                print(f"Skipped {skipped} unsupported non-reschedule exception(s).")

        for exception in selected:
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", exception.id):
                raise ValueError(f"Invalid exception ID for output filename: {exception.id!r}")
            output_path = args.output_dir / f"{exception.id}.png"
            save_post(render_post(exception), output_path)
            print(output_path)
    except (FileNotFoundError, ValueError) as error:
        parser.exit(1, f"error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
