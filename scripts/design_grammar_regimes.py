#!/usr/bin/env python3
"""Design semantic grammar regimes from frozen cells, K*, and optional items."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.grammar_kt.grammar_regimes import design_grammar_regimes


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise ValueError(f"invalid JSONL at {path}:{line_number}") from exc
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, required=True)
    parser.add_argument("--cells", type=Path, required=True)
    parser.add_argument("--kcs", type=Path)
    parser.add_argument("--items", type=Path)
    parser.add_argument("--design", type=Path)
    parser.add_argument("--assignments-output", type=Path)
    parser.add_argument("--audit-output", type=Path)
    arguments = parser.parse_args()

    schema = yaml.safe_load(arguments.schema.read_text(encoding="utf-8"))
    cells = _read_jsonl(arguments.cells)
    kcs = _read_jsonl(arguments.kcs) if arguments.kcs else None
    items = _read_jsonl(arguments.items) if arguments.items else None
    design = (
        yaml.safe_load(arguments.design.read_text(encoding="utf-8"))
        if arguments.design
        else None
    )
    result = design_grammar_regimes(
        schema,
        cells,
        generator_kcs=kcs,
        items=items,
        design=design,
    )
    if arguments.assignments_output:
        _write_jsonl(arguments.assignments_output, result["assignments"])
    if arguments.audit_output:
        arguments.audit_output.parent.mkdir(parents=True, exist_ok=True)
        arguments.audit_output.write_text(
            json.dumps(result["audit"], ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(result["audit"], ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
