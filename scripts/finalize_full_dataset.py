#!/usr/bin/env python3
"""Finalize a fixed grammar item bank through KC selection and KT evaluation."""

from __future__ import annotations

import argparse
import copy
import gzip
import json
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from grammar_kt.evaluate import evaluate, paired_policy_bootstrap
from grammar_kt.fold import build_semantic_fold
from grammar_kt.io import (
    read_jsonl,
    read_yaml,
    write_json,
    write_jsonl,
    write_yaml,
)
from grammar_kt.kc import project_kcs, write_q_matrix
from grammar_kt.kc_candidates import make_kc_candidates
from grammar_kt.kc_selection import select_kcs
from grammar_kt.kt import run_kt
from grammar_kt.simulate import materialize_latent_world, simulate_frozen_probes


GRAMMAR_SCHEMA_PATH = ROOT / "modules/grammar/canonical/schema.yaml"
OPERATIONS_PATH = ROOT / "modules/grammar/canonical/english_operations.yaml"
FOLD_DESIGN_PATH = ROOT / "modules/simulation/folds/semantic.yaml"
WORLD_PATH = ROOT / "modules/simulation/worlds/phase4_mixed.yaml"
SIMULATION_PROTOCOL_PATH = ROOT / "modules/simulation/protocol.yaml"
CANDIDATE_DESIGN_PATH = ROOT / "modules/kcs/candidate_design.yaml"
SELECTION_DESIGN_PATH = ROOT / "modules/kcs/selection.yaml"
KT_PROTOCOL_PATH = ROOT / "modules/evaluation/kt/protocol.yaml"
EVALUATION_PROTOCOL_PATH = ROOT / "modules/evaluation/protocol.yaml"

DEFAULT_DATASET = ROOT / "data/grammar_kt_medium_v1"
DEFAULT_LEARNERS = 1000
DEFAULT_SEED = 20260827
DEFAULT_BOOTSTRAP_REPEATS = 5000
GRAMMAR_REGIMES = (
    "development",
    "compositional_holdout",
    "novel_feature_holdout",
)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_jsonl_gzip(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write large row artifacts deterministically without changing content."""

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


def _gzip_created_json(path: Path) -> Path:
    """Compress one just-created private-oracle JSON artifact deterministically."""

    target = path.with_suffix(path.suffix + ".gz")
    with path.open("rb") as source, target.open("wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as compressed:
            shutil.copyfileobj(source, compressed)
    path.unlink()
    return target


def verify_fixed_bank(dataset_dir: Path) -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    """Fail before downstream writes unless every canonical cell is measured."""

    manifest_path = dataset_dir / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"dataset manifest is absent: {manifest_path}")
    manifest = _read_json(manifest_path)
    if manifest.get("status") != "fixed_item_bank_complete":
        raise ValueError(
            "full-dataset finalization requires manifest status "
            f"fixed_item_bank_complete, found {manifest.get('status')!r}"
        )
    cells = read_jsonl(dataset_dir / "canonical/cells.jsonl")
    items = read_jsonl(dataset_dir / "items/selected_bank.jsonl")
    cell_ids = [row["cell_id"] for row in cells]
    if len(cell_ids) != len(set(cell_ids)):
        raise ValueError("canonical cell IDs must be unique")
    support = Counter(row["cell_id"] for row in items)
    unknown = set(support) - set(cell_ids)
    missing = set(cell_ids) - set(support)
    if unknown or missing:
        raise ValueError(
            "fixed item bank must cover every and only canonical cells: "
            f"missing={sorted(missing)}, unknown={sorted(unknown)}"
        )
    item_ids = [row["item_id"] for row in items]
    if len(item_ids) != len(set(item_ids)):
        raise ValueError("fixed bank item IDs must be unique")
    return manifest, cells, items


def _policy_from_candidates(
    inventory: dict[str, Any],
    candidate_ids: list[str],
    *,
    policy_id: str,
    description: str,
) -> dict[str, Any]:
    by_id = {row["id"]: row for row in inventory["candidates"]}
    unknown = set(candidate_ids) - set(by_id)
    if unknown:
        raise ValueError(f"policy contains unknown candidate KCs: {sorted(unknown)}")
    return {
        "policy_id": policy_id,
        "description": description,
        "kcs": [
            {
                "id": candidate_id,
                "definition": by_id[candidate_id]["definition"],
                "activation": by_id[candidate_id]["activation"],
            }
            for candidate_id in sorted(candidate_ids)
        ],
    }


def freeze_comparison_policies(
    inventory: dict[str, Any], automated: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    """Freeze the three observed policies plus a labelled all-cell oracle."""

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
            inventory,
            feature_ids,
            policy_id="medium_v1_factorized",
            description=(
                "Development-observed non-background feature-value KCs; frozen "
                "before grammar-holdout projection."
            ),
        ),
        "supported_interactions": _policy_from_candidates(
            inventory,
            [*feature_ids, *interaction_ids],
            policy_id="medium_v1_factorized_plus_all_supported_interactions",
            description=(
                "Factorized KCs plus every nonredundant pairwise interaction "
                "meeting development support thresholds."
            ),
        ),
        "automated": automated,
        "oracle_all_cell": {
            "policy_id": "medium_v1_oracle_exact_all_cell",
            "description": (
                "Labelled oracle structural extreme with one KC for every exact "
                "cell, including evaluation cells; never available to selection."
            ),
            "kind": "full_cell",
            "kc_id_pattern": "kc_oracle_cell__{cell_id}",
        },
    }


def _logistic_predictions(
    predictions: list[dict[str, Any]], event_ids: set[str]
) -> list[dict[str, Any]]:
    return [
        {"event_id": row["event_id"], "probability": row["probability"]}
        for row in predictions
        if row["technique"] == "logistic" and row["event_id"] in event_ids
    ]


def paired_logistic_comparisons(
    events: list[dict[str, Any]],
    predictions: dict[str, list[dict[str, Any]]],
    *,
    repeats: int,
    seed: int,
) -> dict[str, Any]:
    """Compare representations with logistic KT fixed and learners paired."""

    rows = []
    for regime in ("all_test", *GRAMMAR_REGIMES):
        selected_events = [
            row
            for row in events
            if row["dataset_split"] == "test"
            and (regime == "all_test" or row["grammar_split"] == regime)
        ]
        event_ids = {row["event_id"] for row in selected_events}
        reference = _logistic_predictions(predictions["factorized"], event_ids)
        for candidate in (
            "supported_interactions",
            "automated",
            "oracle_all_cell",
        ):
            rows.append(
                {
                    "grammar_regime": regime,
                    "reference": "factorized",
                    "candidate": candidate,
                    **paired_policy_bootstrap(
                        selected_events,
                        reference,
                        _logistic_predictions(predictions[candidate], event_ids),
                        repeats=repeats,
                        seed=seed,
                        reference_policy_id="factorized",
                        candidate_policy_id=candidate,
                    ),
                }
            )
    return {
        "method": "learner_cluster_paired_bootstrap",
        "fixed_kt_method": "logistic",
        "repeats": repeats,
        "seed": seed,
        "comparisons": rows,
    }


def finalize_dataset(
    dataset_dir: Path,
    *,
    learners: int = DEFAULT_LEARNERS,
    seed: int = DEFAULT_SEED,
    bootstrap_repeats: int = DEFAULT_BOOTSTRAP_REPEATS,
    exact_command: str = "direct Python call",
) -> dict[str, Any]:
    """Run the frozen bank through the linear downstream methodology."""

    if learners < 2:
        raise ValueError("final simulation requires at least two learners")
    if bootstrap_repeats < 1:
        raise ValueError("paired bootstrap repeats must be positive")
    dataset_dir = dataset_dir.resolve()
    input_manifest, cells, items = verify_fixed_bank(dataset_dir)
    correction = input_manifest.get("item_packaging_correction")
    if correction:
        if correction.get("status") != "complete":
            raise ValueError("item packaging correction is not complete")
        candidate_path = dataset_dir / "items/curated_candidates.jsonl"
        judgment_path = dataset_dir / "items/curated_validation.jsonl"
    else:
        candidate_path = dataset_dir / "items/candidates.jsonl"
        judgment_path = dataset_dir / "items/validation.jsonl"
    candidates = read_jsonl(candidate_path)
    judgments = read_jsonl(judgment_path)
    validator_accepted = read_jsonl(
        dataset_dir / "items/validator_accepted.jsonl"
    )

    grammar_schema = read_yaml(GRAMMAR_SCHEMA_PATH)
    fold_design = read_yaml(FOLD_DESIGN_PATH)
    candidate_design = read_yaml(CANDIDATE_DESIGN_PATH) | {
        "operation_declarations": read_yaml(OPERATIONS_PATH)["operations"]
    }
    selection_design = read_yaml(SELECTION_DESIGN_PATH)
    simulation_protocol = read_yaml(SIMULATION_PROTOCOL_PATH)
    kt_protocol = read_yaml(KT_PROTOCOL_PATH)
    evaluation_protocol = read_yaml(EVALUATION_PROTOCOL_PATH)
    if set(kt_protocol["techniques"]) != {"empirical", "bkt", "logistic"}:
        raise ValueError("final KT protocol must contain empirical, BKT, and logistic")
    if kt_protocol["logistic"]["include_item_difficulty"]:
        raise ValueError("primary logistic KT cannot use simulator difficulty")
    if kt_protocol["logistic"]["include_kc_count"]:
        raise ValueError("primary logistic KT cannot use KC count")

    # 1. Outcome-free grammar fold over the fixed selected bank.
    fold = build_semantic_fold(grammar_schema, cells, items, fold_design)
    write_jsonl(dataset_dir / "fold/assignments.jsonl", fold)
    split_by_cell = {row["cell_id"]: row["grammar_split"] for row in fold}
    development_cells = [
        row for row in cells if split_by_cell[row["cell_id"]] == "development"
    ]
    development_items = [
        row for row in items if split_by_cell[row["cell_id"]] == "development"
    ]

    # 2. Structural hypotheses see development GrammarCells and items only.
    inventory = make_kc_candidates(
        grammar_schema,
        development_cells,
        development_items,
        candidate_design,
    )
    write_json(dataset_dir / "kc/candidate_inventory.json", inventory)

    # 3. Simulate one fixed mixed-world event stream before selecting policies.
    declared_world = copy.deepcopy(read_yaml(WORLD_PATH))
    declared_world["learners"] = learners
    declared_world["seed"] = seed
    world = materialize_latent_world(declared_world, grammar_schema, cells)
    write_yaml(dataset_dir / "simulation/materialized_world.yaml", world)
    oracle_path = dataset_dir / "simulation/oracle_debug.json"
    events = simulate_frozen_probes(
        items,
        fold,
        world,
        simulation_protocol,
        oracle_path=oracle_path,
    )
    _gzip_created_json(oracle_path)
    _write_jsonl_gzip(dataset_dir / "simulation/events.jsonl.gz", events)

    # 4. Select only from development acquisition train/validation evidence.
    development_item_ids = {row["item_id"] for row in development_items}
    development_events = [
        row
        for row in events
        if row["item_id"] in development_item_ids
        and row["dataset_split"] in {"train", "validation"}
    ]
    automated = select_kcs(inventory, development_events, selection_design)
    if automated["selection_metadata"]["held_out_grammar_read"]:
        raise AssertionError("automated selection read held-out grammar")
    if automated["selection_metadata"]["reserved_or_holdout_outcomes_read"]:
        raise AssertionError("automated selection read reserved outcomes")
    policies = freeze_comparison_policies(inventory, automated)
    for name, policy in policies.items():
        write_yaml(dataset_dir / "kc/policies" / f"{name}.yaml", policy)
    write_json(
        dataset_dir / "kc/selection_trace.json",
        automated["selection_metadata"],
    )

    # 5. Project, run all three KT baselines on identical events, and evaluate.
    predictions_by_policy: dict[str, list[dict[str, Any]]] = {}
    evaluation_by_policy: dict[str, dict[str, Any]] = {}
    for name, policy in policies.items():
        projection = project_kcs(items, cells, policy)
        projection_path = dataset_dir / "kc/projections" / f"{name}.jsonl"
        write_jsonl(projection_path, projection)
        write_q_matrix(dataset_dir / "kc/q_matrices" / f"{name}.csv", projection)
        predictions = run_kt(events, projection, kt_protocol)
        predictions_by_policy[name] = predictions
        _write_jsonl_gzip(
            dataset_dir / "kt" / name / "predictions.jsonl.gz", predictions
        )
        results = evaluate(
            candidates,
            judgments,
            items,
            cells,
            fold,
            events,
            policy,
            projection,
            predictions,
            evaluation_protocol,
            validator_accepted_items=validator_accepted,
        )
        evaluation_by_policy[name] = results
        write_json(dataset_dir / "evaluation" / name / "results.json", results)

    # 6. Primary inference fixes logistic KT and resamples whole learners.
    paired = paired_logistic_comparisons(
        events,
        predictions_by_policy,
        repeats=bootstrap_repeats,
        seed=seed,
    )
    write_json(dataset_dir / "evaluation/paired_logistic.json", paired)

    split_counts = Counter(row["grammar_split"] for row in fold)
    policy_summary = {
        name: {
            "policy_id": policy["policy_id"],
            "kc_count": evaluation_by_policy[name]["representation"]["kcs"],
            "q_matrix_density": evaluation_by_policy[name]["representation"][
                "q_matrix_density"
            ],
            "logistic_test_log_loss": evaluation_by_policy[name]["kt"][
                "logistic"
            ]["log_loss"],
        }
        for name, policy in policies.items()
    }
    manifest = {
        "dataset_id": input_manifest.get("dataset_id", dataset_dir.name),
        "status": "downstream_finalized",
        "input_bank_status": input_manifest["status"],
        "scale": {
            "cells": len(cells),
            "selected_items": len(items),
            "learners": learners,
            "events": len(events),
            "development_events_supplied_to_selector": len(development_events),
        },
        "grammar_fold": {
            "fold_id": fold_design["fold_id"],
            "cell_counts": dict(sorted(split_counts.items())),
        },
        "simulation": {
            "world_id": world["world_id"],
            "protocol_id": simulation_protocol["protocol_id"],
            "seed": seed,
            "events_are_identical_across_policies": True,
        },
        "kc": {
            "candidate_design_id": inventory["candidate_design_id"],
            "candidate_counts": inventory["candidate_counts"],
            "selection_id": selection_design["selection_id"],
            "complexity_penalty": selection_design["objective"][
                "complexity_penalty"
            ],
            "policies": policy_summary,
        },
        "kt_protocol_id": kt_protocol["protocol_id"],
        "evaluation_protocol_id": evaluation_protocol["protocol_id"],
        "paired_logistic": {
            "repeats": bootstrap_repeats,
            "seed": seed,
            "comparison_count": len(paired["comparisons"]),
        },
        "large_artifact_storage": {
            "events": "simulation/events.jsonl.gz",
            "private_oracle": "simulation/oracle_debug.json.gz",
            "predictions": "kt/{policy}/predictions.jsonl.gz",
            "gzip_mtime": 0,
        },
        "exact_command": exact_command,
    }
    write_json(dataset_dir / "finalization_manifest.json", manifest)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--learners", type=int, default=DEFAULT_LEARNERS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--bootstrap-repeats", type=int, default=DEFAULT_BOOTSTRAP_REPEATS
    )
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    manifest = finalize_dataset(
        arguments.dataset_dir,
        learners=arguments.learners,
        seed=arguments.seed,
        bootstrap_repeats=arguments.bootstrap_repeats,
        exact_command=" ".join([sys.executable, *sys.argv]),
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
