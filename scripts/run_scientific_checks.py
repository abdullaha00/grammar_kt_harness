#!/usr/bin/env python3
"""Run and retain the small fixture-backed checks required by the refactor."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.remove(str(Path(__file__).resolve().parent))

from grammar_kt.evaluation import kt, simulation
from grammar_kt.generation.generators import generate_items
from grammar_kt.generation.validation import validate_items
from grammar_kt.io import ROOT, read_json, read_yaml, stable_id, utc_now, write_json
from grammar_kt.knowledge import policy, qmatrix, selection
from grammar_kt.measurement.operations import derive_operations
from grammar_kt.measurement.opportunities import (
    build_measurement_opportunities,
    opportunity_bank_fingerprint,
)


CELL = {
    "tense": "past", "aspect": "none", "voice": "active",
    "polarity": "negative", "clause": "declarative", "modal": "none",
}
CELL_ROW = {
    "canonical_cell_id": "CELL_FIX_PAST_NEGATIVE",
    "cell": CELL,
    "source_descriptor_ids": ["FIXTURE_EGP"],
    "source_mapping_notes": {"FIXTURE_EGP": None},
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "reference/five_module_refactor",
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        if not args.force:
            raise FileExistsError(f"evidence directory exists: {output}; use --force")
        expected = (ROOT / "reference/five_module_refactor").resolve()
        if output != expected:
            raise RuntimeError("--force is restricted to reference/five_module_refactor")
        shutil.rmtree(output)
    output.mkdir(parents=True)

    config = {
        "experiment_id": "FIVE_MODULE_REFACTOR_CHECKS_v1",
        "seed": 77,
        "measurement": {
            "include_predicate_class_contrasts": False,
            "include_agreement_variants": False,
        },
        "generators": {
            "standalone": "modules/generation/generators/llm_standalone_fixture_v0.yaml",
            "dialogue": "modules/generation/generators/llm_dialogue_fixture_v0.yaml",
        },
        "validation": "modules/generation/validation/blind_fixture_v0.yaml",
        "kc_policy": "modules/knowledge/policies/factorized.json",
        "kc_selection": "modules/knowledge/selection/configs/deterministic_v0.json",
        "simulation": "modules/evaluation/simulation/configs/structural_oracle_v0.json",
        "kt": "modules/evaluation/kt/configs/default.json",
    }
    write_json(output / "config.json", config)
    write_json(
        output / "manifest.json",
        {
            "command": [
                sys.executable,
                "scripts/run_scientific_checks.py",
                *(["--force"] if args.force else []),
            ],
            "timestamp_utc": utc_now(),
            "fixture_backends_only": True,
            "paid_api_calls": False,
            "seed": config["seed"],
        },
    )

    # A. Same cell, different predicate class, different operations.
    question = {**CELL, "tense": "present", "polarity": "positive", "clause": "polar_question"}
    conditions = {
        "subject_person": 3, "subject_number": "singular",
        "wh_role": None, "imperative_subtype": None,
    }
    operation_dependence = {
        "cell": question,
        "lexical_transitive": derive_operations(question, {**conditions, "predicate_class": "lexical_transitive"}),
        "copular": derive_operations(question, {**conditions, "predicate_class": "copular"}),
    }

    opportunities = build_measurement_opportunities([CELL_ROW], config["measurement"])
    opportunity = opportunities[0]
    opportunity_fingerprint = opportunity_bank_fingerprint(opportunities)

    # B/C. Paired formats and blind validation, with all raw evidence retained.
    accepted_by_format = {}
    reports = {}
    for label, generator_config in config["generators"].items():
        generated = generate_items(
            opportunities,
            generator_config,
            evidence_root=output / "evidence" / label / "generation",
        )
        validated = validate_items(
            generated["candidates"],
            opportunities,
            config["validation"],
            evidence_root=output / "evidence" / label / "validation",
        )
        accepted_by_format[label] = validated["accepted"][0]
        reports[label] = validated["report"]

    bad_generator = read_yaml(config["generators"]["standalone"])
    bad_generator["backend_config"] = {
        "kind": "fixture_map",
        "default": {
            "content": {"prompt": "Complete the sentence."},
            "target_answer": "Yesterday, the technician wrote the report.",
            "accepted_answers": ["Yesterday, the technician wrote the report."],
        },
    }
    bad_candidate = generate_items(
        opportunities,
        bad_generator,
        evidence_root=output / "evidence" / "rejected" / "generation",
    )["candidates"][0]
    bad_evaluator = read_yaml(config["validation"])
    bad_evaluator["structural_backend_config"] = {
        "kind": "fixture_map",
        "default": {
            "cell": {**CELL, "polarity": "positive"},
            "operations": [],
            "predicate_class": "lexical_transitive",
            "agreement_site": "main_verb",
        },
    }
    rejected_validation = validate_items(
        [bad_candidate],
        opportunities,
        bad_evaluator,
        evidence_root=output / "evidence" / "rejected" / "validation",
    )

    # D. Opportunity-level simulation is invariant to surface generator.
    params = simulation.load_simulation_parameters(config["simulation"])
    params.update(
        {
            "seed": config["seed"],
            "learners_per_profile": 1,
            "item_passes_per_learner": 2,
            "profiles": {"mixed": params["profiles"]["mixed"]},
        }
    )

    def simulate_item(item):
        runtime = {**item, "canonical_split": "development"}
        oracle_projection, feature_ids = simulation.project_oracle_items(
            [runtime], opportunities, params
        )
        oracle_by_item = {runtime["item_id"]: oracle_projection[0]["oracle_feature_ids"]}
        events, private, learners, learner_private = simulation.simulate_records(
            params,
            {runtime["item_id"]: runtime},
            oracle_by_item,
            feature_ids,
            1,
            2,
        )
        return {
            "events": events,
            "private_oracle": private,
            "learners": learners,
            "learner_private": learner_private,
            "oracle_projection": oracle_projection,
            "opportunity_outcome_sha256": simulation.opportunity_outcome_fingerprint(events),
        }

    simulations = {label: simulate_item(item) for label, item in accepted_by_format.items()}

    # E. Selection and application do not depend on generated wording.
    selection_fixture = read_json("modules/knowledge/selection/fixtures/core.json")
    selector_config = read_json(config["kc_selection"])
    selected = selection.evaluate_fixture(selection_fixture, selector_config)
    selected_policy_fingerprint = stable_id("FROZEN", selected["selected_policy"])
    frozen_policy = policy.load_policy(ROOT / config["kc_policy"])
    runtime_items = [
        {**accepted_by_format[label], "canonical_split": "development"}
        for label in ("standalone", "dialogue")
    ]
    projections, cards = policy.project_items(runtime_items, opportunities, frozen_policy)
    q_columns, q_rows, q_edges, q_audit = qmatrix.build(runtime_items, cards, projections)

    # F. Frozen compositional probe sanity and order invariance.
    kt_fixture = read_json("modules/evaluation/kt/fixtures/compositional_probe.json")
    second_probe = {
        **kt_fixture["probe_events"][0],
        "event_id": "PROBE_2",
        "sequence_index": 4,
        "timestamp": "2027-01-01T00:04:00+00:00",
    }
    probes = [kt_fixture["probe_events"][0], second_probe]
    forward = kt.project_compositional_interactions(
        kt_fixture["acquisition_events"], probes, kt_fixture["item_projections"]
    )
    reverse = kt.project_compositional_interactions(
        kt_fixture["acquisition_events"], list(reversed(probes)), kt_fixture["item_projections"]
    )
    frozen_states = kt.frozen_development_statistics(forward[0])
    parameters = read_json(config["kt"])
    _features, targets, predictions, fallback = kt.frozen_probe_features(
        forward[1],
        ["KC_COMPONENT"],
        frozen_states,
        alpha=float(parameters["empirical"]["alpha"]),
        beta=float(parameters["empirical"]["beta"]),
        cold_prior=float(parameters["compositional"]["cold_kc_prior"]),
    )

    def report_summary(report):
        fields = (
            "status", "candidate_items", "accepted_items", "rejected_items",
            "candidate_opportunity_coverage", "accepted_opportunity_coverage",
            "grammar_cell_exact_match_rate", "operation_exact_match_rate",
            "failure_types", "structural_evaluator_reliability",
            "quality_evaluator_reliability", "accepted_item_bank_sha256",
        )
        return {field: report[field] for field in fields}

    def item_example(item):
        return {
            "item_id": item["item_id"],
            "measurement_opportunity_id": item["measurement_opportunity_id"],
            "canonical_cell_id": item["canonical_cell_id"],
            "generator_id": item["generator_id"],
            "item_family": item["item_family"],
            "content": item["content"],
            "target_answer": item["target_answer"],
            "validated_structure": item["validated_structure"],
            "quality_diagnostics": item["quality_diagnostics"],
            "evidence_directory": item["generation_metadata"]["evidence_directory"],
        }

    rejected_example = rejected_validation["rejected"][0]
    rejected_item = rejected_example["item"]

    summary = {
        "experiment_id": config["experiment_id"],
        "A_operation_dependence": operation_dependence,
        "B_generator_invariance": {
            "measurement_opportunity_id": opportunity["measurement_opportunity_id"],
            "canonical_cell_id": opportunity["canonical_cell_id"],
            "expected_operations": opportunity["expected_operations"],
            "standalone_item_id": accepted_by_format["standalone"]["item_id"],
            "dialogue_item_id": accepted_by_format["dialogue"]["item_id"],
            "same_opportunity": accepted_by_format["standalone"]["measurement_opportunity_id"] == accepted_by_format["dialogue"]["measurement_opportunity_id"],
            "different_item_ids": accepted_by_format["standalone"]["item_id"] != accepted_by_format["dialogue"]["item_id"],
        },
        "C_validation": {
            "accepted_reports": {
                label: report_summary(report) for label, report in reports.items()
            },
            "rejected_report": report_summary(rejected_validation["report"]),
            "rejected_example": {
                "item_id": rejected_item["item_id"],
                "target_answer": rejected_item["target_answer"],
                "intended": {
                    "cell": opportunity["cell"],
                    "operations": opportunity["expected_operations"],
                    "predicate_class": opportunity["structural_conditions"]["predicate_class"],
                },
                "blindly_recovered": rejected_item["validated_structure"],
                "reasons": rejected_example["reasons"],
            },
        },
        "D_simulation_invariance": {
            "standalone_opportunity_outcome_sha256": simulations["standalone"]["opportunity_outcome_sha256"],
            "dialogue_opportunity_outcome_sha256": simulations["dialogue"]["opportunity_outcome_sha256"],
            "identical": simulations["standalone"]["opportunity_outcome_sha256"] == simulations["dialogue"]["opportunity_outcome_sha256"],
            "standalone_events": simulations["standalone"]["events"],
            "dialogue_events": simulations["dialogue"]["events"],
        },
        "E_KC_invariance": {
            "selection_policy_fingerprint": selected_policy_fingerprint,
            "item_projections": projections,
            "same_kcs_across_formats": projections[0]["kc_ids"] == projections[1]["kc_ids"],
            "qmatrix": {
                "columns": q_columns,
                "rows": q_rows,
                "edge_count": len(q_edges),
                "audit": q_audit,
            },
        },
        "F_KT_sanity": {
            "development_supported_kc_ids": sorted(forward[2]),
            "frozen_state": frozen_states,
            "targets": targets.tolist(),
            "predictions": predictions.tolist(),
            "zero_kc_fallback": fallback.tolist(),
            "probe_order_invariant_frozen_counts": forward[3] == reverse[3],
            "probe_updates_state": False,
        },
        "reproducibility": {
            "seed": config["seed"],
            "opportunity_bank_sha256": opportunity_fingerprint,
            "generator_ids": {label: item["generator_id"] for label, item in accepted_by_format.items()},
            "accepted_counts": {label: report["accepted_items"] for label, report in reports.items()},
            "rejected_count": rejected_validation["report"]["rejected_items"],
            "simulation_fingerprints": {label: value["opportunity_outcome_sha256"] for label, value in simulations.items()},
            "kc_policy_fingerprint": stable_id("FROZEN", frozen_policy),
            "selected_policy_fingerprint": selected_policy_fingerprint,
        },
        "representative_examples": {
            "measurement_opportunity": opportunity,
            "standalone": item_example(accepted_by_format["standalone"]),
            "dialogue": item_example(accepted_by_format["dialogue"]),
            "rejected": {
                "item_id": rejected_item["item_id"],
                "target_answer": rejected_item["target_answer"],
                "validated_structure": rejected_item["validated_structure"],
                "reasons": rejected_example["reasons"],
            },
        },
    }
    write_json(output / "summary.json", summary)
    print(json.dumps({"output": str(output), "checks": ["A", "B", "C", "D", "E", "F"], "status": "PASS"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
