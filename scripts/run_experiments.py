#!/usr/bin/env python3
"""Run small direct interventions over fixed scientific objects."""

from __future__ import annotations

import argparse
import sys
from copy import deepcopy
from functools import partial
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from grammar_kt.canonicalise import canonicalise
from grammar_kt.evaluate import evaluate
from grammar_kt.fold import apply_fold
from grammar_kt.generate import generate_items
from grammar_kt.io import (
    call_model,
    load_typed_resource,
    read_jsonl,
    read_text,
    read_yaml,
    write_json,
    write_jsonl,
)
from grammar_kt.kc import project_kcs
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
phase1_self_check_prompt = read_text(
    ROOT / "modules/grammar/resource/egp/normalisation/phase1_self_check.txt"
)
phase2_prompt = read_text(
    ROOT / "modules/grammar/resource/egp/normalisation/phase2.txt"
)
normalisation_rulebook = read_text(
    ROOT / "modules/grammar/resource/egp/normalisation/rulebook.md"
)
grammar_schema = read_yaml(ROOT / "modules/grammar/canonical/schema.yaml")

generation_prompt = read_text(ROOT / "modules/items/generation/prompt.txt")
contextual_generation_prompt = read_text(
    ROOT / "modules/items/generation/prompt_contextual.txt"
)
generation_rulebook = read_text(ROOT / "modules/items/generation/rulebook.md")
generation_design = read_yaml(ROOT / "modules/items/generation/design.yaml")
item_format = read_yaml(
    ROOT / "modules/items/generation/formats/controlled_production.yaml"
)

validation_prompt = read_text(ROOT / "modules/items/validation/prompt.txt")
validation_criteria = read_yaml(ROOT / "modules/items/validation/criteria.yaml")

grammar_fold_spec = read_yaml(
    ROOT / "data/fixtures/declarations/fold_reference.yaml"
)
simulation_world = read_yaml(
    ROOT / "data/fixtures/declarations/simulation_world.yaml"
)

factorized_policy = read_yaml(
    ROOT / "data/fixtures/declarations/kc_policies/factorized.yaml"
)
full_cell_policy = read_yaml(
    ROOT / "data/fixtures/declarations/kc_policies/full_cell.yaml"
)
interactions_policy = read_yaml(
    ROOT / "data/fixtures/declarations/kc_policies/interactions.yaml"
)

kt_protocol = read_yaml(ROOT / "modules/evaluation/kt/protocol.yaml")
evaluation_protocol = read_yaml(ROOT / "modules/evaluation/protocol.yaml")

fixture_model_call = partial(
    call_model,
    fixture_responses=read_yaml(ROOT / "data/fixtures/model_responses.yaml"),
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run small research-component interventions.")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "runs" / "modularity_experiments",
    )
    arguments = parser.parse_args()
    arguments.output.mkdir(parents=True, exist_ok=False)

    resources = load_typed_resource(RESOURCE_PATH, resource_schema)
    baseline_mappings = normalise(
        resources,
        phase1_prompt,
        phase2_prompt,
        normalisation_rulebook,
        grammar_schema,
        model="fixture",
        reasoning_effort="deterministic",
        model_call=fixture_model_call,
    )
    cells = canonicalise(baseline_mappings, grammar_schema)
    baseline_candidates = generate_items(
        cells,
        generation_prompt,
        generation_rulebook,
        generation_design,
        item_format,
        model="fixture",
        reasoning_effort="deterministic",
        model_call=fixture_model_call,
    )
    accepted, baseline_judgments = validate_items(
        baseline_candidates,
        cells,
        validation_prompt,
        validation_criteria,
        model="fixture",
        reasoning_effort="deterministic",
        model_call=fixture_model_call,
    )
    grammar_fold = apply_fold(cells, grammar_fold_spec)
    events = simulate(accepted, grammar_fold, simulation_world)

    fixed_items = deepcopy(accepted)
    fixed_events = deepcopy(events)
    write_jsonl(arguments.output / "fixed_accepted_items.jsonl", fixed_items)
    write_jsonl(arguments.output / "fixed_events.jsonl", fixed_events)

    # A. Normalisation-prompt intervention with unchanged downstream declarations.
    alternate_mappings = normalise(
        resources,
        phase1_self_check_prompt,
        phase2_prompt,
        normalisation_rulebook,
        grammar_schema,
        model="fixture",
        reasoning_effort="deterministic",
        model_call=fixture_model_call,
    )
    alternate_cells = canonicalise(alternate_mappings, grammar_schema)
    alternate_candidates = generate_items(
        alternate_cells,
        generation_prompt,
        generation_rulebook,
        generation_design,
        item_format,
        model="fixture",
        reasoning_effort="deterministic",
        model_call=fixture_model_call,
    )
    alternate_items, _ = validate_items(
        alternate_candidates,
        alternate_cells,
        validation_prompt,
        validation_criteria,
        model="fixture",
        reasoning_effort="deterministic",
        model_call=fixture_model_call,
    )
    alternate_fold = apply_fold(alternate_cells, grammar_fold_spec)
    alternate_events = simulate(alternate_items, alternate_fold, simulation_world)
    experiment_a = {
        "intervention": "Phase-1 prompt adds a final evidence self-check.",
        "mapping_differences": [
            {"baseline": left, "alternate": right}
            for left, right in zip(
                baseline_mappings, alternate_mappings, strict=True
            )
            if left != right
        ],
        "canonical_cells_identical": cells == alternate_cells,
        "downstream_items_identical": accepted == alternate_items,
        "downstream_events_identical": events == alternate_events,
    }
    write_json(arguments.output / "experiment_a_normalisation.json", experiment_a)

    # B. Generation-prompt intervention on the exact same GrammarCells.
    subset = cells[:3]
    baseline_subset = generate_items(
        subset,
        generation_prompt,
        generation_rulebook,
        generation_design,
        item_format,
        model="fixture",
        reasoning_effort="deterministic",
        model_call=fixture_model_call,
    )
    contextual_subset = generate_items(
        subset,
        contextual_generation_prompt,
        generation_rulebook,
        generation_design,
        item_format,
        model="fixture",
        reasoning_effort="deterministic",
        model_call=fixture_model_call,
    )
    baseline_subset_items, baseline_subset_judgments = validate_items(
        baseline_subset,
        subset,
        validation_prompt,
        validation_criteria,
        model="fixture",
        reasoning_effort="deterministic",
        model_call=fixture_model_call,
    )
    contextual_items, contextual_judgments = validate_items(
        contextual_subset,
        subset,
        validation_prompt,
        validation_criteria,
        model="fixture",
        reasoning_effort="deterministic",
        model_call=fixture_model_call,
    )
    experiment_b = {
        "intervention": "Generation prompt requests an explicit communicative context.",
        "grammar_cells_identical": subset == cells[:3],
        "generated_prompt_pairs": [
            {
                "cell_id": left["cell_id"],
                "baseline": left["prompt"],
                "contextual": right["prompt"],
            }
            for left, right in zip(baseline_subset, contextual_subset, strict=True)
        ],
        "baseline_validation": baseline_subset_judgments,
        "contextual_validation": contextual_judgments,
        "baseline_bank_summary": bank_summary(
            baseline_subset,
            baseline_subset_items,
            baseline_subset_judgments,
            subset,
        ),
        "contextual_bank_summary": bank_summary(
            contextual_subset,
            contextual_items,
            contextual_judgments,
            subset,
        ),
    }
    write_json(arguments.output / "experiment_b_generation.json", experiment_b)

    # C. KC representations on the exact same accepted items and events.
    representation_results = {}
    for name, policy in {
        "factorized": factorized_policy,
        "full_cell": full_cell_policy,
        "interactions": interactions_policy,
    }.items():
        projection = project_kcs(accepted, cells, policy)
        predictions = run_kt(events, projection, kt_protocol)
        results = evaluate(
            baseline_candidates,
            baseline_judgments,
            accepted,
            cells,
            grammar_fold,
            events,
            policy,
            projection,
            predictions,
            evaluation_protocol,
        )
        write_jsonl(arguments.output / f"projection_{name}.jsonl", projection)
        representation_results[name] = {
            "accepted_items_identical": accepted == fixed_items,
            "events_identical": events == fixed_events,
            "projection": projection,
            "kt": results["kt"],
        }

    projections = [
        representation_results[name]["projection"]
        for name in ("factorized", "full_cell", "interactions")
    ]
    experiment_c = {
        "accepted_item_records_identical": accepted == fixed_items,
        "event_records_identical": events == fixed_events,
        "accepted_item_file_matches_records": read_jsonl(
            arguments.output / "fixed_accepted_items.jsonl"
        )
        == accepted,
        "event_file_matches_records": read_jsonl(arguments.output / "fixed_events.jsonl")
        == events,
        "all_projection_records_differ": all(
            left != right
            for index, left in enumerate(projections)
            for right in projections[index + 1 :]
        ),
        "conditions": representation_results,
    }
    write_json(arguments.output / "experiment_c_kc.json", experiment_c)

    # D. Each KT technique receives the exact same event stream and projection.
    baseline_projection = project_kcs(accepted, cells, factorized_policy)
    predictions_by_technique = {}
    event_ids_by_technique = {}
    for technique in ("empirical", "bkt", "logistic"):
        protocol = {**kt_protocol, "techniques": [technique]}
        predictions = run_kt(events, baseline_projection, protocol)
        predictions_by_technique[technique] = predictions
        event_ids_by_technique[technique] = [row["event_id"] for row in predictions]
        write_jsonl(arguments.output / f"predictions_{technique}.jsonl", predictions)

    experiment_d = {
        "events_identical": events == fixed_events,
        "projection_identical": baseline_projection
        == project_kcs(accepted, cells, factorized_policy),
        "same_event_stream": len(
            {tuple(event_ids) for event_ids in event_ids_by_technique.values()}
        )
        == 1,
        "event_counts": {
            name: len(event_ids)
            for name, event_ids in event_ids_by_technique.items()
        },
        "prediction_preview": {
            name: rows[:2] for name, rows in predictions_by_technique.items()
        },
    }
    write_json(arguments.output / "experiment_d_kt.json", experiment_d)

    summary = {
        "normalisation": {
            "mapping_differences": len(experiment_a["mapping_differences"]),
            "downstream_events_identical": experiment_a[
                "downstream_events_identical"
            ],
        },
        "generation": {
            "fixed_cells": experiment_b["grammar_cells_identical"],
            "changed_prompts": sum(
                row["baseline"] != row["contextual"]
                for row in experiment_b["generated_prompt_pairs"]
            ),
            "baseline_acceptance": experiment_b["baseline_bank_summary"][
                "acceptance_rate"
            ],
            "contextual_acceptance": experiment_b["contextual_bank_summary"][
                "acceptance_rate"
            ],
        },
        "kc": {
            "accepted_items_identical": experiment_c[
                "accepted_item_records_identical"
            ],
            "events_identical": experiment_c["event_records_identical"],
            "all_projections_differ": experiment_c[
                "all_projection_records_differ"
            ],
        },
        "kt": {
            "same_event_stream": experiment_d["same_event_stream"],
            "event_counts": experiment_d["event_counts"],
        },
    }
    write_json(arguments.output / "summary.json", summary)
    print(arguments.output)
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
