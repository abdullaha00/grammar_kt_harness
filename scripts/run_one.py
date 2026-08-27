#!/usr/bin/env python3
"""Show one real input flowing through one real stage implementation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from grammar_kt.canonicalise import canonicalise
from grammar_kt.generate import generate_items
from grammar_kt.io import load_experiment, load_typed_resource
from grammar_kt.normalise import normalise
from grammar_kt.validate_items import validate_items


def show(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one fixture-backed research transformation.")
    parser.add_argument("stage", choices=["normalisation", "generation", "validation"])
    arguments = parser.parse_args()
    config = load_experiment("fixture")
    resources = load_typed_resource(config["resource"]["data"], config["resource"]["schema"])
    mappings = normalise(resources, config["normalisation"])

    if arguments.stage == "normalisation":
        print("INPUT")
        show(resources[0])
        print("OUTPUT")
        show(mappings[0])
        return 0

    cells = canonicalise(mappings, config["canonical"]["schema"])
    candidates = generate_items(cells[:1], config["generation"])
    if arguments.stage == "generation":
        print("INPUT")
        show(cells[0])
        print("OUTPUT")
        show(candidates[0])
        return 0

    accepted, judgments = validate_items(candidates, cells[:1], config["validation"])
    print("INPUT")
    show(candidates[0])
    print("OUTPUT")
    show({"judgment": judgments[0], "accepted_item": accepted[0] if accepted else None})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
