#!/usr/bin/env python3
"""Run the four small modularity checks requested for the refactored harness."""

from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from grammar_kt.canonicalise import canonicalise
from grammar_kt.evaluate import evaluate
from grammar_kt.fold import apply_fold
from grammar_kt.generate import generate_items
from grammar_kt.io import load_experiment, load_typed_resource, write_json, write_jsonl, write_yaml
from grammar_kt.kc import build_or_select_kcs, project_kcs
from grammar_kt.kt import run_kt
from grammar_kt.normalise import normalise
from grammar_kt.simulate import simulate
from grammar_kt.validate_items import bank_summary, validate_items


def main() -> int:
    parser = argparse.ArgumentParser(description="Run small research-component interventions.")
    parser.add_argument("--output", type=Path, default=ROOT / "runs" / "modularity_experiments")
    arguments = parser.parse_args()
    arguments.output.mkdir(parents=True, exist_ok=False)

    base = load_experiment("fixture")
    resources = load_typed_resource(base["resource"]["data"], base["resource"]["schema"])
    baseline_mappings = normalise(resources, base["normalisation"])
    cells = canonicalise(baseline_mappings, base["canonical"]["schema"])
    baseline_candidates = generate_items(cells, base["generation"])
    accepted, baseline_judgments = validate_items(baseline_candidates, cells, base["validation"])
    grammar_fold = apply_fold(cells, base["fold"])
    events = simulate(accepted, grammar_fold, base["simulation"])
    fixed_items = copy.deepcopy(accepted)
    fixed_events = copy.deepcopy(events)
    write_jsonl(arguments.output / "fixed_accepted_items.jsonl", accepted)
    write_jsonl(arguments.output / "fixed_events.jsonl", events)

    # A: prompt-only normalisation intervention, followed by the unchanged downstream calls.
    alternate_normalisation = copy.deepcopy(base["normalisation"])
    alternate_normalisation["phase1_prompt"] = "modules/resource/egp/normalisation/phase1_self_check.txt"
    alternate_mappings = normalise(resources, alternate_normalisation)
    alternate_cells = canonicalise(alternate_mappings, base["canonical"]["schema"])
    alternate_downstream_candidates = generate_items(alternate_cells, base["generation"])
    alternate_downstream_items, _ = validate_items(alternate_downstream_candidates, alternate_cells, base["validation"])
    alternate_fold = apply_fold(alternate_cells, base["fold"])
    alternate_events = simulate(alternate_downstream_items, alternate_fold, base["simulation"])
    experiment_a = {
        "intervention": "Phase-1 prompt adds a final evidence self-check.",
        "changed_configuration": ["normalisation.phase1_prompt"],
        "mapping_differences": [
            {"baseline": left, "alternate": right}
            for left, right in zip(baseline_mappings, alternate_mappings, strict=True)
            if left != right
        ],
        "canonical_cells_identical": cells == alternate_cells,
        "downstream_items_identical": accepted == alternate_downstream_items,
        "downstream_events_identical": events == alternate_events,
        "interpretation": "Fixture-scale inspectability check; no superiority claim is made.",
    }
    write_json(arguments.output / "experiment_a_normalisation.json", experiment_a)

    # B: generation-prompt intervention on a fixed cell subset.
    contextual_generation = copy.deepcopy(base["generation"])
    contextual_generation["prompt"] = "modules/generation/prompt_contextual.txt"
    subset = cells[:3]
    baseline_subset = generate_items(subset, base["generation"])
    contextual_subset = generate_items(subset, contextual_generation)
    baseline_subset_items, baseline_subset_judgments = validate_items(baseline_subset, subset, base["validation"])
    contextual_items, contextual_judgments = validate_items(contextual_subset, subset, base["validation"])
    experiment_b = {
        "intervention": "Prompt requests a short utterance or dialogue context.",
        "same_grammar_cells": True,
        "generated_prompt_pairs": [
            {"cell_id": left["cell_id"], "baseline": left["prompt"], "contextual": right["prompt"]}
            for left, right in zip(baseline_subset, contextual_subset, strict=True)
        ],
        "baseline_validation": baseline_subset_judgments,
        "contextual_validation": contextual_judgments,
        "baseline_bank_summary": bank_summary(baseline_subset, baseline_subset_items, baseline_subset_judgments, subset),
        "contextual_bank_summary": bank_summary(contextual_subset, contextual_items, contextual_judgments, subset),
        "interpretation": "Fixture-scale responsiveness check; no prompt-quality claim is made.",
    }
    write_json(arguments.output / "experiment_b_generation.json", experiment_b)

    # C: KC representations over byte-for-byte equal accepted rows and BaseEvents.
    representation_results = {}
    for name, policy_path in {
        "factorized": "modules/kc/policies/factorized.yaml",
        "full_cell": "modules/kc/policies/full_cell.yaml",
        "interactions": "modules/kc/policies/interactions.yaml",
    }.items():
        kc_config = copy.deepcopy(base["kc"])
        kc_config["policy"] = policy_path
        policy = build_or_select_kcs(cells, accepted, grammar_fold, kc_config)
        projection = project_kcs(accepted, cells, policy)
        predictions = run_kt(events, projection, base["kt"])
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
            base["evaluation"],
        )
        representation_results[name] = {
            "policy": policy,
            "projection": projection,
            "kt": results["kt"],
        }
    experiment_c = {
        "shared_accepted_items": "fixed_accepted_items.jsonl",
        "shared_base_events": "fixed_events.jsonl",
        "accepted_item_rows_identical": accepted == fixed_items,
        "base_event_rows_identical": events == fixed_events,
        "projection_rows_differ": len({str(row["projection"]) for row in representation_results.values()}) > 1,
        "conditions": representation_results,
    }
    write_json(arguments.output / "experiment_c_kc.json", experiment_c)

    # D: all KT techniques consume the same event IDs under one fixed projection.
    base_policy = build_or_select_kcs(cells, accepted, grammar_fold, base["kc"])
    base_projection = project_kcs(accepted, cells, base_policy)
    predictions = run_kt(events, base_projection, base["kt"])
    technique_inputs = {
        technique: [row["event_id"] for row in predictions if row["technique"] == technique]
        for technique in ("empirical", "bkt", "logistic")
    }
    experiment_d = {
        "fixed_projection": base_projection,
        "event_counts_by_technique": {name: len(event_ids) for name, event_ids in technique_inputs.items()},
        "first_event_id_by_technique": {name: event_ids[0] for name, event_ids in technique_inputs.items()},
        "last_event_id_by_technique": {name: event_ids[-1] for name, event_ids in technique_inputs.items()},
        "same_event_stream": len({tuple(value) for value in technique_inputs.values()}) == 1,
        "prediction_preview": predictions[:6],
    }
    write_json(arguments.output / "experiment_d_kt.json", experiment_d)

    summary = {
        "experiment_a": {
            "mapping_differences": len(experiment_a["mapping_differences"]),
            "downstream_events_identical": experiment_a["downstream_events_identical"],
        },
        "experiment_b": {
            "changed_prompts": sum(
                row["baseline"] != row["contextual"] for row in experiment_b["generated_prompt_pairs"]
            ),
            "baseline_acceptance": experiment_b["baseline_bank_summary"]["acceptance_rate"],
            "contextual_acceptance": experiment_b["contextual_bank_summary"]["acceptance_rate"],
        },
        "experiment_c": {
            "accepted_item_rows_identical": experiment_c["accepted_item_rows_identical"],
            "base_event_rows_identical": experiment_c["base_event_rows_identical"],
            "projection_rows_differ": experiment_c["projection_rows_differ"],
        },
        "experiment_d": {"same_event_stream": experiment_d["same_event_stream"]},
    }
    write_json(arguments.output / "summary.json", summary)
    print(arguments.output)
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
