#!/usr/bin/env python3
"""Build and gate the full-v1 true Q-matrix before learner simulation."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from grammar_kt.io import read_jsonl, read_yaml
from grammar_kt.measurement_gate import (
    build_measurement_bundle,
    verify_measurement_artifacts,
    write_measurement_artifacts,
)


def _read_regimes(path: Path | None) -> Any:
    if path is None:
        return None
    if path.suffix == ".jsonl":
        return read_jsonl(path)
    if path.suffix == ".csv":
        with path.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cells", type=Path, required=True)
    parser.add_argument("--items", type=Path, required=True)
    parser.add_argument("--kcs", type=Path, required=True)
    parser.add_argument("--design", type=Path, required=True)
    parser.add_argument("--regimes", type=Path)
    parser.add_argument("--dense-q-matrix", type=Path, required=True)
    parser.add_argument("--sparse-q-matrix", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="verify an existing frozen bundle instead of writing it",
    )
    arguments = parser.parse_args()

    bundle = build_measurement_bundle(
        read_jsonl(arguments.cells),
        read_jsonl(arguments.items),
        read_jsonl(arguments.kcs),
        read_yaml(arguments.design),
        grammar_regime_by_cell=_read_regimes(arguments.regimes),
    )
    paths = {
        "dense_q_matrix_path": arguments.dense_q_matrix,
        "sparse_q_matrix_path": arguments.sparse_q_matrix,
        "audit_path": arguments.audit,
        "manifest_path": arguments.manifest,
    }
    if arguments.verify_only:
        verify_measurement_artifacts(bundle, **paths)
        print("verified frozen Q* artifacts", flush=True)
    else:
        write_measurement_artifacts(bundle, **paths)
        counts = bundle["audit"]["counts"]
        print(
            f"measurement gate {bundle['audit']['status']}: "
            f"items={counts['items']}, K*={counts['generator_kcs']}, "
            f"rank={counts['q_rank']}, edges={counts['q_edges']}",
            flush=True,
        )
    if bundle["audit"]["status"] != "PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
