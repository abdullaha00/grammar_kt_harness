#!/usr/bin/env python3
"""Run the baseline research pipeline literally from top to bottom."""

from __future__ import annotations

import argparse
import sys
from functools import partial
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from grammar_kt.canonicalise import canonicalise
from grammar_kt.evaluate import evaluate
from grammar_kt.fold import apply_fold
from grammar_kt.generate import generate_items
from grammar_kt.io import (
    ModelCall,
    call_model,
    load_typed_resource,
    read_jsonl,
    read_text,
    read_yaml,
    write_json,
    write_jsonl,
    write_yaml,
)
from grammar_kt.kc import project_kcs, write_q_matrix
from grammar_kt.kt import run_kt
from grammar_kt.normalise import normalise
from grammar_kt.simulate import simulate
from grammar_kt.validate_items import bank_summary, validate_items


# Research declarations

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

grammar_fold_spec = read_yaml(ROOT / "modules/simulation/folds/reference.yaml")
simulation_world = read_yaml(ROOT / "modules/simulation/world.yaml")
kc_policy = read_yaml(ROOT / "modules/kcs/policies/factorized.yaml")
kt_protocol = read_yaml(ROOT / "modules/evaluation/kt/protocol.yaml")
evaluation_protocol = read_yaml(ROOT / "modules/evaluation/protocol.yaml")

NORMALISATION_MODEL = "gpt-5.6-sol"
GENERATION_MODEL = "gpt-5.6-sol"
VALIDATION_MODEL = "gpt-5.6-terra"
REASONING_EFFORT = "medium"

FIXTURE_RESPONSES_PATH = ROOT / "data/fixtures/model_responses.yaml"


def run_pipeline(
    run_dir: Path,
    *,
    model_call: ModelCall = call_model,
    normalisation_model: str = NORMALISATION_MODEL,
    generation_model: str = GENERATION_MODEL,
    validation_model: str = VALIDATION_MODEL,
    reasoning_effort: str = REASONING_EFFORT,
) -> dict[str, Any]:
    """Execute the complete scientific experiment in conceptual order."""

    run_dir.mkdir(parents=True, exist_ok=False)

    resources = load_typed_resource(RESOURCE_PATH, resource_schema)

    # 1. Normalisation
    mappings = normalise(
        resources,
        phase1_prompt,
        phase2_prompt,
        normalisation_rulebook,
        grammar_schema,
        model=normalisation_model,
        reasoning_effort=reasoning_effort,
        model_call=model_call,
        evidence_dir=run_dir / "normalisation",
    )
    write_jsonl(run_dir / "normalisation" / "mappings.jsonl", mappings)

    # 2. Canonicalisation
    cells = canonicalise(mappings, grammar_schema)
    write_jsonl(run_dir / "canonical" / "cells.jsonl", cells)

    # 3. Item generation
    candidates = generate_items(
        cells,
        generation_prompt,
        generation_rulebook,
        generation_design,
        item_format,
        lexicon,
        model=generation_model,
        reasoning_effort=reasoning_effort,
        model_call=model_call,
        evidence_dir=run_dir / "items" / "generation",
    )
    write_jsonl(run_dir / "items" / "candidates.jsonl", candidates)

    # 4. Item validation
    items, judgments = validate_items(
        candidates,
        cells,
        validation_prompt,
        validation_criteria,
        model=validation_model,
        reasoning_effort=reasoning_effort,
        model_call=model_call,
        evidence_dir=run_dir / "items" / "validation_evidence",
    )
    write_jsonl(run_dir / "items" / "accepted.jsonl", items)
    write_jsonl(run_dir / "items" / "validation.jsonl", judgments)
    write_json(
        run_dir / "items" / "bank_summary.json",
        bank_summary(candidates, items, judgments, cells),
    )

    # 5. Grammar fold
    grammar_fold = apply_fold(cells, grammar_fold_spec)
    write_jsonl(run_dir / "fold" / "assignments.jsonl", grammar_fold)

    # 6. Simulation
    events = simulate(
        items,
        grammar_fold,
        simulation_world,
        oracle_path=run_dir / "simulation" / "oracle_debug.json",
    )
    write_jsonl(run_dir / "simulation" / "events.jsonl", events)

    # 7. KC representation
    policy = kc_policy
    write_yaml(run_dir / "kc" / "frozen_policy.yaml", policy)

    # 8. KC projection
    projection = project_kcs(items, cells, policy)
    write_jsonl(run_dir / "kc" / "projection.jsonl", projection)
    write_q_matrix(run_dir / "kc" / "q_matrix.csv", projection)

    # 9. Knowledge tracing
    predictions = run_kt(events, projection, kt_protocol)
    write_jsonl(run_dir / "kt" / "predictions.jsonl", predictions)

    # 10. Evaluation
    results = evaluate(
        candidates,
        judgments,
        items,
        cells,
        grammar_fold,
        events,
        policy,
        projection,
        predictions,
        evaluation_protocol,
    )
    write_json(run_dir / "evaluation" / "results.json", results)

    write_json(
        run_dir / "run_settings.json",
        {
            "seeds": {
                "simulation": simulation_world["seed"],
                "logistic": kt_protocol["logistic"]["random_seed"],
                "bootstrap": evaluation_protocol["paired_bootstrap"]["seed"],
            },
            "models": {
                "normalisation": normalisation_model,
                "generation": generation_model,
                "validation": validation_model,
                "reasoning_effort": reasoning_effort,
            },
        },
    )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the readable grammar-to-KT pipeline."
    )
    parser.add_argument(
        "--fixture", action="store_true", help="use deterministic fixture model responses"
    )
    parser.add_argument("--output", type=Path, help="new output directory")
    arguments = parser.parse_args()

    if arguments.fixture:
        fixture_model_call = partial(
            call_model,
            fixture_responses=read_yaml(FIXTURE_RESPONSES_PATH),
        )
        output = arguments.output or ROOT / "runs" / "fixture"
        results = run_pipeline(
            output,
            model_call=fixture_model_call,
            normalisation_model="fixture",
            generation_model="fixture",
            validation_model="fixture",
            reasoning_effort="deterministic",
        )
    else:
        output = arguments.output or ROOT / "runs" / "baseline"
        results = run_pipeline(output)

    print(f"completed: {output}")
    print(f"accepted items: {results['dataset']['accepted_items']}")
    print(f"events: {results['input_counts']['events']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
