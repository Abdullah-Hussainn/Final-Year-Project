"""
Smoke test / demo runner for the backend floorplanning pipeline.

Run from the repo root:

    python backend/test_full_pipeline.py

It runs the full headless pipeline and verifies that these artifacts are
created under backend/outputs/:

    backend/outputs/placement.png
    backend/outputs/placement.def
    backend/outputs/metrics.json

This is NOT a pytest unit test yet (kept intentionally simple for the first
milestone); it doubles as a manual demo of the end-to-end flow.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow `python backend/test_full_pipeline.py` from the repo root by making the
# repo root importable (so `backend` is a package-qualified import path).
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.pipeline.full_pipeline import run_pipeline  # noqa: E402

EXPECTED_FILES = [
    "placement.png",
    "placement.def",
    "metrics.json",
]


def main() -> int:
    output_dir = Path(__file__).resolve().parent / "outputs"

    print("Running backend floorplanning pipeline...")
    summary = run_pipeline(output_dir=str(output_dir))

    print("\nPipeline summary:")
    print(json.dumps(summary, indent=2))

    print("\nVerifying expected output files:")
    all_ok = True
    for name in EXPECTED_FILES:
        path = output_dir / name
        exists = path.exists() and path.stat().st_size > 0
        status = "OK" if exists else "MISSING/EMPTY"
        print(f"  [{status}] {path}")
        all_ok = all_ok and exists

    if not all_ok:
        print("\nFAILED: one or more expected output files were not created.")
        return 1

    print("\nSUCCESS: all expected output files were created.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
