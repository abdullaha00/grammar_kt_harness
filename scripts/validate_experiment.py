#!/usr/bin/env python3
"""Validate manifests, schemas, joins, leakage boundaries, and reference counts."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.utils.io import write_json
from shared.utils.run_validation import validate_run, verify_manifests


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path, help="run directory, e.g. runs/current")
    parser.add_argument("--no-reference", action="store_true", help="skip current headline-count comparison")
    parser.add_argument("--manifests-only", action="store_true", help="check only recorded paths and hashes")
    args = parser.parse_args()
    run_dir = args.run.resolve()
    if args.manifests_only:
        errors = verify_manifests(run_dir)
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"{'PASS' if not errors else 'FAIL'}: {len(errors)} manifest error(s)")
        return 1 if errors else 0
    summary = validate_run(run_dir, compare_reference=not args.no_reference)
    write_json(run_dir / "summary.json", summary)
    for warning in summary["warnings"]:
        print(f"WARNING: {warning}", file=sys.stderr)
    for error in summary["errors"]:
        print(f"ERROR: {error}", file=sys.stderr)
    print(f"{summary['status']}: {summary['counts']}")
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
