#!/usr/bin/env python3
"""Apply a declared deterministic design to an identity-checked EGP snapshot."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.remove(str(Path(__file__).resolve().parent))

from grammar_kt.io import read_json
from grammar_kt.grammar.sampling import execute_sampling


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--design", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = execute_sampling(
        args.source,
        expected_sha256=args.sha256,
        design=read_json(args.design),
        output=args.output,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
