#!/usr/bin/env python3
"""Run the direct Phase 3 development-only KC-selection investigation.

The legacy artifact contributes only its 16 ``canonical_split=development``
GrammarCells and 30 measurement-opportunity IDs. Learner evidence is newly
simulated from the declared Phase-3 worlds, then reused unchanged for every KC
representation compared within a world/seed condition.
"""

from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import shutil
import sys
from collections import Counter
from pathlib import Path
from statistics import mean, median
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from grammar_kt.canonicalise import validate_cell
from grammar_kt.evaluate import paired_policy_bootstrap
from grammar_kt.io import read_jsonl, read_yaml, write_json
from grammar_kt.kc_candidates import make_kc_candidates
from grammar_kt.kc_selection import (
    fit_predict_kc_logistic,
    score_candidate_policy,
    select_kcs,
)
from grammar_kt.simulate import materialize_latent_world, simulate


LEGACY_PATH = (
    ROOT / "experiments/post_training_v1/data/pilot_v1/opportunities.jsonl"
)
WORLD_PATHS = (
    ROOT / "modules/simulation/worlds/phase3_factorized.yaml",
    ROOT / "modules/simulation/worlds/phase3_interaction_probe.yaml",
)
SEEDS = tuple(range(20260827, 20260832))
LAMBDA_GRID = (0.0, 0.0001, 0.00025, 0.0005, 0.001, 0.002, 0.005, 0.01)
TRUE_INTERACTION_ID = (
    "kc_interaction__aspect_perfect__and__polarity_negative"
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _rows_digest(rows: Iterable[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(
            json.dumps(
                row, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        )
        digest.update(b"\n")
    return digest.hexdigest()


def _write_jsonl_gzip(path: Path, rows: Iterable[dict[str, Any]]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as compressed:
            for row in rows:
                compressed.write(
                    (
                        json.dumps(
                            row,
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        )
                        + "\n"
                    ).encode("utf-8")
                )
    return _sha256_file(path)


def _gzip_file(source: Path, target: Path) -> dict[str, str]:
    raw_sha256 = _sha256_file(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as source_stream, target.open("wb") as target_stream:
        with gzip.GzipFile(
            fileobj=target_stream, mode="wb", mtime=0
        ) as compressed:
            shutil.copyfileobj(source_stream, compressed)
    source.unlink()
    return {
        "logical_uncompressed_sha256": raw_sha256,
        "retained_gzip_sha256": _sha256_file(target),
    }


def _candidate_design() -> dict[str, Any]:
    design = read_yaml(ROOT / "modules/kcs/candidate_design.yaml")
    operations = read_yaml(
        ROOT / "modules/grammar/canonical/english_operations.yaml"
    )
    return design | {"operation_declarations": operations["operations"]}


def _development_structure(
    schema: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, str]], list[dict[str, Any]]]:
    """Reconstruct only development structure, never legacy study evidence."""

    rows = read_jsonl(LEGACY_PATH)
    development_rows = [
        row for row in rows if row["canonical_split"] == "development"
    ]
    features_by_cell: dict[str, dict[str, str]] = {}
    for row in development_rows:
        cell_id = row["canonical_cell_id"]
        features = row["cell"]
        validate_cell(features, schema)
        if cell_id in features_by_cell and features_by_cell[cell_id] != features:
            raise ValueError(f"legacy development cell has conflicting rows: {cell_id}")
        features_by_cell[cell_id] = features
    items = [
        {
            "item_id": row["measurement_opportunity_id"],
            "cell_id": row["canonical_cell_id"],
        }
        for row in development_rows
    ]
    if len(features_by_cell) != 16 or len(items) != 30:
        raise ValueError(
            "Phase 3 expects the audited 16-cell/30-opportunity development bank"
        )
    if len({row["item_id"] for row in items}) != len(items):
        raise ValueError("legacy development measurement-opportunity IDs are not unique")
    cells = [
        {"cell_id": cell_id, "features": features_by_cell[cell_id]}
        for cell_id in sorted(features_by_cell)
    ]
    fold = [
        {
            "cell_id": row["cell_id"],
            "features": row["features"],
            "grammar_split": "development",
        }
        for row in cells
    ]
    return cells, items, fold


def _selection_design() -> dict[str, Any]:
    return read_yaml(ROOT / "modules/kcs/selection.yaml")


def _selected_ids(policy: dict[str, Any]) -> list[str]:
    return policy["selection_metadata"]["selected_candidate_ids"]


def _policy_ids(inventory: dict[str, Any]) -> dict[str, list[str]]:
    candidates = inventory["candidates"]
    factorized = sorted(
        row["id"]
        for row in candidates
        if row["family"] == "feature_value" and row["selection_eligible"]
    )
    full_cell = sorted(
        row["id"] for row in candidates if row["family"] == "full_cell"
    )
    eligible_additions = sorted(
        row["id"]
        for row in candidates
        if row["family"] in {"operation", "interaction"}
        and row["selection_eligible"]
    )
    candidate_ids = {row["id"] for row in candidates}
    if TRUE_INTERACTION_ID not in candidate_ids:
        raise ValueError("the declared interaction probe is absent from candidates")
    return {
        "factorized": factorized,
        "full_cell": full_cell,
        "manual_true_interaction": sorted([*factorized, TRUE_INTERACTION_ID]),
        "all_eligible": sorted([*factorized, *eligible_additions]),
    }


def _test_predictions(
    predictions: list[dict[str, Any]], test_ids: set[str]
) -> list[dict[str, Any]]:
    return [row for row in predictions if row["event_id"] in test_ids]


def _representation_summary(
    inventory: dict[str, Any], candidate_ids: list[str]
) -> dict[str, Any]:
    by_id = {row["id"]: row for row in inventory["candidates"]}
    rows = [by_id[candidate_id] for candidate_id in candidate_ids]
    supports = [row["item_support"] for row in rows]
    assignments = sum(supports)
    item_count = len(inventory["development_item_ids"])
    return {
        "kc_count": len(rows),
        "family_counts": dict(sorted(Counter(row["family"] for row in rows).items())),
        "q_edges": assignments,
        "q_matrix_density": (
            assignments / (item_count * len(rows)) if item_count and rows else 0.0
        ),
        "mean_kcs_per_item": assignments / item_count if item_count else 0.0,
        "support": {
            "minimum": min(supports) if supports else None,
            "median": median(supports) if supports else None,
            "mean": mean(supports) if supports else None,
            "maximum": max(supports) if supports else None,
        },
    }


def _score_policies(
    inventory: dict[str, Any],
    events: list[dict[str, Any]],
    policies: dict[str, list[str]],
    model_design: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    train_ids = {
        row["event_id"] for row in events if row["dataset_split"] == "train"
    }
    test_ids = {
        row["event_id"] for row in events if row["dataset_split"] == "test"
    }
    metrics = {}
    test_predictions = {}
    for name, candidate_ids in policies.items():
        score, predictions = score_candidate_policy(
            inventory,
            events,
            candidate_ids,
            model_design,
            train_ids,
            test_ids,
        )
        metrics[name] = {
            **score,
            **_representation_summary(inventory, candidate_ids),
            "candidate_ids": candidate_ids,
        }
        test_predictions[name] = _test_predictions(predictions, test_ids)
    return metrics, test_predictions


def _paired_comparisons(
    events: list[dict[str, Any]],
    predictions: dict[str, list[dict[str, Any]]],
    *,
    repeats: int,
    seed: int,
) -> dict[str, Any]:
    test_events = [row for row in events if row["dataset_split"] == "test"]
    pairs = [
        ("factorized", "automated"),
        ("factorized", "manual_true_interaction"),
        ("full_cell", "automated"),
        ("manual_true_interaction", "automated"),
    ]
    return {
        f"{candidate}_minus_{reference}": paired_policy_bootstrap(
            test_events,
            predictions[reference],
            predictions[candidate],
            repeats=repeats,
            seed=seed,
            reference_policy_id=reference,
            candidate_policy_id=candidate,
        )
        for reference, candidate in pairs
    }


def _lambda_sensitivity(
    inventory: dict[str, Any],
    events: list[dict[str, Any]],
    design: dict[str, Any],
    values: tuple[float, ...],
) -> list[dict[str, Any]]:
    output = []
    for penalty in values:
        changed = copy.deepcopy(design)
        changed["selection_id"] = f"phase3_lambda_{penalty:g}"
        changed["objective"]["complexity_penalty"] = penalty
        policy = select_kcs(inventory, events, changed)
        metrics, _predictions = _score_policies(
            inventory,
            events,
            {"selected": _selected_ids(policy)},
            design["selector_model"],
        )
        output.append(
            {
                "complexity_penalty": penalty,
                "selected_candidate_ids": _selected_ids(policy),
                "selection_validation": policy["selection_metadata"][
                    "final_validation_score"
                ],
                "reserved_test": metrics["selected"],
                "trace": policy["selection_metadata"]["trace"],
            }
        )
    return output


def _split_sensitivity(
    inventory: dict[str, Any],
    events: list[dict[str, Any]],
    design: dict[str, Any],
) -> dict[str, Any]:
    learner_design = copy.deepcopy(design)
    learner_design["selection_id"] = "phase3_learner_split_sensitivity"
    learner_design["selection_split"] = {
        "mode": "learner",
        "source_dataset_splits": ["train", "validation"],
        "validation_fraction": 0.25,
        "random_seed": 20260827,
    }
    policy = select_kcs(inventory, events, learner_design)
    metrics, _predictions = _score_policies(
        inventory,
        events,
        {"learner_split_selected": _selected_ids(policy)},
        design["selector_model"],
    )
    return {
        "selected_candidate_ids": _selected_ids(policy),
        "selection_metadata": policy["selection_metadata"],
        "reserved_test": metrics["learner_split_selected"],
    }


def _model_sensitivity(
    inventory: dict[str, Any],
    events: list[dict[str, Any]],
    design: dict[str, Any],
) -> dict[str, Any]:
    bkt_design = copy.deepcopy(design)
    bkt_design["selection_id"] = "phase3_bkt_selector_sensitivity"
    bkt_design["selector_model"] = {
        "model": "bkt",
        "initial_mastery": 0.25,
        "learn": 0.08,
        "guess": 0.20,
        "slip": 0.10,
    }
    policy = select_kcs(inventory, events, bkt_design)
    logistic_metrics, _predictions = _score_policies(
        inventory,
        events,
        {"bkt_selected": _selected_ids(policy)},
        design["selector_model"],
    )
    bkt_metrics, _predictions = _score_policies(
        inventory,
        events,
        {"bkt_selected": _selected_ids(policy)},
        bkt_design["selector_model"],
    )
    return {
        "selected_candidate_ids": _selected_ids(policy),
        "selection_metadata": policy["selection_metadata"],
        "reserved_test_scored_with_primary_logistic": logistic_metrics[
            "bkt_selected"
        ],
        "reserved_test_scored_with_bkt": bkt_metrics["bkt_selected"],
    }


def _regularization_sensitivity(
    inventory: dict[str, Any],
    events: list[dict[str, Any]],
    design: dict[str, Any],
) -> list[dict[str, Any]]:
    output = []
    for regularization_c in (0.1, 1.0, 10.0):
        changed = copy.deepcopy(design)
        changed["selection_id"] = f"phase3_logistic_c_{regularization_c:g}"
        changed["selector_model"]["regularization_c"] = regularization_c
        policy = select_kcs(inventory, events, changed)
        metrics, _predictions = _score_policies(
            inventory,
            events,
            {"selected": _selected_ids(policy)},
            changed["selector_model"],
        )
        output.append(
            {
                "regularization_c": regularization_c,
                "selected_candidate_ids": _selected_ids(policy),
                "selection_validation": policy["selection_metadata"][
                    "final_validation_score"
                ],
                "reserved_test": metrics["selected"],
            }
        )
    return output


def _residual_guided_diagnostic(
    inventory: dict[str, Any],
    events: list[dict[str, Any]],
    design: dict[str, Any],
) -> dict[str, Any]:
    """Propose additions from train residuals, then select on validation."""

    policies = _policy_ids(inventory)
    factorized = policies["factorized"]
    train_ids = {
        row["event_id"] for row in events if row["dataset_split"] == "train"
    }
    proposal_events = [row for row in events if row["dataset_split"] == "train"]
    predictions = fit_predict_kc_logistic(
        inventory,
        events,
        factorized,
        design["selector_model"],
        train_ids,
    )
    probability = {row["event_id"]: row["probability"] for row in predictions}
    ranked = []
    for candidate in inventory["candidates"]:
        if candidate["family"] not in {"operation", "interaction"}:
            continue
        if not candidate["selection_eligible"]:
            continue
        active_items = set(candidate["supporting_development_item_ids"])
        active = [
            row["correct"] - probability[row["event_id"]]
            for row in proposal_events
            if row["item_id"] in active_items
        ]
        inactive = [
            row["correct"] - probability[row["event_id"]]
            for row in proposal_events
            if row["item_id"] not in active_items
        ]
        contrast = mean(active) - mean(inactive)
        ranked.append(
            {
                "candidate_id": candidate["id"],
                "active_residual_mean": mean(active),
                "inactive_residual_mean": mean(inactive),
                "residual_contrast": contrast,
                "absolute_contrast": abs(contrast),
            }
        )
    ranked.sort(key=lambda row: (-row["absolute_contrast"], row["candidate_id"]))
    shortlisted = {row["candidate_id"] for row in ranked[:3]}
    restricted = copy.deepcopy(inventory)
    for candidate in restricted["candidates"]:
        if candidate["family"] in {"operation", "interaction"}:
            candidate["selection_eligible"] = bool(
                candidate["selection_eligible"] and candidate["id"] in shortlisted
            )
    restricted_design = copy.deepcopy(design)
    restricted_design["selection_id"] = "phase3_residual_shortlist_diagnostic"
    policy = select_kcs(restricted, events, restricted_design)
    metrics, _predictions = _score_policies(
        inventory,
        events,
        {"residual_guided": _selected_ids(policy)},
        design["selector_model"],
    )
    return {
        "method": (
            "absolute active-minus-inactive train residual contrast; top 3 "
            "then the unchanged validation predictive/parsimony selector"
        ),
        "ranking": ranked,
        "shortlisted_candidate_ids": sorted(shortlisted),
        "selected_candidate_ids": _selected_ids(policy),
        "selection_metadata": policy["selection_metadata"],
        "reserved_test": metrics["residual_guided"],
    }


def _top_down_abstraction_diagnostic(
    inventory: dict[str, Any],
    events: list[dict[str, Any]],
    design: dict[str, Any],
) -> dict[str, Any]:
    """Small reverse-direction diagnostic, not a retained merge algorithm."""

    policies = _policy_ids(inventory)
    selected_events = [
        row for row in events if row["dataset_split"] in {"train", "validation"}
    ]
    train_ids = {
        row["event_id"] for row in selected_events if row["dataset_split"] == "train"
    }
    validation_ids = {
        row["event_id"]
        for row in selected_events
        if row["dataset_split"] == "validation"
    }
    penalty = float(design["objective"]["complexity_penalty"])
    scores = {}
    for name in ("full_cell", "factorized"):
        metrics, _predictions = score_candidate_policy(
            inventory,
            selected_events,
            policies[name],
            design["selector_model"],
            train_ids,
            validation_ids,
        )
        scores[name] = {
            **metrics,
            "kc_count": len(policies[name]),
            "objective": metrics["log_loss"] + penalty * len(policies[name]),
        }
    return {
        "scope": (
            "single full-cell-versus-factorized abstraction check; no generic "
            "top-down merging implementation"
        ),
        "scores": scores,
        "preferred_extreme": min(scores, key=lambda name: scores[name]["objective"]),
    }


def _selection_stability(runs: list[dict[str, Any]]) -> dict[str, Any]:
    selections = [set(row["selected_candidate_ids"]) for row in runs]
    pairwise_jaccard = []
    for left_index, left in enumerate(selections):
        for right in selections[left_index + 1 :]:
            pairwise_jaccard.append(
                len(left & right) / len(left | right) if left | right else 1.0
            )
    interaction_frequency = Counter(
        candidate_id
        for selected in selections
        for candidate_id in selected
        if candidate_id.startswith("kc_interaction__")
    )
    return {
        "seeds": [row["seed"] for row in runs],
        "selected_kc_counts": [len(row["selected_candidate_ids"]) for row in runs],
        "pairwise_jaccard": pairwise_jaccard,
        "mean_pairwise_jaccard": mean(pairwise_jaccard) if pairwise_jaccard else None,
        "interaction_selection_frequency": dict(sorted(interaction_frequency.items())),
        "true_interaction_frequency": interaction_frequency[TRUE_INTERACTION_ID],
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Software verification: 24 learners, 3 passes, one seed, short grid.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Override the retained-artifact directory.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    quick = bool(args.quick)
    if args.output_dir is None:
        output = ROOT / "reports/phase3/artifacts" / (
            "quick_verification" if quick else "selection_study_v1"
        )
    else:
        output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)

    schema = read_yaml(ROOT / "modules/grammar/canonical/schema.yaml")
    cells, items, fold = _development_structure(schema)
    inventory = make_kc_candidates(
        schema, cells, items, _candidate_design()
    )
    design = _selection_design()
    policies = _policy_ids(inventory)
    seeds = (SEEDS[0],) if quick else SEEDS
    lambda_values = (0.0, 0.002, 0.01) if quick else LAMBDA_GRID
    bootstrap_repeats = 200 if quick else 3000
    learner_count = 24 if quick else 300
    pass_count = 3 if quick else 8

    write_json(output / "candidate_inventory.json", inventory)
    study_design = {
        "experiment_id": "P3-KC-SELECTION-001",
        "evidence_status": "software_verification" if quick else "scientific_run",
        "legacy_artifact": str(LEGACY_PATH.relative_to(ROOT)),
        "legacy_artifact_sha256": _sha256_file(LEGACY_PATH),
        "legacy_fields_used": [
            "canonical_split",
            "canonical_cell_id",
            "cell",
            "measurement_opportunity_id",
        ],
        "legacy_evidence_explicitly_not_used": [
            "expected_operations",
            "structural_conditions",
            "post_training_split",
            "source_descriptor_ids",
            "coverage_reasons",
            "item_format",
            "legacy KCs",
            "legacy learner outcomes",
        ],
        "development_cells": len(cells),
        "development_measurement_opportunities": len(items),
        "world_files": [str(path.relative_to(ROOT)) for path in WORLD_PATHS],
        "world_file_sha256": {
            str(path.relative_to(ROOT)): _sha256_file(path) for path in WORLD_PATHS
        },
        "candidate_design_file": "modules/kcs/candidate_design.yaml",
        "selection_design_file": "modules/kcs/selection.yaml",
        "seeds": list(seeds),
        "learners": learner_count,
        "passes": pass_count,
        "events_per_world_seed": learner_count * pass_count * len(items),
        "lambda_grid": list(lambda_values),
        "paired_bootstrap_repeats": bootstrap_repeats,
        "primary_selector": design["selector_model"],
        "primary_selection_split": design["selection_split"],
        "reserved_test_outcomes_read_by_selection": False,
        "exact_command": (
            "python scripts/run_kc_selection_experiments.py --quick"
            if quick
            else "python scripts/run_kc_selection_experiments.py"
        ),
    }
    write_json(output / "study_design.json", study_design)

    world_runs: dict[str, list[dict[str, Any]]] = {}
    detailed_results = {}
    for world_path in WORLD_PATHS:
        declared_world = materialize_latent_world(
            read_yaml(world_path), schema, cells
        )
        world_id = declared_world["world_id"]
        print(f"Phase 3 world: {world_id}", flush=True)
        world_runs[world_id] = []
        for seed in seeds:
            print(f"  simulate/select seed {seed}", flush=True)
            world = copy.deepcopy(declared_world)
            world["seed"] = seed
            world["learners"] = learner_count
            world["passes"] = pass_count
            oracle_raw = output / "oracles" / f"{world_id}__seed_{seed}.json"
            events = simulate(items, fold, world, oracle_path=oracle_raw)
            expected_events = learner_count * pass_count * len(items)
            if len(events) != expected_events:
                raise ValueError("simulator produced an unexpected event count")
            if {row["item_id"] for row in events} != {row["item_id"] for row in items}:
                raise ValueError("simulator event bank differs from the fixed item bank")
            oracle_document = json.loads(oracle_raw.read_text(encoding="utf-8"))
            probability_by_event = {
                row["event_id"]: row["response_probability"]
                for row in oracle_document["events"]
            }
            target_items = set(
                next(
                    row["supporting_development_item_ids"]
                    for row in inventory["candidates"]
                    if row["id"] == TRUE_INTERACTION_ID
                )
            )
            target_probabilities = [
                probability_by_event[row["event_id"]]
                for row in events
                if row["item_id"] in target_items
            ]
            other_probabilities = [
                probability_by_event[row["event_id"]]
                for row in events
                if row["item_id"] not in target_items
            ]
            oracle_manipulation_check = {
                "scope": "private data-generating check; never supplied to selection",
                "target_event_count": len(target_probabilities),
                "other_event_count": len(other_probabilities),
                "target_mean_response_probability": mean(target_probabilities),
                "other_mean_response_probability": mean(other_probabilities),
                "target_minus_other": mean(target_probabilities)
                - mean(other_probabilities),
            }
            event_path = output / "events" / f"{world_id}__seed_{seed}.jsonl.gz"
            retained_event_sha = _write_jsonl_gzip(event_path, events)
            oracle_hashes = _gzip_file(
                oracle_raw, oracle_raw.with_suffix(".json.gz")
            )

            selected = select_kcs(inventory, events, design)
            active_policies = {
                **policies,
                "automated": _selected_ids(selected),
            }
            metrics, test_predictions = _score_policies(
                inventory,
                events,
                active_policies,
                design["selector_model"],
            )
            run = {
                "world_id": world_id,
                "seed": seed,
                "event_count": len(events),
                "event_split_counts": dict(
                    sorted(Counter(row["dataset_split"] for row in events).items())
                ),
                "event_artifact": _artifact_path(event_path),
                "event_logical_sha256": _rows_digest(events),
                "retained_event_gzip_sha256": retained_event_sha,
                "oracle_artifact": _artifact_path(
                    oracle_raw.with_suffix(".json.gz")
                ),
                "oracle_hashes": oracle_hashes,
                "oracle_manipulation_check": oracle_manipulation_check,
                "selection_artifact": _artifact_path(
                    output
                    / "selections"
                    / f"{world_id}__seed_{seed}.json"
                ),
                "selected_candidate_ids": _selected_ids(selected),
                "selection_final_validation": selected["selection_metadata"][
                    "final_validation_score"
                ],
                "reserved_test_policy_metrics": metrics,
            }
            world_runs[world_id].append(run)
            write_json(
                output / "selections" / f"{world_id}__seed_{seed}.json",
                selected,
            )

            if seed == seeds[0]:
                prediction_rows = [
                    {**row, "policy": name}
                    for name, rows in test_predictions.items()
                    for row in rows
                ]
                prediction_hash = _write_jsonl_gzip(
                    output / "predictions" / f"{world_id}__seed_{seed}.jsonl.gz",
                    prediction_rows,
                )
                prediction_path = (
                    output
                    / "predictions"
                    / f"{world_id}__seed_{seed}.jsonl.gz"
                )
                detailed_results[world_id] = {
                    "seed": seed,
                    "lambda_sensitivity": _lambda_sensitivity(
                        inventory, events, design, lambda_values
                    ),
                    "selection_split_sensitivity": _split_sensitivity(
                        inventory, events, design
                    ),
                    "selector_model_sensitivity": _model_sensitivity(
                        inventory, events, design
                    ),
                    "regularization_sensitivity": _regularization_sensitivity(
                        inventory, events, design
                    ),
                    "residual_guided_diagnostic": _residual_guided_diagnostic(
                        inventory, events, design
                    ),
                    "top_down_abstraction_diagnostic": (
                        _top_down_abstraction_diagnostic(inventory, events, design)
                    ),
                    "paired_learner_bootstrap": _paired_comparisons(
                        events,
                        test_predictions,
                        repeats=bootstrap_repeats,
                        seed=seed,
                    ),
                    "test_prediction_artifact": _artifact_path(prediction_path),
                    "retained_test_prediction_gzip_sha256": prediction_hash,
                }

    results = {
        "experiment_id": "P3-KC-SELECTION-001",
        "evidence_status": study_design["evidence_status"],
        "study_design": study_design,
        "candidate_counts": inventory["candidate_counts"],
        "declared_policy_extremes": {
            name: {
                "candidate_ids": candidate_ids,
                **_representation_summary(inventory, candidate_ids),
            }
            for name, candidate_ids in policies.items()
        },
        "world_runs": world_runs,
        "selection_stability": {
            world_id: _selection_stability(runs)
            for world_id, runs in world_runs.items()
        },
        "reference_seed_diagnostics": detailed_results,
        "interpretation_boundary": (
            "World-relative synthetic recovery evidence only; no human learner "
            "or grammar-holdout/compositional-transfer claim is supported."
        ),
    }
    write_json(output / "results.json", results)
    print(f"Wrote {output / 'results.json'}", flush=True)


if __name__ == "__main__":
    main()
