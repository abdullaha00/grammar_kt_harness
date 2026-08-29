#!/usr/bin/env python3
"""Audit latent worlds, acquisition protocols, and simple KT assumptions.

The 24 canonical feature tuples and 42 measurement-opportunity identifiers in
the retained legacy artifact are used only as a fixed structural bank. New
learner events are simulated for every declared world/seed and reused unchanged
across KC representations within each condition.
"""

from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import itertools
import json
import shutil
import sys
from collections import Counter
from pathlib import Path
from statistics import mean, median
from typing import Any, Iterable

import numpy as np
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from grammar_kt.canonicalise import validate_cell
from grammar_kt.evaluate import paired_policy_bootstrap
from grammar_kt.fold import build_semantic_fold
from grammar_kt.io import read_jsonl, read_yaml, write_json, write_jsonl
from grammar_kt.kc import project_kcs
from grammar_kt.kc_candidates import make_kc_candidates
from grammar_kt.kc_selection import select_kcs
from grammar_kt.kt import run_kt
from grammar_kt.simulate import (
    materialize_latent_world,
    simulate,
    simulate_frozen_probes,
)


SOURCE = ROOT / "experiments/post_training_v1/data/pilot_v1/opportunities.jsonl"
WORLD_PATHS = (
    ROOT / "modules/simulation/worlds/phase4_factorized.yaml",
    ROOT / "modules/simulation/worlds/phase4_interaction_heavy.yaml",
    ROOT / "modules/simulation/worlds/phase4_cell_specific.yaml",
    ROOT / "modules/simulation/worlds/phase4_mixed.yaml",
)
SEEDS = (20260827, 20260828, 20260829)
GRAMMAR_SPLITS = (
    "development",
    "compositional_holdout",
    "novel_feature_holdout",
)
PLANTED_INTERACTIONS = {
    "kc_interaction__aspect_perfect__and__polarity_negative",
    "kc_interaction__polarity_negative__and__tense_present",
    "kc_interaction__tense_present__and__voice_passive",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _artifact_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _logical_digest(rows: Iterable[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(
            json.dumps(
                row, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        )
        digest.update(b"\n")
    return digest.hexdigest()


def _write_jsonl_gzip(path: Path, rows: list[dict[str, Any]]) -> dict[str, str]:
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
    return {
        "logical_sha256": _logical_digest(rows),
        "retained_gzip_sha256": _sha256(path),
    }


def _gzip_json(source: Path) -> dict[str, str]:
    target = source.with_suffix(source.suffix + ".gz")
    logical_sha = _sha256(source)
    with source.open("rb") as input_stream, target.open("wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as compressed:
            shutil.copyfileobj(input_stream, compressed)
    source.unlink()
    return {
        "path": _artifact_path(target),
        "logical_sha256": logical_sha,
        "retained_gzip_sha256": _sha256(target),
    }


def _legacy_bank(
    schema: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    rows = read_jsonl(SOURCE)
    features_by_cell: dict[str, dict[str, str]] = {}
    for row in rows:
        cell_id = row["canonical_cell_id"]
        features = row["cell"]
        validate_cell(features, schema)
        if cell_id in features_by_cell and features_by_cell[cell_id] != features:
            raise ValueError(f"legacy cell has conflicting features: {cell_id}")
        features_by_cell[cell_id] = features
    cells = [
        {"cell_id": cell_id, "features": features_by_cell[cell_id]}
        for cell_id in sorted(features_by_cell)
    ]
    items = [
        {
            "item_id": row["measurement_opportunity_id"],
            "cell_id": row["canonical_cell_id"],
        }
        for row in rows
    ]
    if len(cells) != 24 or len(items) != 42:
        raise ValueError("Phase 4 expects the audited 24-cell/42-item bank")
    if len({row["item_id"] for row in items}) != len(items):
        raise ValueError("structural item IDs must be unique")
    return cells, items


def _candidate_design() -> dict[str, Any]:
    design = read_yaml(ROOT / "modules/kcs/candidate_design.yaml")
    operations = read_yaml(
        ROOT / "modules/grammar/canonical/english_operations.yaml"
    )
    return design | {"operation_declarations": operations["operations"]}


def _policy_from_candidates(
    inventory: dict[str, Any], candidate_ids: list[str], policy_id: str
) -> dict[str, Any]:
    by_id = {row["id"]: row for row in inventory["candidates"]}
    return {
        "policy_id": policy_id,
        "description": "Frozen candidate-based Phase-4 comparison policy.",
        "kcs": [
            {
                "id": candidate_id,
                "definition": by_id[candidate_id]["definition"],
                "activation": by_id[candidate_id]["activation"],
            }
            for candidate_id in sorted(candidate_ids)
        ],
    }


def _comparison_policies(
    inventory: dict[str, Any], selected: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    feature_ids = sorted(
        row["id"]
        for row in inventory["candidates"]
        if row["family"] == "feature_value" and row["selection_eligible"]
    )
    interaction_ids = sorted(
        row["id"]
        for row in inventory["candidates"]
        if row["family"] == "interaction" and row["selection_eligible"]
    )
    return {
        "factorized": _policy_from_candidates(
            inventory, feature_ids, "phase4_factorized"
        ),
        "supported_interactions": _policy_from_candidates(
            inventory,
            [*feature_ids, *interaction_ids],
            "phase4_factorized_plus_all_supported_interactions",
        ),
        "automated": selected,
        "oracle_all_cell": {
            "policy_id": "phase4_oracle_exact_all_cell",
            "description": (
                "Labelled oracle structural extreme with one KC for every exact "
                "cell, including evaluation cells; never a selectable policy."
            ),
            "kind": "full_cell",
            "kc_id_pattern": "kc_oracle_cell__{cell_id}",
        },
    }


def _primary_kt_protocol() -> dict[str, Any]:
    protocol = read_yaml(ROOT / "modules/evaluation/kt/protocol.yaml")
    if protocol["logistic"]["include_item_difficulty"]:
        raise ValueError("primary logistic must exclude simulator difficulty")
    if protocol["logistic"]["include_kc_count"]:
        raise ValueError("primary logistic must exclude KC count")
    return protocol


def _control_protocol(
    primary: dict[str, Any], name: str, **changes: Any
) -> dict[str, Any]:
    protocol = copy.deepcopy(primary)
    protocol["techniques"] = [name]
    protocol[name] = {**protocol["logistic"], **changes}
    return protocol


def _binary_metrics(
    events: list[dict[str, Any]], probabilities: dict[str, float]
) -> dict[str, Any]:
    if not events:
        return {
            "n": 0,
            "log_loss": None,
            "brier_score": None,
            "auc": None,
            "accuracy": None,
        }
    targets = np.asarray([row["correct"] for row in events], dtype=float)
    predicted = np.asarray(
        [probabilities[row["event_id"]] for row in events], dtype=float
    )
    predicted = np.clip(predicted, 1e-6, 1 - 1e-6)
    return {
        "n": len(events),
        "log_loss": float(
            np.mean(
                -(
                    targets * np.log(predicted)
                    + (1.0 - targets) * np.log(1.0 - predicted)
                )
            )
        ),
        "brier_score": float(np.mean((predicted - targets) ** 2)),
        "auc": (
            float(roc_auc_score(targets, predicted))
            if len(set(targets.tolist())) > 1
            else None
        ),
        "accuracy": float(np.mean((predicted >= 0.5) == targets)),
    }


def _prediction_metrics(
    events: list[dict[str, Any]], predictions: list[dict[str, Any]]
) -> dict[str, Any]:
    test = [row for row in events if row["dataset_split"] == "test"]
    output = {}
    for technique in sorted({row["technique"] for row in predictions}):
        lookup = {
            row["event_id"]: row["probability"]
            for row in predictions
            if row["technique"] == technique
        }
        output[technique] = {
            "all_test": _binary_metrics(test, lookup),
            "by_grammar_split": {
                split: _binary_metrics(
                    [row for row in test if row["grammar_split"] == split], lookup
                )
                for split in GRAMMAR_SPLITS
            },
        }
    return output


def _representation_summary(
    items: list[dict[str, Any]],
    fold: list[dict[str, Any]],
    events: list[dict[str, Any]],
    projection: list[dict[str, Any]],
) -> dict[str, Any]:
    by_item = {row["item_id"]: row["kc_ids"] for row in projection}
    split_by_cell = {row["cell_id"]: row["grammar_split"] for row in fold}
    split_items = {
        split: [
            row
            for row in items
            if split_by_cell[row["cell_id"]] == split
        ]
        for split in GRAMMAR_SPLITS
    }
    kc_ids = sorted({kc_id for values in by_item.values() for kc_id in values})
    edges = sum(len(values) for values in by_item.values())
    acquisition = [
        row
        for row in events
        if row["dataset_split"] in {"train", "validation"}
    ]
    update_counts = [len(by_item[row["item_id"]]) for row in acquisition]
    return {
        "kc_count": len(kc_ids),
        "q_edges": edges,
        "q_density": edges / (len(items) * len(kc_ids)) if kc_ids else 0.0,
        "mean_kcs_per_item": edges / len(items),
        "primary_logistic_feature_columns": 3 + len(kc_ids),
        "item_coverage_by_grammar_split": {
            split: (
                sum(bool(by_item[row["item_id"]]) for row in rows) / len(rows)
                if rows
                else None
            )
            for split, rows in split_items.items()
        },
        "bkt_full_credit_updates_per_acquisition_event": {
            "minimum": min(update_counts) if update_counts else None,
            "median": median(update_counts) if update_counts else None,
            "mean": mean(update_counts) if update_counts else None,
            "maximum": max(update_counts) if update_counts else None,
        },
    }


def _test_predictions(
    predictions: list[dict[str, Any]], technique: str, event_ids: set[str]
) -> list[dict[str, Any]]:
    return [
        {"event_id": row["event_id"], "probability": row["probability"]}
        for row in predictions
        if row["technique"] == technique and row["event_id"] in event_ids
    ]


def _paired_representations(
    events: list[dict[str, Any]],
    predictions: dict[str, list[dict[str, Any]]],
    repeats: int,
    seed: int,
) -> dict[str, Any]:
    output = {}
    for split in ("all", *GRAMMAR_SPLITS):
        selected_events = [
            row
            for row in events
            if row["dataset_split"] == "test"
            and (split == "all" or row["grammar_split"] == split)
        ]
        event_ids = {row["event_id"] for row in selected_events}
        output[split] = {}
        for candidate in (
            "supported_interactions",
            "automated",
            "oracle_all_cell",
        ):
            output[split][f"{candidate}_minus_factorized"] = (
                paired_policy_bootstrap(
                    selected_events,
                    _test_predictions(
                        predictions["factorized"], "logistic", event_ids
                    ),
                    _test_predictions(predictions[candidate], "logistic", event_ids),
                    repeats=repeats,
                    seed=seed,
                    reference_policy_id="factorized",
                    candidate_policy_id=candidate,
                )
            )
    return output


def _oracle_summary(
    events: list[dict[str, Any]], oracle_document: dict[str, Any]
) -> dict[str, Any]:
    probability = {
        row["event_id"]: row["response_probability"]
        for row in oracle_document["events"]
    }
    test = [row for row in events if row["dataset_split"] == "test"]
    return {
        split: {
            "n": len(rows),
            "mean_response_probability": (
                mean(probability[row["event_id"]] for row in rows)
                if rows
                else None
            ),
        }
        for split, rows in {
            "all_test": test,
            **{
                split: [row for row in test if row["grammar_split"] == split]
                for split in GRAMMAR_SPLITS
            },
        }.items()
    }


def _prior_cell_exposure(
    events: list[dict[str, Any]], items: list[dict[str, Any]]
) -> dict[str, Any]:
    cell_by_item = {row["item_id"]: row["cell_id"] for row in items}
    counts: Counter[tuple[str, str]] = Counter()
    values: dict[str, list[int]] = {split: [] for split in GRAMMAR_SPLITS}
    for event in sorted(
        events, key=lambda row: (row["learner_id"], row["sequence_index"])
    ):
        key = (event["learner_id"], cell_by_item[event["item_id"]])
        if event["dataset_split"] == "test":
            values[event["grammar_split"]].append(counts[key])
        if event.get("updates_mastery", True):
            counts[key] += 1
    return {
        split: {
            "n": len(rows),
            "minimum": min(rows) if rows else None,
            "mean": mean(rows) if rows else None,
            "maximum": max(rows) if rows else None,
        }
        for split, rows in values.items()
    }


def _max_prediction_change(
    first: list[dict[str, Any]], second: list[dict[str, Any]]
) -> dict[str, float]:
    left = {
        (row["event_id"], row["technique"]): row["probability"] for row in first
    }
    right = {
        (row["event_id"], row["technique"]): row["probability"] for row in second
    }
    if set(left) != set(right):
        raise ValueError("prediction comparison has different event coverage")
    return {
        technique: max(
            abs(left[key] - right[key])
            for key in left
            if key[1] == technique
        )
        for technique in sorted({key[1] for key in left})
    }


def _probe_update_audit(
    events: list[dict[str, Any]],
    projection: list[dict[str, Any]],
    protocol: dict[str, Any],
    reference_predictions: list[dict[str, Any]],
) -> dict[str, Any]:
    changed = copy.deepcopy(events)
    by_learner: dict[str, list[dict[str, Any]]] = {}
    for row in changed:
        if row.get("protocol_phase") == "probe":
            row["correct"] = 1 - row["correct"]
            by_learner.setdefault(row["learner_id"], []).append(row)
    for rows in by_learner.values():
        sequence_indices = sorted(row["sequence_index"] for row in rows)
        for row, sequence_index in zip(reversed(rows), sequence_indices, strict=True):
            row["sequence_index"] = sequence_index
    repeated = run_kt(changed, projection, protocol)
    changes = _max_prediction_change(reference_predictions, repeated)
    if any(value != 0.0 for value in changes.values()):
        raise AssertionError("non-updating probe outcomes/order changed predictions")
    return {
        "intervention": "flip every probe outcome and reverse probe order per learner",
        "maximum_absolute_prediction_change": changes,
        "invariant": True,
    }


def _duplicate_activation_audit(
    events: list[dict[str, Any]],
    projection: list[dict[str, Any]],
    protocol: dict[str, Any],
    reference_predictions: list[dict[str, Any]],
) -> dict[str, Any]:
    duplicated = [
        {
            **row,
            "kc_ids": [
                value
                for kc_id in row["kc_ids"]
                for value in (kc_id, f"activation_duplicate__{kc_id}")
            ],
        }
        for row in projection
    ]
    repeated = run_kt(events, duplicated, protocol)
    changes = _max_prediction_change(reference_predictions, repeated)
    if changes.get("bkt") != 0.0:
        raise AssertionError("mean shared-credit BKT lost duplicate invariance")
    return {
        "intervention": "duplicate every KC activation column exactly",
        "maximum_absolute_prediction_change": changes,
        "bkt_duplicate_invariant": changes.get("bkt") == 0.0,
        "interpretation": (
            "BKT gives every active KC the full item outcome, so exact state "
            "clones remain clones. Logistic indicators can change because exact "
            "duplicates alter effective L2 regularisation."
        ),
    }


def _regularization_audit(
    events: list[dict[str, Any]],
    projections: dict[str, list[dict[str, Any]]],
    primary: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = []
    for regularization_c in (0.1, 1.0, 10.0):
        protocol = _control_protocol(
            primary,
            "logistic",
            regularization_c=regularization_c,
        )
        for representation, projection in projections.items():
            predictions = run_kt(events, projection, protocol)
            metrics = _prediction_metrics(events, predictions)["logistic"]
            rows.append(
                {
                    "regularization_c": regularization_c,
                    "representation": representation,
                    "metrics": metrics,
                }
            )
    return rows


def _selector_model_audit(
    inventory: dict[str, Any],
    development_events: list[dict[str, Any]],
    selection_design: dict[str, Any],
    logistic_policy: dict[str, Any],
) -> dict[str, Any]:
    changed = copy.deepcopy(selection_design)
    changed["selection_id"] = "phase4_bkt_selector_sensitivity"
    changed["selector_model"] = {
        "model": "bkt",
        "initial_mastery": 0.25,
        "learn": 0.08,
        "guess": 0.20,
        "slip": 0.10,
    }
    bkt_policy = select_kcs(inventory, development_events, changed)
    logistic_ids = set(
        logistic_policy["selection_metadata"]["selected_candidate_ids"]
    )
    bkt_ids = set(bkt_policy["selection_metadata"]["selected_candidate_ids"])
    return {
        "logistic_selected_candidate_ids": sorted(logistic_ids),
        "bkt_selected_candidate_ids": sorted(bkt_ids),
        "jaccard": len(logistic_ids & bkt_ids) / len(logistic_ids | bkt_ids),
        "bkt_selection_policy": bkt_policy,
    }


def _selection_stability(runs: list[dict[str, Any]]) -> dict[str, Any]:
    selections = [set(row["selected_candidate_ids"]) for row in runs]
    similarities = [
        len(left & right) / len(left | right)
        for index, left in enumerate(selections)
        for right in selections[index + 1 :]
    ]
    frequency = Counter(
        candidate_id
        for selected in selections
        for candidate_id in selected
        if candidate_id.startswith("kc_interaction__")
    )
    return {
        "selected_kc_counts": [len(rows) for rows in selections],
        "mean_pairwise_jaccard": mean(similarities) if similarities else None,
        "pairwise_jaccard": similarities,
        "interaction_frequency": dict(sorted(frequency.items())),
    }


def _aggregate(world_runs: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for world_id, runs in world_runs.items():
        world_output: dict[str, Any] = {}
        for protocol_name in ("frozen_probe", "mixed_history"):
            protocol_output: dict[str, Any] = {}
            for representation in (
                "factorized",
                "supported_interactions",
                "automated",
                "oracle_all_cell",
            ):
                representation_output = {}
                for split in ("all_test", *GRAMMAR_SPLITS):
                    metric_rows = []
                    for run in runs:
                        technique = run["protocols"][protocol_name]["metrics"][
                            representation
                        ]["logistic"]
                        metric_rows.append(
                            technique["all_test"]
                            if split == "all_test"
                            else technique["by_grammar_split"][split]
                        )
                    available = [row for row in metric_rows if row["n"]]
                    representation_output[split] = {
                        "events_per_seed": [row["n"] for row in metric_rows],
                        "mean_log_loss": (
                            mean(row["log_loss"] for row in available)
                            if available
                            else None
                        ),
                        "mean_brier_score": (
                            mean(row["brier_score"] for row in available)
                            if available
                            else None
                        ),
                    }
                protocol_output[representation] = representation_output
            world_output[protocol_name] = protocol_output
        output[world_id] = world_output
    return output


def _compact_reference_diagnostics(
    world_runs: dict[str, list[dict[str, Any]]],
    diagnostics: dict[str, Any],
) -> dict[str, Any]:
    output = {}
    for world_id, row in diagnostics.items():
        reference_run = world_runs[world_id][0]
        controls = {}
        for protocol_name in ("frozen_probe", "mixed_history"):
            primary = reference_run["protocols"][protocol_name]["metrics"][
                "factorized"
            ]["logistic"]
            control = row["labelled_logistic_controls_on_factorized"][
                protocol_name
            ]
            controls[protocol_name] = {
                "primary_log_loss": primary["all_test"]["log_loss"],
                "oracle_difficulty_log_loss": control["oracle_difficulty"][
                    "all_test"
                ]["log_loss"],
                "kc_count_log_loss": control["kc_count"]["all_test"][
                    "log_loss"
                ],
            }
        regularization: dict[str, dict[str, float]] = {}
        for setting in row["regularization_sensitivity_frozen_probe"]:
            regularization.setdefault(
                str(setting["regularization_c"]), {}
            )[setting["representation"]] = setting["metrics"]["all_test"][
                "log_loss"
            ]
        paired = row["paired_primary_logistic"]["frozen_probe"]
        output[world_id] = {
            "probe_nonupdate_maximum_change": row[
                "probe_nonupdate_invariance"
            ]["maximum_absolute_prediction_change"],
            "activation_duplicate_maximum_change": row[
                "activation_duplicate_audit"
            ]["maximum_absolute_prediction_change"],
            "selector_model_jaccard": row["selector_model_sensitivity"][
                "jaccard"
            ],
            "mixed_vs_frozen_selection_jaccard": row[
                "mixed_history_selection_diagnostic"
            ]["jaccard"],
            "factorized_logistic_controls": controls,
            "regularization_log_loss": regularization,
            "frozen_probe_paired_log_loss": {
                split: {
                    comparison: {
                        "point_estimate": value.get("delta_log_loss", {}).get(
                            "point_estimate"
                        ),
                        "interval_95": value.get("delta_log_loss", {}).get(
                            "interval_95"
                        ),
                    }
                    for comparison, value in comparisons.items()
                }
                for split, comparisons in paired.items()
            },
        }
    return output


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Software verification: 24 learners and one seed.",
    )
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    quick = bool(args.quick)
    output = (
        args.output_dir.resolve()
        if args.output_dir
        else ROOT
        / "reports/phase4/artifacts/world_kt"
        / ("quick_verification" if quick else "study_v1")
    )
    output.mkdir(parents=True, exist_ok=True)

    schema = read_yaml(ROOT / "modules/grammar/canonical/schema.yaml")
    cells, items = _legacy_bank(schema)
    fold_design = read_yaml(ROOT / "modules/simulation/folds/semantic.yaml")
    fold = build_semantic_fold(schema, cells, items, fold_design)
    development_ids = {
        row["cell_id"]
        for row in fold
        if row["grammar_split"] == "development"
    }
    development_cells = [row for row in cells if row["cell_id"] in development_ids]
    development_items = [row for row in items if row["cell_id"] in development_ids]
    inventory = make_kc_candidates(
        schema, development_cells, development_items, _candidate_design()
    )
    selection_design = read_yaml(ROOT / "modules/kcs/selection.yaml")
    frozen_protocol = read_yaml(ROOT / "modules/simulation/protocol.yaml")
    primary_kt = _primary_kt_protocol()

    write_jsonl(output / "canonical_cells.jsonl", cells)
    write_jsonl(output / "fixed_structural_items.jsonl", items)
    write_jsonl(output / "semantic_fold.jsonl", fold)
    write_json(output / "candidate_inventory.json", inventory)
    seeds = SEEDS[:1] if quick else SEEDS
    learners = 24 if quick else 240
    bootstrap_repeats = 100 if quick else 1000
    study_design = {
        "experiment_id": "P4-WORLD-KT-001",
        "evidence_status": "software_verification" if quick else "scientific_run",
        "date": "2026-08-27",
        "rqs": ["RQ5", "RQ6", "RQ7", "RQ9", "RQ19", "RQ20"],
        "exact_command": (
            ".venv/bin/python scripts/run_phase4_world_audit.py --quick"
            if quick
            else ".venv/bin/python scripts/run_phase4_world_audit.py"
        ),
        "source": str(SOURCE.relative_to(ROOT)),
        "source_sha256": _sha256(SOURCE),
        "legacy_fields_used": [
            "canonical_cell_id",
            "cell",
            "measurement_opportunity_id",
        ],
        "legacy_fields_not_used": [
            "canonical_split",
            "post_training_split",
            "expected_operations",
            "source_descriptor_ids",
            "structural_conditions",
            "legacy learner evidence",
            "legacy KCs",
        ],
        "scale": {
            "cells": len(cells),
            "fixed_structural_items": len(items),
            "development_cells": len(development_cells),
            "development_items": len(development_items),
            "learners_per_world_seed": learners,
            "worlds": len(WORLD_PATHS),
            "seeds": list(seeds),
        },
        "world_files": {
            str(path.relative_to(ROOT)): _sha256(path) for path in WORLD_PATHS
        },
        "fold_design_file": "modules/simulation/folds/semantic.yaml",
        "frozen_protocol_file": "modules/simulation/protocol.yaml",
        "candidate_design_file": "modules/kcs/candidate_design.yaml",
        "selection_design_file": "modules/kcs/selection.yaml",
        "primary_kt_file": "modules/evaluation/kt/protocol.yaml",
        "learner_model": "declared synthetic latent mastery world",
        "kt_models": {
            "empirical": primary_kt["empirical"],
            "bkt": primary_kt["bkt"],
            "logistic": {
                "implementation": "sklearn.linear_model.LogisticRegression",
                **primary_kt["logistic"],
            },
        },
        "primary_logistic_excludes": ["simulator_item_difficulty", "kc_count"],
        "controls": [
            "mixed_history",
            "oracle_difficulty_logistic",
            "kc_count_logistic",
            "regularization_C_0.1_1_10",
            "BKT_selector",
            "activation_duplicate",
            "probe_outcome_and_order_mutation",
        ],
        "paired_bootstrap": {
            "unit": "learner",
            "repeats": bootstrap_repeats,
            "seed": seeds[0],
        },
        "model_calls": None,
    }
    write_json(output / "study_design.json", study_design)

    world_runs: dict[str, list[dict[str, Any]]] = {}
    reference_diagnostics: dict[str, Any] = {}
    for world_path in WORLD_PATHS:
        declared = read_yaml(world_path)
        base_world = materialize_latent_world(declared, schema, cells)
        world_id = base_world["world_id"]
        print(f"Phase 4 world: {world_id}", flush=True)
        write_json(output / "worlds" / f"{world_id}.json", base_world)
        world_runs[world_id] = []
        for seed in seeds:
            print(f"  seed {seed}: simulate", flush=True)
            world = copy.deepcopy(base_world)
            world["seed"] = seed
            world["learners"] = learners

            frozen_oracle_path = output / "oracles" / f"{world_id}__{seed}__frozen.json"
            frozen_events = simulate_frozen_probes(
                items,
                fold,
                world,
                frozen_protocol,
                oracle_path=frozen_oracle_path,
            )
            mixed_oracle_path = output / "oracles" / f"{world_id}__{seed}__mixed.json"
            mixed_events = simulate(
                items, fold, world, oracle_path=mixed_oracle_path
            )
            frozen_oracle = json.loads(frozen_oracle_path.read_text(encoding="utf-8"))
            mixed_oracle = json.loads(mixed_oracle_path.read_text(encoding="utf-8"))

            expected_frozen = learners * (
                frozen_protocol["acquisition_passes"] * len(development_items)
                + frozen_protocol["probe_repeats"] * len(items)
            )
            expected_mixed = learners * world["passes"] * len(items)
            if len(frozen_events) != expected_frozen or len(mixed_events) != expected_mixed:
                raise AssertionError("simulation produced an unexpected event count")
            if {row["item_id"] for row in frozen_events} != {
                row["item_id"] for row in items
            }:
                raise AssertionError("frozen protocol changed the fixed item bank")

            frozen_development_events = [
                row for row in frozen_events if row["grammar_split"] == "development"
            ]
            selected = select_kcs(
                inventory, frozen_development_events, selection_design
            )
            policies = _comparison_policies(inventory, selected)
            projections = {
                name: project_kcs(items, cells, policy)
                for name, policy in policies.items()
            }

            protocol_results = {}
            prediction_sets: dict[str, dict[str, list[dict[str, Any]]]] = {}
            for protocol_name, events, oracle in (
                ("frozen_probe", frozen_events, frozen_oracle),
                ("mixed_history", mixed_events, mixed_oracle),
            ):
                print(f"    {protocol_name}: KT", flush=True)
                policy_predictions = {
                    name: run_kt(events, projection, primary_kt)
                    for name, projection in projections.items()
                }
                prediction_sets[protocol_name] = policy_predictions
                protocol_results[protocol_name] = {
                    "event_count": len(events),
                    "event_split_counts": dict(
                        sorted(Counter(row["dataset_split"] for row in events).items())
                    ),
                    "test_grammar_split_counts": dict(
                        sorted(
                            Counter(
                                row["grammar_split"]
                                for row in events
                                if row["dataset_split"] == "test"
                            ).items()
                        )
                    ),
                    "prior_same_cell_exposure": _prior_cell_exposure(events, items),
                    "oracle_response": _oracle_summary(events, oracle),
                    "representations": {
                        name: _representation_summary(
                            items, fold, events, projection
                        )
                        for name, projection in projections.items()
                    },
                    "metrics": {
                        name: _prediction_metrics(events, predictions)
                        for name, predictions in policy_predictions.items()
                    },
                }

            event_artifacts = {}
            for protocol_name, events in (
                ("frozen_probe", frozen_events),
                ("mixed_history", mixed_events),
            ):
                path = output / "events" / f"{world_id}__{seed}__{protocol_name}.jsonl.gz"
                event_artifacts[protocol_name] = {
                    "path": _artifact_path(path),
                    **_write_jsonl_gzip(path, events),
                }
            oracle_artifacts = {
                "frozen_probe": _gzip_json(frozen_oracle_path),
                "mixed_history": _gzip_json(mixed_oracle_path),
            }
            selection_path = output / "selections" / f"{world_id}__{seed}.json"
            write_json(selection_path, selected)
            run = {
                "seed": seed,
                "selected_candidate_ids": selected["selection_metadata"][
                    "selected_candidate_ids"
                ],
                "selected_interaction_ids": [
                    row
                    for row in selected["selection_metadata"][
                        "selected_candidate_ids"
                    ]
                    if row.startswith("kc_interaction__")
                ],
                "selection_validation": selected["selection_metadata"][
                    "final_validation_score"
                ],
                "selection_artifact": _artifact_path(selection_path),
                "protocols": protocol_results,
                "event_artifacts": event_artifacts,
                "oracle_artifacts": oracle_artifacts,
            }
            world_runs[world_id].append(run)

            if seed == seeds[0]:
                print("    reference-seed diagnostics", flush=True)
                factorized_projection = projections["factorized"]
                oracle_control = _control_protocol(
                    primary_kt,
                    "logistic_oracle_difficulty",
                    include_item_difficulty=True,
                )
                count_control = _control_protocol(
                    primary_kt,
                    "logistic_kc_count_control",
                    include_kc_count=True,
                )
                controls = {}
                for protocol_name, events in (
                    ("frozen_probe", frozen_events),
                    ("mixed_history", mixed_events),
                ):
                    controls[protocol_name] = {
                        "oracle_difficulty": _prediction_metrics(
                            events,
                            run_kt(events, factorized_projection, oracle_control),
                        )["logistic_oracle_difficulty"],
                        "kc_count": _prediction_metrics(
                            events,
                            run_kt(events, factorized_projection, count_control),
                        )["logistic_kc_count_control"],
                    }

                mixed_development_events = [
                    row
                    for row in mixed_events
                    if row["grammar_split"] == "development"
                ]
                mixed_selected = select_kcs(
                    inventory, mixed_development_events, selection_design
                )
                frozen_ids = set(
                    selected["selection_metadata"]["selected_candidate_ids"]
                )
                mixed_ids = set(
                    mixed_selected["selection_metadata"]["selected_candidate_ids"]
                )
                diagnostics = {
                    "paired_primary_logistic": {
                        protocol_name: _paired_representations(
                            events,
                            prediction_sets[protocol_name],
                            bootstrap_repeats,
                            seed,
                        )
                        for protocol_name, events in (
                            ("frozen_probe", frozen_events),
                            ("mixed_history", mixed_events),
                        )
                    },
                    "labelled_logistic_controls_on_factorized": controls,
                    "regularization_sensitivity_frozen_probe": _regularization_audit(
                        frozen_events, projections, primary_kt
                    ),
                    "probe_nonupdate_invariance": _probe_update_audit(
                        frozen_events,
                        factorized_projection,
                        primary_kt,
                        prediction_sets["frozen_probe"]["factorized"],
                    ),
                    "activation_duplicate_audit": _duplicate_activation_audit(
                        frozen_events,
                        factorized_projection,
                        primary_kt,
                        prediction_sets["frozen_probe"]["factorized"],
                    ),
                    "selector_model_sensitivity": _selector_model_audit(
                        inventory,
                        frozen_development_events,
                        selection_design,
                        selected,
                    ),
                    "mixed_history_selection_diagnostic": {
                        "frozen_selected_candidate_ids": sorted(frozen_ids),
                        "mixed_selected_candidate_ids": sorted(mixed_ids),
                        "jaccard": len(frozen_ids & mixed_ids)
                        / len(frozen_ids | mixed_ids),
                        "warning": (
                            "Mixed-history latent states have already been updated "
                            "by holdout grammar even though the selector receives "
                            "only development-labelled rows."
                        ),
                    },
                }
                test_ids_by_protocol = {
                    "frozen_probe": {
                        row["event_id"]
                        for row in frozen_events
                        if row["dataset_split"] == "test"
                    },
                    "mixed_history": {
                        row["event_id"]
                        for row in mixed_events
                        if row["dataset_split"] == "test"
                    },
                }
                prediction_rows = [
                    {
                        **row,
                        "protocol": protocol_name,
                        "representation": representation,
                    }
                    for protocol_name, by_representation in prediction_sets.items()
                    for representation, rows in by_representation.items()
                    for row in rows
                    if row["event_id"] in test_ids_by_protocol[protocol_name]
                ]
                prediction_path = (
                    output / "predictions" / f"{world_id}__{seed}.jsonl.gz"
                )
                diagnostics["prediction_artifact"] = {
                    "path": _artifact_path(prediction_path),
                    **_write_jsonl_gzip(prediction_path, prediction_rows),
                }
                reference_diagnostics[world_id] = diagnostics

    candidate_by_id = {
        row["id"]: row for row in inventory["candidates"]
    }
    planted_audit = {
        candidate_id: (
            {
                "present_in_development_candidates": True,
                "cell_support": candidate_by_id[candidate_id]["cell_support"],
                "item_support": candidate_by_id[candidate_id]["item_support"],
                "selection_eligible": candidate_by_id[candidate_id][
                    "selection_eligible"
                ],
                "exclusion_reasons": candidate_by_id[candidate_id][
                    "exclusion_reasons"
                ],
            }
            if candidate_id in candidate_by_id
            else {"present_in_development_candidates": False}
        )
        for candidate_id in sorted(PLANTED_INTERACTIONS)
    }
    results = {
        "experiment_id": "P4-WORLD-KT-001",
        "evidence_status": study_design["evidence_status"],
        "study_design": study_design,
        "fold_counts": dict(
            sorted(Counter(row["grammar_split"] for row in fold).items())
        ),
        "candidate_counts": inventory["candidate_counts"],
        "interaction_heavy_planted_candidate_audit": planted_audit,
        "world_runs": world_runs,
        "selection_stability": {
            world_id: _selection_stability(runs)
            for world_id, runs in world_runs.items()
        },
        "world_by_representation_primary_logistic": _aggregate(world_runs),
        "reference_seed_diagnostics": reference_diagnostics,
        "interpretation_boundary": (
            "All predictive results concern controlled synthetic learner worlds "
            "over a legacy structural measurement bank. They diagnose protocol "
            "and model assumptions; they are not evidence about human learners."
        ),
    }
    write_json(output / "results.json", results)
    summary = {
        "experiment_id": results["experiment_id"],
        "evidence_status": results["evidence_status"],
        "exact_command": study_design["exact_command"],
        "scale": study_design["scale"],
        "fold_counts": results["fold_counts"],
        "candidate_counts": results["candidate_counts"],
        "planted_candidate_audit": planted_audit,
        "selection_stability": results["selection_stability"],
        "world_by_representation_primary_logistic": results[
            "world_by_representation_primary_logistic"
        ],
        "reference_seed_diagnostics": _compact_reference_diagnostics(
            world_runs, reference_diagnostics
        ),
        "full_results": _artifact_path(output / "results.json"),
    }
    write_json(output / "summary.json", summary)
    print(f"Wrote {output / 'results.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
