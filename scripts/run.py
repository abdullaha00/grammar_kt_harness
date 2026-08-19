#!/usr/bin/env python3
"""Run a declared experiment."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Prevent this directory's inspect.py from shadowing Python's standard inspect module.
sys.path.remove(str(Path(__file__).resolve().parent))

from grammar_kt.runner import run_experiment


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the grammar-to-KT pipeline.")
    parser.add_argument("experiment", help="short name in experiments/ (without .yaml)")
    parser.add_argument("--from", dest="from_stage", help="reuse earlier outputs from the parent run and execute from this stage")
    parser.add_argument("--force", action="store_true", help="replace this exact run directory")
    args = parser.parse_args()
    print(run_experiment(args.experiment, from_stage=args.from_stage, force=args.force))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
