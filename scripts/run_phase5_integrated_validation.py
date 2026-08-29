#!/usr/bin/env python3
"""Replay the Phase-4 bank to validate the active KC selector at medium scale.

This experiment deliberately does not regenerate grammar cells, items, or
learner events.  It varies only the number of development learners and the
KC-count penalty seen by ``select_kcs``.  Final representation comparisons use
the already-retained primary-logistic predictions and paired learner-cluster
bootstrap resampling.
"""

from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from grammar_kt.io import read_yaml, write_json
from grammar_kt.kc_selection import select_kcs


PHASE4 = ROOT / "reports/phase4/artifacts/world_kt/study_v1"
DEFAULT_OUTPUT = ROOT / "reports/phase5/artifacts/integrated_validation_v1"
ACTIVE_PENALTY = 0.0005
LEARNER_SIZES = (30, 60, 120, 240)
LAMBDA_GRID = (0.0, 0.00025, 0.0005, 0.001, 0.002)
REFERENCE_SEED = 20260827
BOOTSTRAP_REPEATS = 5000
GRAMMAR_REGIMES = (
    "development",
    "compositional_holdout",
    "novel_feature_holdout",
)
DIAGNOSTIC_WORLDS = (
    "phase4_factorized_v1",
    "phase4_interaction_heavy_v1",
)
RECOVERABLE_PLANTED_INTERACTIONS = {
    "kc_interaction__aspect_perfect__and__polarity_negative",
    "kc_interaction__polarity_negative__and__tense_present",
}


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl_gzip(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


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


def _penalty_slug(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".").replace(".", "p") or "0"


def subset_development_learners(
    events: list[dict[str, Any]], learner_count: int
) -> list[dict[str, Any]]:
    """Return a deterministic nested learner subset containing development only."""

    if learner_count < 2:
        raise ValueError("learner support must include at least two learners")
    learners = sorted({str(row["learner_id"]) for row in events})
    if learner_count > len(learners):
        raise ValueError(
            f"requested {learner_count} learners from a {len(learners)}-learner stream"
        )
    included = set(learners[:learner_count])
    selected = [
        row
        for row in events
        if str(row["learner_id"]) in included
        and row["grammar_split"] == "development"
    ]
    if {str(row["learner_id"]) for row in selected} != included:
        raise ValueError("one or more selected learners has no development evidence")
    if any(row["grammar_split"] != "development" for row in selected):
        raise AssertionError("learner subset leaked holdout grammar")
    return selected


def _pairwise_jaccard(sets: list[set[str]]) -> dict[str, Any]:
    values = []
    for index, left in enumerate(sets):
        for right in sets[index + 1 :]:
            union = left | right
            values.append(len(left & right) / len(union) if union else 1.0)
    return {
        "values": values,
        "mean": mean(values) if values else None,
    }


def _selection_record(
    policy: dict[str, Any],
    *,
    world_id: str,
    simulation_seed: int,
    learner_count: int,
    complexity_penalty: float,
    source: Path,
    artifact: Path,
) -> dict[str, Any]:
    metadata = policy["selection_metadata"]
    selected = set(metadata["selected_candidate_ids"])
    initial = set(metadata["initial_candidate_ids"])
    additions = sorted(selected - initial)
    return {
        "world_id": world_id,
        "simulation_seed": simulation_seed,
        "learner_count": learner_count,
        "complexity_penalty": complexity_penalty,
        "selected_candidate_ids": sorted(selected),
        "selected_addition_ids": additions,
        "selected_interaction_ids": [
            row for row in additions if row.startswith("kc_interaction__")
        ],
        "selected_operation_ids": [
            row for row in additions if row.startswith("kc_operation__")
        ],
        "selected_kc_count": len(selected),
        "validation": metadata["final_validation_score"],
        "split": metadata["split"],
        "source_event_artifact": _artifact_path(source),
        "selection_artifact": _artifact_path(artifact),
    }


def _select_or_reuse(
    candidate_inventory: dict[str, Any],
    events: list[dict[str, Any]],
    base_design: dict[str, Any],
    *,
    world_id: str,
    simulation_seed: int,
    learner_count: int,
    complexity_penalty: float,
    source: Path,
    artifact: Path,
    recompute: bool,
    phase4_policy: Path | None = None,
) -> dict[str, Any]:
    if phase4_policy is not None and not recompute:
        policy = _read_json(phase4_policy)
        retained_artifact = phase4_policy
    elif artifact.exists() and not recompute:
        policy = _read_json(artifact)
        retained_artifact = artifact
    else:
        design = copy.deepcopy(base_design)
        design["selection_id"] = (
            "phase5_forward_predictive_parsimony"
            f"__n{learner_count}__lambda_{_penalty_slug(complexity_penalty)}"
        )
        design["objective"]["complexity_penalty"] = complexity_penalty
        policy = select_kcs(candidate_inventory, events, design)
        write_json(artifact, policy)
        retained_artifact = artifact

    metadata = policy["selection_metadata"]
    observed_penalty = float(metadata["objective"]["complexity_penalty"])
    if observed_penalty != complexity_penalty:
        raise ValueError(
            f"cached selection has lambda={observed_penalty}, expected {complexity_penalty}"
        )
    if metadata["held_out_grammar_read"] or metadata["reserved_or_holdout_outcomes_read"]:
        raise AssertionError("Phase-5 selection crossed its evidence boundary")
    if int(metadata["split"]["train_learners"]) != learner_count:
        # Chronological splitting uses every learner in both temporal partitions.
        raise ValueError("cached selection has the wrong learner support")
    return _selection_record(
        policy,
        world_id=world_id,
        simulation_seed=simulation_seed,
        learner_count=learner_count,
        complexity_penalty=complexity_penalty,
        source=source,
        artifact=retained_artifact,
    )


def _summarise_selection_group(rows: list[dict[str, Any]]) -> dict[str, Any]:
    selected_sets = [set(row["selected_candidate_ids"]) for row in rows]
    addition_sets = [set(row["selected_addition_ids"]) for row in rows]
    interaction_frequency = Counter(
        candidate_id
        for row in rows
        for candidate_id in row["selected_interaction_ids"]
    )
    addition_frequency = Counter(
        candidate_id for row in rows for candidate_id in row["selected_addition_ids"]
    )
    return {
        "runs": len(rows),
        "simulation_seeds": [row["simulation_seed"] for row in rows],
        "selected_kc_counts": [row["selected_kc_count"] for row in rows],
        "selected_addition_counts": [len(row["selected_addition_ids"]) for row in rows],
        "all_kc_pairwise_jaccard": _pairwise_jaccard(selected_sets),
        "addition_pairwise_jaccard": _pairwise_jaccard(addition_sets),
        "addition_frequency": dict(sorted(addition_frequency.items())),
        "interaction_frequency": dict(sorted(interaction_frequency.items())),
        "factorized_null_false_addition_runs": sum(
            bool(row["selected_addition_ids"])
            for row in rows
            if row["world_id"] == "phase4_factorized_v1"
        ),
        "interaction_heavy_recovery": {
            candidate_id: sum(
                candidate_id in row["selected_candidate_ids"] for row in rows
            )
            for candidate_id in sorted(RECOVERABLE_PLANTED_INTERACTIONS)
        },
        "mean_validation_log_loss": mean(
            row["validation"]["log_loss"] for row in rows
        ),
    }


def _group_selection_results(
    records: list[dict[str, Any]], keys: tuple[str, ...]
) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for row in records:
        key = tuple(row[name] for name in keys)
        groups.setdefault(key, []).append(row)
    return [
        {
            **dict(zip(keys, key, strict=True)),
            **_summarise_selection_group(sorted(rows, key=lambda row: row["simulation_seed"])),
        }
        for key, rows in sorted(groups.items())
    ]


def _nested_support_agreement(
    records: list[dict[str, Any]], full_learner_count: int
) -> list[dict[str, Any]]:
    lookup = {
        (row["world_id"], row["simulation_seed"], row["learner_count"]): row
        for row in records
    }
    output = []
    for row in records:
        if row["learner_count"] == full_learner_count:
            continue
        full = lookup[(row["world_id"], row["simulation_seed"], full_learner_count)]
        selected = set(row["selected_candidate_ids"])
        full_selected = set(full["selected_candidate_ids"])
        additions = set(row["selected_addition_ids"])
        full_additions = set(full["selected_addition_ids"])
        output.append(
            {
                "world_id": row["world_id"],
                "simulation_seed": row["simulation_seed"],
                "learner_count": row["learner_count"],
                "all_kc_jaccard_with_240": _pairwise_jaccard(
                    [selected, full_selected]
                )["mean"],
                "addition_jaccard_with_240": _pairwise_jaccard(
                    [additions, full_additions]
                )["mean"],
                "exact_inventory_match_with_240": selected == full_selected,
            }
        )
    return output


def paired_cluster_bootstrap(
    events: list[dict[str, Any]],
    reference_predictions: dict[str, float],
    candidate_predictions: dict[str, float],
    *,
    repeats: int,
    seed: int,
    reference_policy_id: str,
    candidate_policy_id: str,
) -> dict[str, Any]:
    """Efficient event-weighted paired bootstrap over whole learners."""

    if repeats < 1:
        raise ValueError("bootstrap repeats must be positive")
    if not events:
        raise ValueError("paired comparison requires evaluation events")
    event_ids = [str(row["event_id"]) for row in events]
    if len(event_ids) != len(set(event_ids)):
        raise ValueError("evaluation event IDs must be unique")
    expected = set(event_ids)
    if set(reference_predictions) != expected or set(candidate_predictions) != expected:
        raise ValueError("predictions must exactly cover evaluation events")

    learners = sorted({str(row["learner_id"]) for row in events})
    learner_index = {learner_id: index for index, learner_id in enumerate(learners)}
    log_loss_sums = np.zeros(len(learners), dtype=float)
    brier_sums = np.zeros(len(learners), dtype=float)
    counts = np.zeros(len(learners), dtype=float)
    reference_log_loss_sum = 0.0
    candidate_log_loss_sum = 0.0
    reference_brier_sum = 0.0
    candidate_brier_sum = 0.0
    for event in events:
        event_id = str(event["event_id"])
        target = float(event["correct"])
        if target not in (0.0, 1.0):
            raise ValueError("paired comparison outcomes must be binary")
        reference_raw = float(reference_predictions[event_id])
        candidate_raw = float(candidate_predictions[event_id])
        if (
            not np.isfinite(reference_raw)
            or not np.isfinite(candidate_raw)
            or not 0.0 <= reference_raw <= 1.0
            or not 0.0 <= candidate_raw <= 1.0
        ):
            raise ValueError(
                "paired comparison probabilities must be finite and in [0, 1]"
            )
        reference = float(np.clip(reference_raw, 1e-6, 1 - 1e-6))
        candidate = float(np.clip(candidate_raw, 1e-6, 1 - 1e-6))
        reference_loss = -(target * np.log(reference) + (1 - target) * np.log(1 - reference))
        candidate_loss = -(target * np.log(candidate) + (1 - target) * np.log(1 - candidate))
        reference_brier = (reference - target) ** 2
        candidate_brier = (candidate - target) ** 2
        index = learner_index[str(event["learner_id"])]
        log_loss_sums[index] += candidate_loss - reference_loss
        brier_sums[index] += candidate_brier - reference_brier
        counts[index] += 1
        reference_log_loss_sum += reference_loss
        candidate_log_loss_sum += candidate_loss
        reference_brier_sum += reference_brier
        candidate_brier_sum += candidate_brier

    rng = np.random.default_rng(seed)
    sampled_indices = rng.integers(
        0, len(learners), size=(repeats, len(learners)), endpoint=False
    )
    sampled_counts = counts[sampled_indices].sum(axis=1)
    sampled_log_loss = log_loss_sums[sampled_indices].sum(axis=1) / sampled_counts
    sampled_brier = brier_sums[sampled_indices].sum(axis=1) / sampled_counts
    total_events = int(counts.sum())
    event_counts = sorted(int(value) for value in counts)
    return {
        "available": True,
        "reference_policy_id": reference_policy_id,
        "candidate_policy_id": candidate_policy_id,
        "sign_convention": "candidate_minus_reference; negative favours candidate",
        "sampling_unit": "learner",
        "aggregation": "event_weighted",
        "percentile_method": "linear",
        "n_learners": len(learners),
        "n_events": total_events,
        "events_per_learner": {
            "minimum": event_counts[0],
            "median": float(np.median(event_counts)),
            "maximum": event_counts[-1],
        },
        "repeats": repeats,
        "seed": seed,
        "observed": {
            "reference": {
                "log_loss": reference_log_loss_sum / total_events,
                "brier_score": reference_brier_sum / total_events,
            },
            "candidate": {
                "log_loss": candidate_log_loss_sum / total_events,
                "brier_score": candidate_brier_sum / total_events,
            },
        },
        "delta_log_loss": {
            "point_estimate": float(log_loss_sums.sum() / total_events),
            "interval_95": [
                float(np.quantile(sampled_log_loss, 0.025, method="linear")),
                float(np.quantile(sampled_log_loss, 0.975, method="linear")),
            ],
        },
        "delta_brier_score": {
            "point_estimate": float(brier_sums.sum() / total_events),
            "interval_95": [
                float(np.quantile(sampled_brier, 0.025, method="linear")),
                float(np.quantile(sampled_brier, 0.975, method="linear")),
            ],
        },
    }


def _paired_representation_comparisons(
    worlds: list[str], *, phase4_dir: Path, repeats: int, seed: int
) -> list[dict[str, Any]]:
    output = []
    for world_id in worlds:
        event_path = phase4_dir / "events" / f"{world_id}__{REFERENCE_SEED}__frozen_probe.jsonl.gz"
        prediction_path = phase4_dir / "predictions" / f"{world_id}__{REFERENCE_SEED}.jsonl.gz"
        events = _read_jsonl_gzip(event_path)
        predictions = [
            row
            for row in _read_jsonl_gzip(prediction_path)
            if row["protocol"] == "frozen_probe" and row["technique"] == "logistic"
        ]
        prediction_by_representation = {
            representation: {
                row["event_id"]: float(row["probability"])
                for row in predictions
                if row["representation"] == representation
            }
            for representation in {
                row["representation"] for row in predictions
            }
        }
        for regime in ("all_test", *GRAMMAR_REGIMES):
            selected_events = [
                row
                for row in events
                if row["dataset_split"] == "test"
                and (regime == "all_test" or row["grammar_split"] == regime)
            ]
            selected_ids = {row["event_id"] for row in selected_events}
            reference = {
                event_id: probability
                for event_id, probability in prediction_by_representation[
                    "factorized"
                ].items()
                if event_id in selected_ids
            }
            for candidate in (
                "automated",
                "supported_interactions",
                "oracle_all_cell",
            ):
                comparison = paired_cluster_bootstrap(
                    selected_events,
                    reference,
                    {
                        event_id: probability
                        for event_id, probability in prediction_by_representation[
                            candidate
                        ].items()
                        if event_id in selected_ids
                    },
                    repeats=repeats,
                    seed=seed,
                    reference_policy_id="factorized",
                    candidate_policy_id=candidate,
                )
                output.append(
                    {
                        "world_id": world_id,
                        "simulation_seed": REFERENCE_SEED,
                        "grammar_regime": regime,
                        "reference": "factorized",
                        "candidate": candidate,
                        **comparison,
                    }
                )
    return output


def _representation_table(phase4_results: dict[str, Any]) -> list[dict[str, Any]]:
    output = []
    aggregates = phase4_results["world_by_representation_primary_logistic"]
    for world_id, protocols in sorted(aggregates.items()):
        for representation, regimes in protocols["frozen_probe"].items():
            for regime, metrics in regimes.items():
                output.append(
                    {
                        "world_id": world_id,
                        "protocol": "frozen_probe",
                        "representation": representation,
                        "grammar_regime": regime,
                        **metrics,
                    }
                )
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase4-dir", type=Path, default=PHASE4)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--recompute", action="store_true")
    args = parser.parse_args()

    phase4_dir = args.phase4_dir.resolve()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)

    phase4_results = _read_json(phase4_dir / "results.json")
    study = _read_json(phase4_dir / "study_design.json")
    inventory = _read_json(phase4_dir / "candidate_inventory.json")
    design_path = ROOT / "modules/kcs/selection.yaml"
    selection_design = read_yaml(design_path)
    if float(selection_design["objective"]["complexity_penalty"]) != ACTIVE_PENALTY:
        raise ValueError(
            "Phase-5 design expects the retained active lambda=0.0005; "
            "update the declared study before changing this intervention"
        )
    worlds = sorted(phase4_results["world_runs"])
    seeds = sorted(int(seed) for seed in study["scale"]["seeds"])
    if max(LEARNER_SIZES) != int(study["scale"]["learners_per_world_seed"]):
        raise ValueError("Phase-4 learner scale does not match the Phase-5 design")

    event_cache: dict[tuple[str, int], tuple[Path, list[dict[str, Any]]]] = {}
    input_hashes = {}
    for world_id in worlds:
        for simulation_seed in seeds:
            path = phase4_dir / "events" / f"{world_id}__{simulation_seed}__frozen_probe.jsonl.gz"
            event_cache[(world_id, simulation_seed)] = (
                path,
                _read_jsonl_gzip(path),
            )
            input_hashes[_artifact_path(path)] = _sha256(path)

    support_records = []
    for learner_count in LEARNER_SIZES:
        print(f"learner-support stage: n={learner_count}", flush=True)
        for world_id in worlds:
            for simulation_seed in seeds:
                source, all_events = event_cache[(world_id, simulation_seed)]
                events = subset_development_learners(all_events, learner_count)
                artifact = (
                    output
                    / "selections"
                    / "learner_support"
                    / f"{world_id}__{simulation_seed}__n{learner_count}.json"
                )
                phase4_policy = None
                if learner_count == max(LEARNER_SIZES):
                    phase4_policy = (
                        phase4_dir / "selections" / f"{world_id}__{simulation_seed}.json"
                    )
                support_records.append(
                    _select_or_reuse(
                        inventory,
                        events,
                        selection_design,
                        world_id=world_id,
                        simulation_seed=simulation_seed,
                        learner_count=learner_count,
                        complexity_penalty=ACTIVE_PENALTY,
                        source=source,
                        artifact=artifact,
                        recompute=args.recompute,
                        phase4_policy=phase4_policy,
                    )
                )

    lambda_records = []
    for complexity_penalty in LAMBDA_GRID:
        print(f"lambda stage: lambda={complexity_penalty:g}", flush=True)
        for world_id in DIAGNOSTIC_WORLDS:
            for simulation_seed in seeds:
                source, all_events = event_cache[(world_id, simulation_seed)]
                events = subset_development_learners(all_events, max(LEARNER_SIZES))
                artifact = (
                    output
                    / "selections"
                    / "lambda_sensitivity"
                    / (
                        f"{world_id}__{simulation_seed}"
                        f"__lambda_{_penalty_slug(complexity_penalty)}.json"
                    )
                )
                phase4_policy = None
                if complexity_penalty == ACTIVE_PENALTY:
                    phase4_policy = (
                        phase4_dir / "selections" / f"{world_id}__{simulation_seed}.json"
                    )
                lambda_records.append(
                    _select_or_reuse(
                        inventory,
                        events,
                        selection_design,
                        world_id=world_id,
                        simulation_seed=simulation_seed,
                        learner_count=max(LEARNER_SIZES),
                        complexity_penalty=complexity_penalty,
                        source=source,
                        artifact=artifact,
                        recompute=args.recompute,
                        phase4_policy=phase4_policy,
                    )
                )

    print("paired representation bootstrap: 5,000 learner resamples", flush=True)
    comparisons = _paired_representation_comparisons(
        worlds,
        phase4_dir=phase4_dir,
        repeats=BOOTSTRAP_REPEATS,
        seed=REFERENCE_SEED,
    )

    support_summary = _group_selection_results(
        support_records, ("world_id", "learner_count")
    )
    lambda_summary = _group_selection_results(
        lambda_records, ("world_id", "complexity_penalty")
    )
    nested = _nested_support_agreement(support_records, max(LEARNER_SIZES))
    results = {
        "experiment_id": "P5-INTEGRATED-VALIDATION-001",
        "evidence_status": "scientific_replay",
        "study_design": {
            "date": "2026-08-27",
            "exact_command": (
                ".venv/bin/python scripts/run_phase5_integrated_validation.py"
            ),
            "source_experiment": phase4_results["experiment_id"],
            "source_artifact": _artifact_path(phase4_dir),
            "frozen_inputs": [
                "24 canonical cells",
                "42 structural item identifiers",
                "semantic 18/5/1 grammar fold",
                "four latent-world event streams for three seeds",
                "reference-seed primary-logistic predictions",
            ],
            "interventions": {
                "learner_support": list(LEARNER_SIZES),
                "active_complexity_penalty": ACTIVE_PENALTY,
                "lambda_grid_on_diagnostic_worlds": list(LAMBDA_GRID),
                "diagnostic_worlds": list(DIAGNOSTIC_WORLDS),
                "paired_bootstrap_repeats": BOOTSTRAP_REPEATS,
                "paired_bootstrap_seed": REFERENCE_SEED,
                "paired_bootstrap_unit": "learner",
            },
            "selection_config": _artifact_path(design_path),
            "selection_config_sha256": _sha256(design_path),
            "source_event_sha256": input_hashes,
            "language_model_calls": None,
            "new_simulation": False,
            "new_item_generation": False,
            "new_kt_fits_for_policy_comparison": False,
        },
        "learner_support": {
            "records": support_records,
            "by_world_and_size": support_summary,
            "nested_agreement_with_240": nested,
        },
        "lambda_sensitivity": {
            "records": lambda_records,
            "by_world_and_lambda": lambda_summary,
        },
        "paired_primary_logistic": comparisons,
        "three_seed_primary_logistic": _representation_table(phase4_results),
        "interpretation_boundary": (
            "The study reuses synthetic learner evidence and structural item IDs. "
            "It supports method behavior under declared worlds, not claims about "
            "human cognition or natural-language item quality."
        ),
    }
    write_json(output / "results.json", results)
    write_json(
        output / "summary.json",
        {
            "experiment_id": results["experiment_id"],
            "evidence_status": results["evidence_status"],
            "study_design": results["study_design"],
            "learner_support": support_summary,
            "nested_agreement_with_240": nested,
            "lambda_sensitivity": lambda_summary,
            "paired_primary_logistic": comparisons,
            "three_seed_primary_logistic": results["three_seed_primary_logistic"],
            "full_results": _artifact_path(output / "results.json"),
        },
    )
    print(f"Wrote {output / 'results.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
