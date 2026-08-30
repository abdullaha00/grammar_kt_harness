#!/usr/bin/env python3
"""Standalone deterministic verifier for a frozen matched-format bank."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from measurement_realism_bank import DEFAULT_RUNS, _run_root, verify_bank


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--runs-root", type=Path, default=DEFAULT_RUNS)
    args = parser.parse_args()
    result = verify_bank(_run_root(args.run_id, args.runs_root.resolve()))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
