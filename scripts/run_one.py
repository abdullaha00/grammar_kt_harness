#!/usr/bin/env python3
"""Show one fixture input flowing through one real stage implementation."""

from __future__ import annotations

import argparse
import json
import sys
from functools import partial
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from grammar_kt.canonicalise import canonicalise
from grammar_kt.generate import generate_items
from grammar_kt.io import call_model, load_typed_resource, read_jsonl, read_text, read_yaml
from grammar_kt.normalise import normalise
from grammar_kt.validate_items import validate_items


RESOURCE_PATH = ROOT / "data/fixtures/egp_pilot.jsonl"
resource_schema = read_yaml(ROOT / "modules/grammar/resource/egp/schema.yaml")
phase1_prompt = read_text(
    ROOT / "modules/grammar/resource/egp/normalisation/phase1.txt"
)
phase2_prompt = read_text(
    ROOT / "modules/grammar/resource/egp/normalisation/phase2.txt"
)
normalisation_rulebook = read_text(
    ROOT / "modules/grammar/resource/egp/normalisation/rulebook.md"
)
grammar_schema = read_yaml(ROOT / "modules/grammar/canonical/schema.yaml")
generation_prompt = read_text(ROOT / "modules/items/generation/prompt.txt")
generation_rulebook = read_text(ROOT / "modules/items/generation/rulebook.md")
generation_design = read_yaml(ROOT / "modules/items/generation/design.yaml")
item_format = read_yaml(
    ROOT / "modules/items/generation/formats/controlled_production.yaml"
)
lexicon = read_jsonl(ROOT / "modules/items/generation/lexicon.jsonl")
validation_prompt = read_text(ROOT / "modules/items/validation/prompt.txt")
validation_criteria = read_yaml(ROOT / "modules/items/validation/criteria.yaml")
fixture_model_call = partial(
    call_model,
    fixture_responses=read_yaml(ROOT / "data/fixtures/model_responses.yaml"),
)


def show(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one fixture-backed transformation.")
    parser.add_argument("stage", choices=["normalisation", "generation", "validation"])
    arguments = parser.parse_args()

    resources = load_typed_resource(RESOURCE_PATH, resource_schema)
    mappings = normalise(
        resources,
        phase1_prompt,
        phase2_prompt,
        normalisation_rulebook,
        grammar_schema,
        model="fixture",
        reasoning_effort="deterministic",
        model_call=fixture_model_call,
    )

    if arguments.stage == "normalisation":
        print("INPUT")
        show(resources[0])
        print("OUTPUT")
        show(mappings[0])
        return 0

    cells = canonicalise(mappings, grammar_schema)
    candidates = generate_items(
        cells[:1],
        generation_prompt,
        generation_rulebook,
        generation_design,
        item_format,
        lexicon,
        model="fixture",
        reasoning_effort="deterministic",
        model_call=fixture_model_call,
    )
    if arguments.stage == "generation":
        print("INPUT")
        show(cells[0])
        print("OUTPUT")
        show(candidates[0])
        return 0

    accepted, judgments = validate_items(
        candidates,
        cells[:1],
        validation_prompt,
        validation_criteria,
        model="fixture",
        reasoning_effort="deterministic",
        model_call=fixture_model_call,
    )
    print("INPUT")
    show(candidates[0])
    print("OUTPUT")
    show({"judgment": judgments[0], "accepted_item": accepted[0] if accepted else None})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
