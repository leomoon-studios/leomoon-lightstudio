"""Run every ``tests/headless/test_*.py`` in fresh Blender subprocesses.

Invoked by ``make headless-test`` as a regular Python script (not from
within Blender). Each test file gets its own
``blender --background --factory-startup`` subprocess: in-process
execution leaks ``bpy.context`` state (active area, keyconfig overrides)
across enable/disable cycles and triggers spurious operator-poll
failures, so subprocess isolation is required.

Set the Blender binary via the ``BLENDER`` environment variable, or pass
``--blender /path/to/blender``. Filter tests with ``--keyword foo``.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

HEADLESS_DIR = Path(__file__).resolve().parent / "headless"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--blender",
        default=os.environ.get("BLENDER") or shutil.which("blender") or "blender",
        help="Blender binary (defaults to $BLENDER, then PATH).",
    )
    parser.add_argument(
        "--keyword",
        "-k",
        default=None,
        help="Substring filter applied to each test filename.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    tests = sorted(HEADLESS_DIR.glob("test_*.py"))
    if args.keyword:
        tests = [t for t in tests if args.keyword in t.name]

    if not tests:
        print("No headless tests matched.")
        sys.exit(1)

    failed: list[str] = []
    for test in tests:
        print(f"\n=== {test.name} ===", flush=True)
        proc = subprocess.run(
            [
                args.blender,
                "--background",
                "--factory-startup",
                "--python",
                str(test),
            ],
            check=False,
        )
        if proc.returncode != 0:
            failed.append(test.name)

    print("\n=== headless summary ===", flush=True)
    print(f"  ran:    {len(tests)}")
    print(f"  failed: {len(failed)}")
    for name in failed:
        print(f"    - {name}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
