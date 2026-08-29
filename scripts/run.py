#!/usr/bin/env python3
"""Run the active grammar-to-KT methodology literally from top to bottom."""

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
from grammar_kt.fold import build_semantic_fold
from grammar_kt.generate import generate_items
from grammar_kt.io import (
    ModelCall,
    call_model,
    load_typed_resource,
    read_text,
    read_yaml,
    write_json,
    write_jsonl,
    write_yaml,
)
from grammar_kt.kc import project_kcs, write_q_matrix
from grammar_kt.kc_candidates import make_kc_candidates
from grammar_kt.kc_selection import select_kcs
from grammar_kt.kt import run_kt
from grammar_kt.normalise import normalise
from grammar_kt.simulate import materialize_latent_world, simulate_frozen_probes
from grammar_kt.validate_items import bank_summary, select_item_bank, validate_items


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
operation_design = read_yaml(
    ROOT / "modules/grammar/canonical/english_operations.yaml"
)

generation_prompt = read_text(ROOT / "modules/items/generation/prompt.txt")
generation_rulebook = read_text(ROOT / "modules/items/generation/rulebook.md")
generation_design = read_yaml(ROOT / "modules/items/generation/design.yaml")
item_format = read_yaml(
    ROOT / "modules/items/generation/formats/controlled_production.yaml"
)

validation_prompt = read_text(ROOT / "modules/items/validation/prompt.txt")
validation_criteria = read_yaml(ROOT / "modules/items/validation/criteria.yaml")

grammar_fold_design = read_yaml(ROOT / "modules/simulation/folds/semantic.yaml")
# The default executable world is an active schema-derived research condition,
# not the tiny fixture's manually enumerated hidden state.
simulation_world_design = read_yaml(
    ROOT / "modules/simulation/worlds/phase4_factorized.yaml"
)
simulation_protocol = read_yaml(ROOT / "modules/simulation/protocol.yaml")
candidate_design = read_yaml(ROOT / "modules/kcs/candidate_design.yaml") | {
    "operation_declarations": operation_design["operations"]
}
selection_design = read_yaml(ROOT / "modules/kcs/selection.yaml")
kt_protocol = read_yaml(ROOT / "modules/evaluation/kt/protocol.yaml")
evaluation_protocol = read_yaml(ROOT / "modules/evaluation/protocol.yaml")
model_backends = read_yaml(ROOT / "modules/model_backends.yaml")

FIXTURE_RESPONSES_PATH = ROOT / "data/fixtures/model_responses.yaml"
FIXTURE_FOLD_DESIGN_PATH = ROOT / "data/fixtures/semantic_fold.yaml"
FIXTURE_GENERATION_DESIGN_PATH = ROOT / "data/fixtures/item_generation.yaml"
FIXTURE_WORLD_PATH = ROOT / "data/fixtures/declarations/simulation_world.yaml"


def run_pipeline(
    run_dir: Path,
    *,
    model_call: ModelCall = call_model,
    backend_settings: dict[str, dict[str, str]] | None = None,
    fold_design: dict[str, Any] | None = None,
    item_design: dict[str, Any] | None = None,
    world_design: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute the complete scientific experiment in conceptual order."""

    run_dir.mkdir(parents=True, exist_ok=False)
    active_backends = (
        model_backends if backend_settings is None else backend_settings
    )

    resources = load_typed_resource(RESOURCE_PATH, resource_schema)

    # 1. Normalisation
    mappings = normalise(
        resources,
        phase1_prompt,
        phase2_prompt,
        normalisation_rulebook,
        grammar_schema,
        model=active_backends["normalisation"]["model"],
        reasoning_effort=active_backends["normalisation"]["reasoning_effort"],
        model_call=model_call,
        evidence_dir=run_dir / "normalisation",
    )
    write_jsonl(run_dir / "normalisation" / "mappings.jsonl", mappings)

    # 2. Canonicalisation
    cells = canonicalise(mappings, grammar_schema)
    write_jsonl(run_dir / "canonical" / "cells.jsonl", cells)

    # 3. Item generation
    active_item_design = item_design or generation_design
    candidates = generate_items(
        cells,
        generation_prompt,
        generation_rulebook,
        active_item_design,
        item_format,
        model=active_backends["generation"]["model"],
        reasoning_effort=active_backends["generation"]["reasoning_effort"],
        model_call=model_call,
        evidence_dir=run_dir / "items" / "generation",
    )
    write_jsonl(run_dir / "items" / "candidates.jsonl", candidates)

    # 4. Item validation
    validator_accepted, judgments = validate_items(
        candidates,
        cells,
        validation_prompt,
        validation_criteria,
        model=active_backends["validation"]["model"],
        reasoning_effort=active_backends["validation"]["reasoning_effort"],
        model_call=model_call,
        evidence_dir=run_dir / "items" / "validation_evidence",
    )
    items = select_item_bank(validator_accepted, active_item_design)
    write_jsonl(
        run_dir / "items" / "validator_accepted.jsonl", validator_accepted
    )
    write_jsonl(run_dir / "items" / "selected_bank.jsonl", items)
    write_jsonl(run_dir / "items" / "validation.jsonl", judgments)
    write_json(
        run_dir / "items" / "bank_summary.json",
        bank_summary(
            candidates,
            validator_accepted,
            judgments,
            cells,
            selected_items=items,
        ),
    )

    # 5. Grammar fold
    grammar_fold = build_semantic_fold(
        grammar_schema,
        cells,
        items,
        fold_design or grammar_fold_design,
    )
    write_jsonl(run_dir / "fold" / "assignments.jsonl", grammar_fold)

    # Candidate discovery is partitioned before the function call. It receives
    # no learner outcomes and cannot inspect held-out GrammarCell content.
    development_cell_ids = {
        row["cell_id"]
        for row in grammar_fold
        if row["grammar_split"] == "development"
    }
    development_cells = [
        row for row in cells if row["cell_id"] in development_cell_ids
    ]
    development_items = [
        row for row in items if row["cell_id"] in development_cell_ids
    ]
    candidate_inventory = make_kc_candidates(
        grammar_schema,
        development_cells,
        development_items,
        candidate_design,
    )
    write_json(run_dir / "kc" / "candidate_inventory.json", candidate_inventory)

    # 6. Simulation
    latent_world = materialize_latent_world(
        world_design or simulation_world_design,
        grammar_schema,
        cells,
    )
    events = simulate_frozen_probes(
        items,
        grammar_fold,
        latent_world,
        simulation_protocol,
        oracle_path=run_dir / "simulation" / "oracle_debug.json",
    )
    write_jsonl(run_dir / "simulation" / "events.jsonl", events)

    # 7. Learner-evidence KC selection. Only development items and the reserved
    # train/validation evidence declared by selection_design can enter.
    development_item_ids = {row["item_id"] for row in development_items}
    development_events = [
        row for row in events if row["item_id"] in development_item_ids
    ]
    policy = select_kcs(
        candidate_inventory,
        development_events,
        selection_design,
    )
    write_yaml(run_dir / "kc" / "frozen_policy.yaml", policy)
    write_json(
        run_dir / "kc" / "selection_trace.json",
        policy["selection_metadata"],
    )

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
        validator_accepted_items=validator_accepted,
    )
    write_json(run_dir / "evaluation" / "results.json", results)

    write_json(
        run_dir / "run_settings.json",
        {
            "declarations": {
                "grammar_schema": grammar_schema["schema_id"],
                "item_generation": active_item_design["design_id"],
                "grammar_fold": (fold_design or grammar_fold_design)["fold_id"],
                "simulation_protocol": simulation_protocol["protocol_id"],
                "simulation_world": latent_world["world_id"],
                "candidate_design": candidate_design["candidate_design_id"],
                "kc_selection": selection_design["selection_id"],
                "kt_protocol": kt_protocol["protocol_id"],
                "evaluation_protocol": evaluation_protocol["protocol_id"],
            },
            "seeds": {
                "simulation": latent_world["seed"],
                "logistic": kt_protocol["logistic"]["random_seed"],
                "bootstrap": evaluation_protocol["paired_bootstrap"]["seed"],
            },
            "models": {
                stage: {
                    "model": active_backends[stage]["model"],
                    "reasoning_effort": active_backends[stage]["reasoning_effort"],
                }
                for stage in ("normalisation", "generation", "validation")
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
        fixture_backends = {
            stage: {"model": "fixture", "reasoning_effort": "deterministic"}
            for stage in ("normalisation", "generation", "validation")
        }
        results = run_pipeline(
            output,
            model_call=fixture_model_call,
            backend_settings=fixture_backends,
            fold_design=read_yaml(FIXTURE_FOLD_DESIGN_PATH),
            item_design=read_yaml(FIXTURE_GENERATION_DESIGN_PATH),
            world_design=read_yaml(FIXTURE_WORLD_PATH),
        )
    else:
        output = arguments.output or ROOT / "runs" / "baseline"
        results = run_pipeline(output)

    print(f"completed: {output}")
    print(f"selected bank items: {results['dataset']['selected_bank_items']}")
    print(f"events: {results['input_counts']['events']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
