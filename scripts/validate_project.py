#!/usr/bin/env python3
from __future__ import annotations

import py_compile
import subprocess
import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    os.chdir(ROOT)
    run([sys.executable, "tests.py"])
    validate_exception_json()
    compile_python_files()
    return 0


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def validate_exception_json() -> None:
    from lokace_svozu import WasteType
    from svoz_exceptions import load_svoz_exceptions

    load_svoz_exceptions(
        allowed_waste_types={waste_type.name for waste_type in WasteType}
    )


def compile_python_files() -> None:
    python_files = sorted(Path(".").glob("*.py")) + sorted(Path("scripts").glob("*.py"))
    for path in python_files:
        py_compile.compile(str(path), doraise=True)


if __name__ == "__main__":
    raise SystemExit(main())
