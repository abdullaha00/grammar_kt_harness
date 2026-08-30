#!/usr/bin/env python3
"""Preregister and run the frozen-full-v1 KC misspecification study.

The predictor consumes observable interactions and an item-to-KC hypothesis.
It never reads private learner trajectories.  ``plan`` freezes every hypothesis
before response outcomes are analysed; ``run`` refuses a changed plan, script,
input, or projection bundle.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Sequence

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = ROOT / "data/grammar_kt_full_v1"
DEFAULT_OUTPUT = ROOT / "reports/full_v1_artifacts/rq2_misspecification_v1"
STUDY_ID = "full_v1_rq2_kc_misspecification_v1"
NOISE_RATE = 0.10
NOISE_SEEDS = (20260830, 20260831, 20260832)
BOOTSTRAP_SEED = 20260830
BOOTSTRAP_REPEATS = 2000
MODEL_SEED = 20260830
ECE_BINS = 10

COARSE_GROUPS = {
    "coarse_aspect": {
        "gkc_aspect_perfect",
        "gkc_aspect_progressive",
    },
    "coarse_clause_formation": {
        "gkc_imperative",
        "gkc_non_subject_wh_question",
        "gkc_polar_question",
    },
    "coarse_finite_tense": {
        "gkc_finite_past",
        "gkc_finite_present",
    },
    "coarse_modality": {
        "gkc_modal_can",
        "gkc_modal_could",
        "gkc_modal_may",
        "gkc_modal_might",
        "gkc_modal_must",
        "gkc_modal_shall",
        "gkc_modal_should",
        "gkc_modal_will",
        "gkc_modal_would",
    },
    "coarse_negation": {"gkc_negation"},
    "coarse_voice": {"gkc_be_passive"},
}


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _repository_head() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _write_frozen_json(path: Path, value: Any, label: str) -> None:
    payload = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_text(encoding="utf-8") != payload:
            raise FileExistsError(f"refusing to overwrite changed {label}: {path}")
        return
    path.write_text(payload, encoding="utf-8")


def _write_frozen_text(path: Path, payload: str, label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_text(encoding="utf-8") != payload:
            raise FileExistsError(f"refusing to overwrite changed {label}: {path}")
        return
    path.write_text(payload, encoding="utf-8")


def load_true_projection(
    path: str | Path,
) -> tuple[list[str], dict[str, tuple[str, ...]]]:
    with Path(path).open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or reader.fieldnames[0] != "item_id":
            raise ValueError("dense Q* must begin with item_id")
        kc_ids = list(reader.fieldnames[1:])
        if not kc_ids or len(kc_ids) != len(set(kc_ids)):
            raise ValueError("dense Q* has empty or duplicate KC columns")
        projection: dict[str, tuple[str, ...]] = {}
        for row in reader:
            item_id = str(row["item_id"])
            if item_id in projection:
                raise ValueError(f"dense Q* duplicates item {item_id}")
            unknown = {
                value for key, value in row.items() if key != "item_id" and value not in {"0", "1"}
            }
            if unknown:
                raise ValueError(f"dense Q* must be binary: {sorted(unknown)}")
            projection[item_id] = tuple(
                kc_id for kc_id in kc_ids if row[kc_id] == "1"
            )
    if not projection or any(not active for active in projection.values()):
        raise ValueError("true Q* must cover every item")
    return kc_ids, dict(sorted(projection.items()))


def validate_projection(
    projection: dict[str, Sequence[str]], expected_items: Iterable[str]
) -> dict[str, Any]:
    expected = set(expected_items)
    if set(projection) != expected:
        raise ValueError("KC projection must exactly cover the fixed item bank")
    normalized: dict[str, tuple[str, ...]] = {}
    for item_id, active in projection.items():
        values = tuple(sorted(str(value) for value in active))
        if len(values) != len(set(values)):
            raise ValueError(f"projection duplicates a KC edge for {item_id}")
        normalized[item_id] = values
    kc_ids = sorted({kc_id for active in normalized.values() for kc_id in active})
    edge_count = sum(len(active) for active in normalized.values())
    supports = {
        kc_id: sum(kc_id in active for active in normalized.values())
        for kc_id in kc_ids
    }
    columns: dict[tuple[str, ...], list[str]] = defaultdict(list)
    for kc_id in kc_ids:
        columns[
            tuple(item_id for item_id, active in sorted(normalized.items()) if kc_id in active)
        ].append(kc_id)
    identical = [sorted(group) for group in columns.values() if len(group) > 1]
    matrix = np.asarray(
        [
            [int(kc_id in normalized[item_id]) for kc_id in kc_ids]
            for item_id in sorted(normalized)
        ],
        dtype=np.int8,
    )
    return {
        "items": len(normalized),
        "kcs": len(kc_ids),
        "edges": edge_count,
        "density": edge_count / (len(normalized) * len(kc_ids)) if kc_ids else 0.0,
        "empty_items": sum(not active for active in normalized.values()),
        "support": {
            "minimum": min(supports.values()) if supports else 0,
            "median": float(median(supports.values())) if supports else 0.0,
            "maximum": max(supports.values()) if supports else 0,
        },
        "identical_column_groups": identical,
        "column_rank": int(np.linalg.matrix_rank(matrix)) if kc_ids else 0,
    }


def all_merged_projection(
    true_projection: dict[str, Sequence[str]],
) -> dict[str, tuple[str, ...]]:
    return {item_id: ("coarse_all_grammar",) for item_id in true_projection}


def coarse_projection(
    true_projection: dict[str, Sequence[str]],
    true_kc_ids: Sequence[str],
) -> dict[str, tuple[str, ...]]:
    reverse: dict[str, str] = {}
    for group_id, members in COARSE_GROUPS.items():
        for kc_id in members:
            if kc_id in reverse:
                raise ValueError(f"coarse grouping duplicates {kc_id}")
            reverse[kc_id] = group_id
    if set(reverse) != set(true_kc_ids):
        raise ValueError(
            "coarse grouping must partition K*: "
            f"missing={sorted(set(true_kc_ids) - set(reverse))}, "
            f"unknown={sorted(set(reverse) - set(true_kc_ids))}"
        )
    return {
        item_id: tuple(sorted({reverse[kc_id] for kc_id in active}))
        for item_id, active in true_projection.items()
    }


def structural_split_projection(
    true_projection: dict[str, Sequence[str]],
    items: Sequence[dict[str, Any]],
    cells: Sequence[dict[str, Any]],
    factor: int,
) -> dict[str, tuple[str, ...]]:
    """Split each true KC by deterministic canonical-cell context.

    Contexts are complete GrammarCell feature tuples, ordered lexicographically
    within the parent KC and assigned cyclically to at most ``factor`` children.
    Item variants of the same cell remain in the same child.  The construction
    uses no outcomes and creates a controlled finer, not interaction, ontology.
    """

    if factor < 2:
        raise ValueError("structural split factor must be at least two")
    features_by_cell = {
        str(row["cell_id"]): _canonical_json(row["features"]) for row in cells
    }
    cell_by_item = {str(row["item_id"]): str(row["cell_id"]) for row in items}
    if set(cell_by_item) != set(true_projection):
        raise ValueError("items and Q* disagree while constructing structural split")
    if set(cell_by_item.values()) - set(features_by_cell):
        raise ValueError("item bank refers to an unknown GrammarCell")
    contexts_by_kc: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for item_id, active in true_projection.items():
        cell_id = cell_by_item[item_id]
        context = (features_by_cell[cell_id], cell_id)
        for kc_id in active:
            contexts_by_kc[str(kc_id)].add(context)
    bucket_by_kc_context: dict[tuple[str, tuple[str, str]], int] = {}
    for kc_id, contexts in sorted(contexts_by_kc.items()):
        for index, context in enumerate(sorted(contexts)):
            bucket_by_kc_context[(kc_id, context)] = index % factor
    return {
        item_id: tuple(
            sorted(
                f"{kc_id}__structural_split_{factor}_{bucket_by_kc_context[(str(kc_id), (features_by_cell[cell_by_item[item_id]], cell_by_item[item_id]))] + 1}"
                for kc_id in active
            )
        )
        for item_id, active in true_projection.items()
    }


def exact_cell_projection(
    items: Sequence[dict[str, Any]],
) -> dict[str, tuple[str, ...]]:
    return {
        str(row["item_id"]): (f"exact_cell::{row['cell_id']}",) for row in items
    }


def perturb_projection(
    true_projection: dict[str, Sequence[str]],
    true_kc_ids: Sequence[str],
    *,
    kind: str,
    rate: float,
    seed: int,
) -> tuple[dict[str, tuple[str, ...]], dict[str, Any]]:
    if kind not in {"false_positive", "false_negative", "mixed"}:
        raise ValueError(f"unknown Q perturbation: {kind}")
    if not 0.0 < rate < 1.0:
        raise ValueError("Q perturbation rate must be in (0, 1)")
    item_ids = sorted(true_projection)
    kc_ids = sorted(true_kc_ids)
    edges = {(item_id, kc_id) for item_id in item_ids for kc_id in true_projection[item_id]}
    nonedges = {
        (item_id, kc_id)
        for item_id in item_ids
        for kc_id in kc_ids
        if (item_id, kc_id) not in edges
    }
    budget = max(1, int(round(rate * len(edges))))
    remove_count = budget if kind == "false_negative" else (budget + 1) // 2 if kind == "mixed" else 0
    add_count = budget if kind == "false_positive" else budget // 2 if kind == "mixed" else 0
    rng = np.random.default_rng(seed)

    def sample(population: set[tuple[str, str]], count: int) -> set[tuple[str, str]]:
        ordered = sorted(population)
        if count > len(ordered):
            raise ValueError("Q perturbation budget exceeds eligible edges")
        if not count:
            return set()
        indices = rng.choice(len(ordered), size=count, replace=False)
        return {ordered[int(index)] for index in indices}

    def constrained_removals(count: int) -> set[tuple[str, str]]:
        """Sample deletions while retaining item and KC support."""

        if not count:
            return set()
        item_degree = Counter(item_id for item_id, _kc_id in edges)
        kc_support = Counter(kc_id for _item_id, kc_id in edges)
        ordered = sorted(edges)
        order = rng.permutation(len(ordered))
        selected: set[tuple[str, str]] = set()
        for raw_index in order:
            edge = ordered[int(raw_index)]
            item_id, kc_id = edge
            if item_degree[item_id] <= 1 or kc_support[kc_id] <= 1:
                continue
            selected.add(edge)
            item_degree[item_id] -= 1
            kc_support[kc_id] -= 1
            if len(selected) == count:
                return selected
        raise ValueError(
            "Q false-negative budget cannot preserve at least one edge per item "
            "and at least one item per KC"
        )

    removed = constrained_removals(remove_count)
    added = sample(nonedges, add_count)
    perturbed_edges = (edges - removed) | added
    projection = {
        item_id: tuple(kc_id for kc_id in kc_ids if (item_id, kc_id) in perturbed_edges)
        for item_id in item_ids
    }
    metadata = {
        "kind": kind,
        "seed": seed,
        "rate_relative_to_true_edges": rate,
        "true_edges": len(edges),
        "hamming_budget": budget,
        "removed_edges": len(removed),
        "added_edges": len(added),
        "realized_hamming_rate_relative_to_true_edges": (len(removed) + len(added)) / len(edges),
        "result_edges": len(perturbed_edges),
        "deletion_constraints": {
            "minimum_edges_per_item": 1,
            "minimum_support_per_kc": 1,
        },
        "removed_edge_sha256": _sha256_bytes(_canonical_json(sorted(removed)).encode()),
        "added_edge_sha256": _sha256_bytes(_canonical_json(sorted(added)).encode()),
    }
    return projection, metadata


def build_representations(
    *,
    true_kc_ids: Sequence[str],
    true_projection: dict[str, Sequence[str]],
    items: Sequence[dict[str, Any]],
    cells: Sequence[dict[str, Any]],
) -> tuple[dict[str, dict[str, tuple[str, ...]]], dict[str, dict[str, Any]]]:
    representations: dict[str, dict[str, tuple[str, ...]]] = {
        "all_merged": all_merged_projection(true_projection),
        "coarse_linguistic_families": coarse_projection(
            true_projection, true_kc_ids
        ),
        "true_kstar": {
            item_id: tuple(active) for item_id, active in true_projection.items()
        },
        "structural_split2": structural_split_projection(
            true_projection, items, cells, 2
        ),
        "structural_split4": structural_split_projection(
            true_projection, items, cells, 4
        ),
        "exact_cell": exact_cell_projection(items),
    }
    metadata: dict[str, dict[str, Any]] = {
        "all_merged": {"kind": "merge", "granularity": "very_coarse"},
        "coarse_linguistic_families": {
            "kind": "merge",
            "granularity": "coarse",
            "groups": {key: sorted(value) for key, value in COARSE_GROUPS.items()},
        },
        "true_kstar": {"kind": "reference", "granularity": "generator_truth"},
        "structural_split2": {
            "kind": "split",
            "factor": 2,
            "rule": "lexicographic canonical-cell contexts, cyclic buckets within parent K*",
        },
        "structural_split4": {
            "kind": "split",
            "factor": 4,
            "rule": "lexicographic canonical-cell contexts, cyclic buckets within parent K*",
        },
        "exact_cell": {
            "kind": "upper_bound",
            "rule": "one hypothesis KC per canonical GrammarCell",
        },
    }
    for kind in ("false_positive", "false_negative", "mixed"):
        for seed in NOISE_SEEDS:
            representation_id = f"q_{kind}_10pct_seed_{seed}"
            projection, perturbation = perturb_projection(
                true_projection,
                true_kc_ids,
                kind=kind,
                rate=NOISE_RATE,
                seed=seed,
            )
            representations[representation_id] = projection
            metadata[representation_id] = {
                "kind": "q_matrix_perturbation",
                "base": "true_kstar",
                **perturbation,
            }
    expected_items = [str(row["item_id"]) for row in items]
    for representation_id, projection in representations.items():
        metadata[representation_id]["structure"] = validate_projection(
            projection, expected_items
        )
    return representations, metadata


def render_projection_bundle(
    representations: dict[str, dict[str, Sequence[str]]]
) -> str:
    return "".join(
        _canonical_json(
            {
                "representation_id": representation_id,
                "item_id": item_id,
                "kc_ids": list(representations[representation_id][item_id]),
            }
        )
        + "\n"
        for representation_id in sorted(representations)
        for item_id in sorted(representations[representation_id])
    )


def load_projection_bundle(
    path: Path,
) -> dict[str, dict[str, tuple[str, ...]]]:
    output: dict[str, dict[str, tuple[str, ...]]] = defaultdict(dict)
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        representation_id = str(row["representation_id"])
        item_id = str(row["item_id"])
        if item_id in output[representation_id]:
            raise ValueError("projection bundle duplicates a representation/item row")
        output[representation_id][item_id] = tuple(str(kc) for kc in row["kc_ids"])
    return {key: dict(value) for key, value in output.items()}


def _plan_inputs(dataset_dir: Path) -> dict[str, dict[str, Any]]:
    relative = {
        "manifest": "manifest.json",
        "interactions": "interactions.jsonl.gz",
        "items": "items/items.jsonl",
        "cells": "grammar/cells.jsonl",
        "generator_kcs": "kcs.jsonl",
        "true_q_matrix": "q_matrix.csv",
        "grammar_regimes": "grammar/regime_assignments.jsonl",
    }
    output = {}
    for name, filename in relative.items():
        path = dataset_dir / filename
        if not path.is_file():
            raise FileNotFoundError(path)
        output[name] = {
            "path": filename,
            "sha256": file_sha256(path),
            "bytes": path.stat().st_size,
        }
    return output


def create_plan(dataset_dir: Path, output_dir: Path) -> dict[str, Any]:
    manifest = json.loads((dataset_dir / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("status") != "FROZEN_BASELINE_COMPLETE":
        raise ValueError("RQ2 requires a frozen full-v1 baseline")
    items = _read_jsonl(dataset_dir / "items/items.jsonl")
    cells = _read_jsonl(dataset_dir / "grammar/cells.jsonl")
    kcs = _read_jsonl(dataset_dir / "kcs.jsonl")
    true_kc_ids, true_projection = load_true_projection(dataset_dir / "q_matrix.csv")
    declared_kcs = sorted(str(row["id"]) for row in kcs)
    if sorted(true_kc_ids) != declared_kcs:
        raise ValueError("K* inventory and dense Q* columns disagree")
    representations, metadata = build_representations(
        true_kc_ids=true_kc_ids,
        true_projection=true_projection,
        items=items,
        cells=cells,
    )
    projection_payload = render_projection_bundle(representations)
    projection_path = output_dir / "projections.jsonl"
    _write_frozen_text(projection_path, projection_payload, "preregistered projections")
    script_path = Path(__file__).resolve()
    plan = {
        "study_id": STUDY_ID,
        "status": "PREREGISTERED_BEFORE_OUTCOME_ANALYSIS",
        "research_question": "How does observable KT prediction change when K-hat/Q-hat differs from frozen generator K*/Q*?",
        "hypotheses": [
            "Very coarse merging will lose reusable distinction and worsen terminal-probe log loss relative to K*.",
            "Moderate linguistically grouped merging may remain predictively competitive, demonstrating that prediction need not uniquely identify K*.",
            "Increasing structural splitting will eventually reduce support per hypothesis KC and worsen prediction.",
            "Ten-percent Q false negatives, false positives, and mixed corruption will worsen prediction on average, with false negatives expected to be most damaging under a conjunctive generator.",
        ],
        "scientific_boundary": {
            "predictor_inputs": [
                "observable interaction rows",
                "one preregistered item-to-KC hypothesis",
            ],
            "learner_oracle_read": False,
            "generator_truth_use": "reference representation and controlled perturbation construction only",
            "same_frozen_events_across_representations": True,
            "training_outcomes": "all acquisition events",
            "evaluation_outcomes": "terminal non-updating probes only",
            "probe_outcomes_used_for_selection_or_tuning": False,
        },
        "conditions_in_execution_order": list(representations),
        "representations": metadata,
        "model": {
            "name": "observable_history_logistic_pfa_like",
            "history_priors": {"alpha": 1.0, "beta": 1.0},
            "features": [
                "learner prior-smoothed overall correctness",
                "mean prior-smoothed correctness over active hypothesis KCs",
                "mean log1p opportunities over active hypothesis KCs",
                "active hypothesis-KC count",
                "hypothesis-KC indicators",
            ],
            "history_updates": "after acquisition events only; probes are non-updating",
            "standardize": True,
            "regularization_c": 1.0,
            "max_iterations": 500,
            "random_seed": MODEL_SEED,
            "technique_scope": "Logistic is the RQ2 primary model; empirical/BKT technique sensitivity is reserved for the separate KT robustness programme.",
        },
        "evaluation": {
            "primary_metric": "terminal-probe event-weighted log loss",
            "secondary_metrics": ["Brier score", "ECE", "AUC", "accuracy"],
            "grammar_regimes": [
                "all_probe",
                "seen",
                "unseen_combination",
                "unseen_value",
            ],
            "uncertainty": {
                "method": "paired percentile bootstrap over whole learners",
                "reference": "true_kstar",
                "repeats": BOOTSTRAP_REPEATS,
                "seed": BOOTSTRAP_SEED,
                "aggregation": "event_weighted",
                "delta_sign": "candidate_minus_true_kstar; positive favours K*",
            },
            "interpretation": {
                "cost_supported": "candidate-minus-K* log-loss interval is entirely above zero",
                "candidate_predictive_gain": "interval is entirely below zero; this does not establish cognitive truth",
                "not_resolved": "interval includes zero; this is not an equivalence test",
            },
        },
        "inputs": _plan_inputs(dataset_dir),
        "projection_bundle": {
            "path": projection_path.name,
            "sha256": _sha256_bytes(projection_payload.encode("utf-8")),
            "rows": len(representations) * len(items),
        },
        "implementation": {
            "script": str(script_path.relative_to(ROOT)),
            "script_sha256": file_sha256(script_path),
            "repository_head_at_preregistration": _repository_head(),
            "python": sys.version.split()[0],
            "numpy": np.__version__,
        },
        "exact_commands": {
            "plan": ".venv/bin/python scripts/experiments/rq2_kc_misspecification.py --stage plan",
            "run": ".venv/bin/python scripts/experiments/rq2_kc_misspecification.py --stage run",
        },
    }
    _write_frozen_json(output_dir / "study_plan.json", plan, "study plan")
    return plan


def _validate_plan(dataset_dir: Path, output_dir: Path) -> tuple[dict[str, Any], dict[str, dict[str, tuple[str, ...]]]]:
    plan_path = output_dir / "study_plan.json"
    projection_path = output_dir / "projections.jsonl"
    if not plan_path.is_file() or not projection_path.is_file():
        raise FileNotFoundError("run requires study_plan.json and projections.jsonl from --stage plan")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if plan.get("status") != "PREREGISTERED_BEFORE_OUTCOME_ANALYSIS":
        raise ValueError("study plan is not a preregistration")
    if plan.get("study_id") != STUDY_ID:
        raise ValueError("study plan ID does not match this implementation")
    if plan["implementation"]["script_sha256"] != file_sha256(Path(__file__).resolve()):
        raise ValueError("experiment script changed after preregistration")
    current_inputs = _plan_inputs(dataset_dir)
    if plan["inputs"] != current_inputs:
        raise ValueError("frozen dataset inputs changed after preregistration")
    if plan["projection_bundle"]["sha256"] != file_sha256(projection_path):
        raise ValueError("projection bundle changed after preregistration")
    projections = load_projection_bundle(projection_path)
    if list(projections) != sorted(projections):
        # The bundle renderer sorts IDs; this guards hand-edited bundles.
        raise ValueError("projection bundle is not canonically ordered")
    if set(projections) != set(plan["conditions_in_execution_order"]):
        raise ValueError("projection bundle and planned conditions disagree")
    return plan, projections


def load_observable_events(
    path: Path, *, learner_limit: int | None = None
) -> list[dict[str, Any]]:
    required = {
        "learner_id",
        "item_id",
        "sequence_index",
        "correct",
        "phase",
        "pass_index",
        "grammar_regime",
    }
    events = []
    included_learners: set[str] = set()
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            row = json.loads(line)
            if set(row) != required:
                raise ValueError("observable event schema changed or contains oracle fields")
            learner_id = str(row["learner_id"])
            if learner_limit is not None and learner_id not in included_learners:
                if len(included_learners) >= learner_limit:
                    continue
                included_learners.add(learner_id)
            correct = row["correct"]
            if isinstance(correct, bool) or correct not in (0, 1):
                raise ValueError("observable correct must be integer 0/1")
            phase = str(row["phase"])
            if phase not in {"acquisition", "probe"}:
                raise ValueError(f"unknown event phase {phase}")
            sequence_index = int(row["sequence_index"])
            events.append(
                {
                    **row,
                    "learner_id": learner_id,
                    "sequence_index": sequence_index,
                    "event_id": f"{learner_id}::{sequence_index:04d}",
                    "updates_history": phase == "acquisition",
                    "dataset_split": "train" if phase == "acquisition" else "test",
                }
            )
    if not events:
        raise ValueError("no observable events loaded")
    event_ids = [row["event_id"] for row in events]
    if len(event_ids) != len(set(event_ids)):
        raise ValueError("composite observable event key is not unique")
    by_learner: dict[str, list[int]] = defaultdict(list)
    phase_by_learner: dict[str, list[str]] = defaultdict(list)
    for row in events:
        by_learner[row["learner_id"]].append(row["sequence_index"])
        phase_by_learner[row["learner_id"]].append(row["phase"])
    for learner_id, indices in by_learner.items():
        if indices != list(range(1, len(indices) + 1)):
            raise ValueError(f"non-contiguous event sequence for {learner_id}")
        phases = phase_by_learner[learner_id]
        if "acquisition" in phases[phases.index("probe") :] if "probe" in phases else False:
            raise ValueError(f"acquisition follows probe for {learner_id}")
    return events


def build_observable_feature_matrix(
    events: Sequence[dict[str, Any]],
    projection: dict[str, Sequence[str]],
    *,
    alpha: float = 1.0,
    beta: float = 1.0,
) -> tuple[np.ndarray, list[str]]:
    """Build causal PFA-like features without materialising Python vectors."""

    if alpha <= 0 or beta <= 0:
        raise ValueError("history priors must be positive")
    event_items = {str(row["item_id"]) for row in events}
    if event_items - set(projection):
        raise ValueError("KC projection lacks event items")
    kc_ids = sorted({str(kc) for values in projection.values() for kc in values})
    kc_index = {kc_id: index for index, kc_id in enumerate(kc_ids)}
    x = np.zeros((len(events), 4 + len(kc_ids)), dtype=np.float32)
    attempts: Counter[str] = Counter()
    corrects: Counter[str] = Counter()
    kc_attempts: Counter[tuple[str, str]] = Counter()
    kc_corrects: Counter[tuple[str, str]] = Counter()
    ordered_indices = sorted(
        range(len(events)),
        key=lambda index: (
            str(events[index]["learner_id"]),
            int(events[index]["sequence_index"]),
        ),
    )
    for index in ordered_indices:
        event = events[index]
        learner_id = str(event["learner_id"])
        active = tuple(str(kc) for kc in projection[str(event["item_id"])])
        overall = (corrects[learner_id] + alpha) / (
            attempts[learner_id] + alpha + beta
        )
        if active:
            rates = [
                (kc_corrects[(learner_id, kc_id)] + alpha)
                / (kc_attempts[(learner_id, kc_id)] + alpha + beta)
                for kc_id in active
            ]
            active_rate = sum(rates) / len(rates)
            log_attempts = sum(
                math.log1p(kc_attempts[(learner_id, kc_id)]) for kc_id in active
            ) / len(active)
        else:
            active_rate = overall
            log_attempts = 0.0
        x[index, :4] = overall, active_rate, log_attempts, len(active)
        for kc_id in active:
            x[index, 4 + kc_index[kc_id]] = 1.0
        if bool(event["updates_history"]):
            attempts[learner_id] += 1
            corrects[learner_id] += int(event["correct"])
            for kc_id in active:
                kc_attempts[(learner_id, kc_id)] += 1
                kc_corrects[(learner_id, kc_id)] += int(event["correct"])
    return x, kc_ids


def fit_observable_logistic(
    events: Sequence[dict[str, Any]],
    projection: dict[str, Sequence[str]],
    *,
    random_seed: int = MODEL_SEED,
) -> tuple[np.ndarray, dict[str, Any]]:
    x, kc_ids = build_observable_feature_matrix(events, projection)
    y = np.asarray([int(row["correct"]) for row in events], dtype=np.int8)
    train = np.asarray([row["phase"] == "acquisition" for row in events])
    evaluate = ~train
    if not np.any(train) or not np.any(evaluate):
        raise ValueError("observable logistic requires acquisition and probe rows")
    if len(np.unique(y[train])) != 2:
        raise ValueError("acquisition outcomes require both classes")
    scaler = StandardScaler()
    x_train = scaler.fit_transform(x[train])
    model = LogisticRegression(
        C=1.0,
        max_iter=500,
        random_state=random_seed,
    )
    model.fit(x_train, y[train])
    probabilities = model.predict_proba(scaler.transform(x[evaluate]))[:, 1]
    probabilities = np.clip(probabilities, 1e-6, 1 - 1e-6)
    return probabilities, {
        "hypothesis_kcs": len(kc_ids),
        "features": int(x.shape[1]),
        "training_events": int(train.sum()),
        "evaluation_events": int(evaluate.sum()),
        "iterations": [int(value) for value in model.n_iter_.tolist()],
        "converged": bool(np.max(model.n_iter_) < model.max_iter),
    }


def prediction_metrics(
    targets: Sequence[int] | np.ndarray,
    probabilities: Sequence[float] | np.ndarray,
    *,
    bins: int = ECE_BINS,
) -> dict[str, Any]:
    y = np.asarray(targets, dtype=np.int8)
    p = np.clip(np.asarray(probabilities, dtype=float), 1e-6, 1 - 1e-6)
    if len(y) != len(p):
        raise ValueError("targets and probabilities must pair exactly")
    if not len(y):
        return {
            "n": 0,
            "log_loss": None,
            "brier_score": None,
            "ece": None,
            "auc": None,
            "accuracy": None,
        }
    losses = -(y * np.log(p) + (1 - y) * np.log(1 - p))
    ece = 0.0
    edges = np.linspace(0.0, 1.0, bins + 1)
    for index in range(bins):
        mask = (p >= edges[index]) & (
            p <= edges[index + 1]
            if index == bins - 1
            else p < edges[index + 1]
        )
        if np.any(mask):
            ece += float(np.mean(mask)) * abs(float(np.mean(p[mask]) - np.mean(y[mask])))
    return {
        "n": len(y),
        "log_loss": float(np.mean(losses)),
        "brier_score": float(np.mean((p - y) ** 2)),
        "ece": ece,
        "auc": float(roc_auc_score(y, p)) if len(np.unique(y)) > 1 else None,
        "accuracy": float(np.mean((p >= 0.5) == y)),
    }


def paired_learner_bootstrap(
    evaluation_events: Sequence[dict[str, Any]],
    reference_probabilities: Sequence[float] | np.ndarray,
    candidate_probabilities: Sequence[float] | np.ndarray,
    *,
    repeats: int,
    seed: int,
    reference_id: str,
    candidate_id: str,
) -> dict[str, Any]:
    if repeats < 1:
        raise ValueError("bootstrap repeats must be positive")
    if not evaluation_events:
        raise ValueError("bootstrap requires evaluation events")
    y = np.asarray([int(row["correct"]) for row in evaluation_events], dtype=float)
    reference = np.clip(np.asarray(reference_probabilities, dtype=float), 1e-6, 1 - 1e-6)
    candidate = np.clip(np.asarray(candidate_probabilities, dtype=float), 1e-6, 1 - 1e-6)
    if len(y) != len(reference) or len(y) != len(candidate):
        raise ValueError("bootstrap predictions must exactly pair with events")
    if not np.all(np.isfinite(reference)) or not np.all(np.isfinite(candidate)):
        raise ValueError("bootstrap probabilities must be finite")
    if np.any(reference < 0) or np.any(reference > 1) or np.any(candidate < 0) or np.any(candidate > 1):
        raise ValueError("bootstrap probabilities must lie in [0, 1]")
    learners = sorted({str(row["learner_id"]) for row in evaluation_events})
    learner_index = {learner_id: index for index, learner_id in enumerate(learners)}
    indices = np.asarray(
        [learner_index[str(row["learner_id"])] for row in evaluation_events], dtype=int
    )
    reference_loss = -(y * np.log(reference) + (1 - y) * np.log(1 - reference))
    candidate_loss = -(y * np.log(candidate) + (1 - y) * np.log(1 - candidate))
    delta_loss = candidate_loss - reference_loss
    delta_brier = (candidate - y) ** 2 - (reference - y) ** 2
    counts = np.bincount(indices, minlength=len(learners)).astype(float)
    loss_sums = np.bincount(indices, weights=delta_loss, minlength=len(learners))
    brier_sums = np.bincount(indices, weights=delta_brier, minlength=len(learners))
    rng = np.random.default_rng(seed)
    sampled = rng.integers(0, len(learners), size=(repeats, len(learners)))
    sampled_counts = counts[sampled].sum(axis=1)
    loss_draws = loss_sums[sampled].sum(axis=1) / sampled_counts
    brier_draws = brier_sums[sampled].sum(axis=1) / sampled_counts

    def interval(values: np.ndarray) -> list[float] | None:
        if len(learners) < 2:
            return None
        return [
            float(np.quantile(values, 0.025, method="linear")),
            float(np.quantile(values, 0.975, method="linear")),
        ]

    return {
        "reference_id": reference_id,
        "candidate_id": candidate_id,
        "sign_convention": "candidate_minus_true_kstar; positive favours K*",
        "sampling_unit": "learner",
        "aggregation": "event_weighted",
        "learners": len(learners),
        "events": len(y),
        "repeats": repeats,
        "seed": seed,
        "delta_log_loss": {
            "point_estimate": float(np.mean(delta_loss)),
            "interval_95": interval(loss_draws),
        },
        "delta_brier_score": {
            "point_estimate": float(np.mean(delta_brier)),
            "interval_95": interval(brier_draws),
        },
    }


def _regime_masks(evaluation_events: Sequence[dict[str, Any]]) -> dict[str, np.ndarray]:
    regimes = np.asarray([str(row["grammar_regime"]) for row in evaluation_events])
    return {
        "all_probe": np.ones(len(evaluation_events), dtype=bool),
        "seen": regimes == "seen",
        "unseen_combination": regimes == "unseen_combination",
        "unseen_value": regimes == "unseen_value",
    }


def run_study(
    dataset_dir: Path,
    output_dir: Path,
    *,
    learner_limit: int | None = None,
) -> dict[str, Any]:
    plan, projections = _validate_plan(dataset_dir, output_dir)
    events = load_observable_events(
        dataset_dir / "interactions.jsonl.gz", learner_limit=learner_limit
    )
    learners = sorted({str(row["learner_id"]) for row in events})
    expected_full_learners = int(
        json.loads((dataset_dir / "manifest.json").read_text(encoding="utf-8"))[
            "scale"
        ]["learners"]
    )
    development_only = learner_limit is not None and len(learners) < expected_full_learners
    evaluation_events = [row for row in events if row["phase"] == "probe"]
    evaluation_targets = np.asarray(
        [int(row["correct"]) for row in evaluation_events], dtype=np.int8
    )
    masks = _regime_masks(evaluation_events)
    predictions: dict[str, np.ndarray] = {}
    metrics: dict[str, Any] = {}
    for representation_id in plan["conditions_in_execution_order"]:
        print(f"fit {representation_id}", flush=True)
        probability, model_audit = fit_observable_logistic(
            events, projections[representation_id]
        )
        predictions[representation_id] = probability
        metrics[representation_id] = {
            "model_audit": model_audit,
            "probe_metrics": {
                regime: prediction_metrics(
                    evaluation_targets[mask], probability[mask]
                )
                for regime, mask in masks.items()
            },
        }
    reference = predictions["true_kstar"]
    comparisons = []
    for representation_id in plan["conditions_in_execution_order"]:
        if representation_id == "true_kstar":
            continue
        for regime, mask in masks.items():
            selected_events = [
                row for row, include in zip(evaluation_events, mask, strict=True) if include
            ]
            comparison = paired_learner_bootstrap(
                selected_events,
                reference[mask],
                predictions[representation_id][mask],
                repeats=int(plan["evaluation"]["uncertainty"]["repeats"]),
                seed=int(plan["evaluation"]["uncertainty"]["seed"]),
                reference_id="true_kstar",
                candidate_id=representation_id,
            )
            interval = comparison["delta_log_loss"]["interval_95"]
            if interval is not None and interval[0] > 0:
                interpretation = "cost_supported"
            elif interval is not None and interval[1] < 0:
                interpretation = "candidate_predictive_gain"
            else:
                interpretation = "not_resolved"
            comparisons.append(
                {"grammar_regime": regime, "interpretation": interpretation, **comparison}
            )
    event_key_payload = "\n".join(row["event_id"] for row in evaluation_events) + "\n"
    result = {
        "study_id": STUDY_ID,
        "status": "DEVELOPMENT_ONLY" if development_only else "FINAL_FULL_DATASET_RESULT",
        "plan_sha256": file_sha256(output_dir / "study_plan.json"),
        "projection_bundle_sha256": file_sha256(output_dir / "projections.jsonl"),
        "observable_only": True,
        "private_learner_oracle_read": False,
        "same_evaluation_event_rows_for_every_representation": True,
        "evaluation_event_key_sha256": _sha256_bytes(event_key_payload.encode()),
        "scale": {
            "learners": len(learners),
            "events": len(events),
            "acquisition_events": sum(row["phase"] == "acquisition" for row in events),
            "probe_events": len(evaluation_events),
        },
        "metrics_by_representation": metrics,
        "paired_comparisons": comparisons,
        "result_scope_note": (
            "Predictive differences identify consequences under the declared synthetic world; they do not establish human cognitive KC truth."
        ),
    }
    result_path = (
        output_dir / f"development_results_n{len(learners)}.json"
        if development_only
        else output_dir / "results.json"
    )
    _write_frozen_json(result_path, result, "experiment result")
    print(f"wrote {result_path}", flush=True)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("plan", "run"), required=True)
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--learner-limit",
        type=int,
        help="Development-only nested learner prefix; omit for the final full run.",
    )
    args = parser.parse_args()
    dataset_dir = args.dataset_dir.resolve()
    output_dir = args.output_dir.resolve()
    if args.learner_limit is not None and args.learner_limit < 2:
        parser.error("--learner-limit must be at least 2")
    if args.stage == "plan":
        if args.learner_limit is not None:
            parser.error("--learner-limit is valid only for --stage run")
        plan = create_plan(dataset_dir, output_dir)
        print(
            f"preregistered {len(plan['conditions_in_execution_order'])} conditions at {output_dir}",
            flush=True,
        )
        return 0
    run_study(dataset_dir, output_dir, learner_limit=args.learner_limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
