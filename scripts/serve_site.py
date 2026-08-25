#!/usr/bin/env python3
from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_MODULES = ("icalendar", "PIL")


def validate_runtime() -> None:
    if sys.version_info < (3, 12):
        compatible_python = next(
            (
                executable
                for name in ("python3.14", "python3.13", "python3.12")
                if (executable := shutil.which(name)) is not None
            ),
            "python3.12",
        )
        raise SystemExit(
            f"Python 3.12 or newer is required; this command is using "
            f"{sys.version_info.major}.{sys.version_info.minor}.\n"
            "Create the project environment with:\n"
            f"  {compatible_python} -m venv .venv\n"
            "  source .venv/bin/activate\n"
            "  python -m pip install -r requirements.txt\n"
            "Then run: python scripts/serve_site.py"
        )

    missing = [name for name in REQUIRED_MODULES if importlib.util.find_spec(name) is None]
    if missing:
        raise SystemExit(
            "Project dependencies are not installed for this Python interpreter.\n"
            "Run: python -m pip install -r requirements.txt\n"
            "Then run: python scripts/serve_site.py"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build and serve the generated site for local development."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--output-dir", default="_site")
    args = parser.parse_args()
    validate_runtime()

    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "build_site.py"),
            "--output-dir",
            str(output_dir),
        ],
        cwd=ROOT,
        check=True,
    )

    handler = partial(SimpleHTTPRequestHandler, directory=str(output_dir))
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Serving {output_dir} at http://{args.host}:{args.port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
