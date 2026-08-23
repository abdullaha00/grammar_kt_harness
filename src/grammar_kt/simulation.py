"""Generate ontology-independent synthetic learner-item event streams."""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np

from .folds import annotate_items, assignment_for_cells, fold_path, load_fold
from .io import read_json, read_jsonl, repo_path, write_json, write_jsonl
from .items import item_bank_fingerprint
from .kc import evaluate_rule
from .records import compositional_base_event, oracle_interaction, observable_base_event


# Fixed difficulty, response, and split equations

def difficulty(item_id: str, low: float, high: float) -> float:
    fraction = int(hashlib.sha256(item_id.encode()).hexdigest()[:16], 16) / float(
        0xFFFFFFFFFFFFFFFF
    )
    return low + (high - low) * fraction


def sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-value))


def logit(value: float) -> float:
    value = min(max(value, 0.001), 0.999)
    return math.log(value / (1.0 - value))


def split_boundaries(
    event_count: int, train_fraction: float, validation_fraction: float
) -> tuple[int, int]:
    if event_count < 1:
        raise ValueError("simulation requires at least one event per learner")
    if train_fraction <= 0 or validation_fraction <= 0 or train_fraction + validation_fraction >= 1:
        raise ValueError(
            "train and validation fractions must be positive and sum to less than one"
        )
    train_end = int(event_count * train_fraction)
    validation_end = int(event_count * (train_fraction + validation_fraction))
    if event_count >= 3:
        train_end = min(max(train_end, 1), event_count - 2)
        validation_end = min(max(validation_end, train_end + 1), event_count - 1)
    else:
        train_end = max(train_end, 1)
        validation_end = event_count
    return train_end, validation_end


def event_stream_fingerprint(rows: list[dict[str, Any]]) -> str:
    payload = "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def deterministic_draw(seed: int, *parts: object) -> float:
    """Return a stable uniform draw whose value does not depend on row ordering."""

    payload = "|".join([str(seed), *(str(part) for part in parts)])
    return int(hashlib.sha256(payload.encode()).hexdigest()[:16], 16) / float(
        0xFFFFFFFFFFFFFFFF
    )


def response_probability(
    mastery: dict[str, float], active: list[str], item_difficulty: float, params: dict[str, Any]
) -> tuple[float, float, dict[str, float]]:
    """Apply the fixed structural-oracle response equation."""

    pre = {feature_id: mastery[feature_id] for feature_id in active}
    complexity_penalty = float(params["oracle_complexity_penalty"]) * max(
        0, len(active) - 1
    )
    z = (
        sum(logit(pre[feature_id]) for feature_id in active) / len(active)
        - item_difficulty
        - complexity_penalty
    )
    probability = params["probability_floor"] + params["probability_span"] * sigmoid(z)
    return probability, complexity_penalty, pre


# Ontology-independent item → simulation primitive projection

def _frame_type(item: dict[str, Any]) -> str:
    prefix = "frame_type:"
    values = [
        tag.removeprefix(prefix)
        for tag in item["realization_evidence"]["coverage_tags"]
        if tag.startswith(prefix)
    ]
    if len(values) != 1:
        raise ValueError(f"{item['item_id']}: expected exactly one frame_type coverage tag")
    return values[0]


def load_simulation_parameters(path: str | Path) -> dict[str, Any]:
    """Resolve the one-level compatibility alias used by the former default path."""

    selected = repo_path(path)
    params = read_json(selected)
    if "extends" in params:
        base = read_json(selected.parent / params["extends"])
        params = {**base, **{key: value for key, value in params.items() if key != "extends"}}
    return params


def project_oracle_items(
    items: list[dict[str, Any]],
    cells: list[dict[str, Any]],
    params: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Compile fixed structural evidence; these dimensions are not candidate KCs."""

    definitions = params["oracle_features"]
    feature_ids = [row["oracle_feature_id"] for row in definitions]
    if len(feature_ids) != len(set(feature_ids)):
        raise ValueError("simulation oracle feature IDs are duplicated")
    if not feature_ids or any("activation_rule" not in row for row in definitions):
        raise ValueError("simulation oracle features require declarative activation_rule values")
    cell_by_id = {row["canonical_cell_id"]: row["cell"] for row in cells}
    projections = []
    for item in sorted(items, key=lambda row: row["item_id"]):
        cell = cell_by_id.get(item["canonical_cell_id"])
        if cell is None:
            raise RuntimeError(f"oracle item projection has unknown cell: {item['item_id']}")
        opportunity = {
            "cell": cell,
            "realization_operations": item["realization_evidence"]["operations"],
            "agreement_site": item["realization_evidence"]["agreement_site"],
            "frame_type": _frame_type(item),
        }
        evidence = {}
        active = []
        for definition in definitions:
            feature_id = definition["oracle_feature_id"]
            activated, rule_evidence = evaluate_rule(
                definition["activation_rule"], opportunity
            )
            evidence[feature_id] = {
                "activated": activated,
                "activation_rule": definition["activation_rule"],
                "evidence": rule_evidence,
            }
            if activated:
                active.append(feature_id)
        if not active:
            raise RuntimeError(f"fixed simulation oracle leaves item uncovered: {item['item_id']}")
        projections.append(
            {
                "item_id": item["item_id"],
                "canonical_cell_id": item["canonical_cell_id"],
                "canonical_split": item["canonical_split"],
                "oracle_representation_id": params["oracle_representation_id"],
                "oracle_feature_ids": active,
                "activation_evidence": evidence,
            }
        )
    return projections, feature_ids


# Chronological fixed learner events

def simulate_records(
    params: dict[str, Any],
    item_by_id: dict[str, dict[str, Any]],
    oracle_by_item: dict[str, list[str]],
    oracle_feature_ids: list[str],
    train_end_sequence: int,
    validation_end_sequence: int,
    *,
    target_learner: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Use only fixed items, fixed oracle primitives, config, and seed."""

    if set(oracle_by_item) != set(item_by_id):
        raise RuntimeError("oracle item projection does not exactly cover the accepted item bank")
    rng = np.random.default_rng(params["seed"])
    observed: list[dict[str, Any]] = []
    oracle: list[dict[str, Any]] = []
    learners: list[dict[str, Any]] = []
    learner_oracle: list[dict[str, Any]] = []
    base_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    learner_number = 0
    found = False
    for profile_name, profile in params["profiles"].items():
        for _ in range(int(params["learners_per_profile"])):
            learner_number += 1
            learner_id = f"L{learner_number:04d}"
            retain = target_learner is None or learner_id == target_learner
            mastery = {
                feature_id: float(rng.beta(profile["beta_alpha"], profile["beta_beta"]))
                for feature_id in oracle_feature_ids
            }
            initial = dict(mastery)
            order: list[str] = []
            for _pass in range(int(params["item_passes_per_learner"])):
                item_ids = sorted(item_by_id)
                rng.shuffle(item_ids)
                order.extend(item_ids)
            oracle_opportunities: Counter[str] = Counter()
            if retain:
                found = True
                learners.append(
                    {
                        "learner_id": learner_id,
                        "interaction_count": len(order),
                        "stable_learner": True,
                    }
                )
                learner_oracle.append(
                    {
                        "learner_id": learner_id,
                        "profile": profile_name,
                        "learning_rate": profile["learning_rate"],
                        "oracle_representation_id": params["oracle_representation_id"],
                        "initial_mastery": initial,
                    }
                )
            for sequence, item_id_value in enumerate(order, 1):
                item = item_by_id[item_id_value]
                active = oracle_by_item[item_id_value]
                pre = {feature_id: mastery[feature_id] for feature_id in active}
                item_difficulty = difficulty(
                    item_id_value, params["difficulty_min"], params["difficulty_max"]
                )
                complexity_penalty = float(params["oracle_complexity_penalty"]) * max(
                    0, len(active) - 1
                )
                z = (
                    sum(logit(pre[feature_id]) for feature_id in active) / len(active)
                    - item_difficulty
                    - complexity_penalty
                )
                probability = params["probability_floor"] + params["probability_span"] * sigmoid(z)
                draw = float(rng.random())
                correct = int(draw < probability)
                temporal_split = (
                    "train"
                    if sequence <= train_end_sequence
                    else "validation"
                    if sequence <= validation_end_sequence
                    else "test"
                )
                event_id = f"EVENT_{learner_id}_{sequence:03d}"
                timestamp = (
                    base_time + timedelta(days=learner_number, minutes=sequence)
                ).isoformat()
                oracle_indices = {
                    feature_id: oracle_opportunities[feature_id] + 1 for feature_id in active
                }
                if retain:
                    observed.append(
                        {
                            "event_id": event_id,
                            "learner_id": learner_id,
                            "item_id": item_id_value,
                            "canonical_cell_id": item["canonical_cell_id"],
                            "canonical_split": item["canonical_split"],
                            "sequence_index": sequence,
                            "timestamp": timestamp,
                            "correct": correct,
                            "item_difficulty": round(item_difficulty, 8),
                            "dataset_split": temporal_split,
                        }
                    )
                gain = params["correct_gain"] if correct else params["incorrect_gain"]
                for feature_id in active:
                    mastery[feature_id] = min(
                        0.999,
                        max(
                            0.001,
                            mastery[feature_id]
                            + profile["learning_rate"]
                            * (1.0 - mastery[feature_id])
                            * gain,
                        ),
                    )
                    oracle_opportunities[feature_id] += 1
                if retain:
                    oracle.append(
                        {
                            "event_id": event_id,
                            "learner_id": learner_id,
                            "item_id": item_id_value,
                            "profile": profile_name,
                            "oracle_feature_ids": active,
                            "oracle_opportunity_indices": oracle_indices,
                            "pre_mastery": pre,
                            "response_probability": probability,
                            "random_draw": draw,
                            "oracle_complexity_penalty": complexity_penalty,
                            "post_mastery": {
                                feature_id: mastery[feature_id] for feature_id in active
                            },
                        }
                    )
            if target_learner is not None and found:
                return observed, oracle, learners, learner_oracle
    if target_learner is not None and not found:
        raise KeyError(f"learner outside configured population: {target_learner}")
    return observed, oracle, learners, learner_oracle


def simulate_compositional_records(
    params: dict[str, Any],
    item_by_id: dict[str, dict[str, Any]],
    oracle_by_item: dict[str, list[str]],
    oracle_feature_ids: list[str],
) -> dict[str, list[dict[str, Any]]]:
    """Generate development acquisition followed by non-updating held-out probes.

    The acquisition RNG is independent of the ordinary temporal benchmark. Probe
    draws are keyed by learner and item, so reordering probes cannot change their
    probabilities or outcomes. Every probe for a learner reads the same frozen
    post-development oracle state.
    """

    protocol = params.get("compositional_protocol")
    if not isinstance(protocol, dict):
        raise ValueError("simulation config requires compositional_protocol")
    acquisition_passes = int(protocol["acquisition_passes"])
    probe_repetitions = int(protocol.get("probe_repetitions", 1))
    if acquisition_passes < 1 or probe_repetitions < 1:
        raise ValueError("compositional acquisition/probe counts must be positive")
    protocol_seed = int(params["seed"]) + int(protocol["seed_offset"])
    rng = np.random.default_rng(protocol_seed)
    development_ids = sorted(
        item_id
        for item_id, item in item_by_id.items()
        if item["canonical_split"] == "development"
    )
    compositional_ids = sorted(
        item_id
        for item_id, item in item_by_id.items()
        if item["canonical_split"] == "compositional_holdout"
    )
    novel_ids = sorted(
        item_id
        for item_id, item in item_by_id.items()
        if item["canonical_split"] == "novel_feature_holdout"
    )
    if not development_ids:
        raise RuntimeError("Phase-D protocol requires development items")
    acquisition_count = len(development_ids) * acquisition_passes
    train_end, validation_end = split_boundaries(
        acquisition_count,
        float(params["train_fraction"]),
        float(params["validation_fraction"]),
    )
    base_time = datetime(2027, 1, 1, tzinfo=timezone.utc)
    acquisition_events: list[dict[str, Any]] = []
    compositional_probes: list[dict[str, Any]] = []
    novel_probes: list[dict[str, Any]] = []
    oracle_acquisition: list[dict[str, Any]] = []
    oracle_probes: list[dict[str, Any]] = []
    frozen_states: list[dict[str, Any]] = []
    learners: list[dict[str, Any]] = []
    learner_number = 0
    for profile_name, profile in params["profiles"].items():
        for _ in range(int(params["learners_per_profile"])):
            learner_number += 1
            learner_id = f"L{learner_number:04d}"
            mastery = {
                feature_id: float(rng.beta(profile["beta_alpha"], profile["beta_beta"]))
                for feature_id in oracle_feature_ids
            }
            initial = dict(mastery)
            acquisition_order: list[str] = []
            for _pass in range(acquisition_passes):
                pass_ids = list(development_ids)
                rng.shuffle(pass_ids)
                acquisition_order.extend(pass_ids)
            oracle_opportunities: Counter[str] = Counter()
            for sequence, item_id_value in enumerate(acquisition_order, 1):
                item = item_by_id[item_id_value]
                active = oracle_by_item[item_id_value]
                item_difficulty = difficulty(
                    item_id_value, params["difficulty_min"], params["difficulty_max"]
                )
                probability, complexity_penalty, pre = response_probability(
                    mastery, active, item_difficulty, params
                )
                draw = float(rng.random())
                correct = int(draw < probability)
                temporal_split = (
                    "train"
                    if sequence <= train_end
                    else "validation"
                    if sequence <= validation_end
                    else "test"
                )
                event_id = f"COMP_ACQ_{learner_id}_{sequence:03d}"
                timestamp = (
                    base_time + timedelta(days=learner_number, minutes=sequence)
                ).isoformat()
                acquisition_events.append(
                    {
                        "event_id": event_id,
                        "learner_id": learner_id,
                        "item_id": item_id_value,
                        "canonical_cell_id": item["canonical_cell_id"],
                        "canonical_split": "development",
                        "sequence_index": sequence,
                        "timestamp": timestamp,
                        "correct": correct,
                        "item_difficulty": round(item_difficulty, 8),
                        "dataset_split": temporal_split,
                        "evaluation_role": "acquisition",
                        "probe_type": "development_acquisition",
                    }
                )
                indices = {
                    feature_id: oracle_opportunities[feature_id] + 1 for feature_id in active
                }
                gain = params["correct_gain"] if correct else params["incorrect_gain"]
                for feature_id in active:
                    mastery[feature_id] = min(
                        0.999,
                        max(
                            0.001,
                            mastery[feature_id]
                            + profile["learning_rate"]
                            * (1.0 - mastery[feature_id])
                            * gain,
                        ),
                    )
                    oracle_opportunities[feature_id] += 1
                oracle_acquisition.append(
                    {
                        "event_id": event_id,
                        "learner_id": learner_id,
                        "item_id": item_id_value,
                        "profile": profile_name,
                        "oracle_feature_ids": active,
                        "oracle_opportunity_indices": indices,
                        "pre_mastery": pre,
                        "post_mastery": {
                            feature_id: mastery[feature_id] for feature_id in active
                        },
                        "response_probability": probability,
                        "random_draw": draw,
                        "oracle_complexity_penalty": complexity_penalty,
                    }
                )
            frozen_mastery = dict(mastery)
            frozen_states.append(
                {
                    "learner_id": learner_id,
                    "profile": profile_name,
                    "oracle_representation_id": params["oracle_representation_id"],
                    "initial_mastery": initial,
                    "post_development_mastery": frozen_mastery,
                    "development_oracle_opportunities": dict(sorted(oracle_opportunities.items())),
                }
            )
            learners.append(
                {
                    "learner_id": learner_id,
                    "development_acquisition_events": acquisition_count,
                    "compositional_probe_events": len(compositional_ids) * probe_repetitions,
                    "novel_feature_probe_events": len(novel_ids) * probe_repetitions,
                }
            )
            probe_sequence = acquisition_count
            for probe_type, probe_ids, destination in (
                ("compositional_holdout", compositional_ids, compositional_probes),
                ("novel_feature_holdout", novel_ids, novel_probes),
            ):
                for repetition in range(1, probe_repetitions + 1):
                    for item_id_value in probe_ids:
                        probe_sequence += 1
                        item = item_by_id[item_id_value]
                        active = oracle_by_item[item_id_value]
                        item_difficulty = difficulty(
                            item_id_value, params["difficulty_min"], params["difficulty_max"]
                        )
                        probability, complexity_penalty, pre = response_probability(
                            frozen_mastery, active, item_difficulty, params
                        )
                        event_id = (
                            f"COMP_PROBE_{probe_type.upper()}_{learner_id}_"
                            f"{item_id_value}_{repetition:02d}"
                        )
                        draw = deterministic_draw(protocol_seed, event_id)
                        correct = int(draw < probability)
                        timestamp = (
                            base_time + timedelta(days=learner_number, minutes=probe_sequence)
                        ).isoformat()
                        destination.append(
                            {
                                "event_id": event_id,
                                "learner_id": learner_id,
                                "item_id": item_id_value,
                                "canonical_cell_id": item["canonical_cell_id"],
                                "canonical_split": probe_type,
                                "sequence_index": probe_sequence,
                                "timestamp": timestamp,
                                "correct": correct,
                                "item_difficulty": round(item_difficulty, 8),
                                "dataset_split": "test",
                                "evaluation_role": "probe",
                                "probe_type": probe_type,
                            }
                        )
                        oracle_probes.append(
                            {
                                "event_id": event_id,
                                "learner_id": learner_id,
                                "item_id": item_id_value,
                                "profile": profile_name,
                                "oracle_feature_ids": active,
                                "frozen_post_development_mastery": pre,
                                "response_probability": probability,
                                "random_draw": draw,
                                "oracle_complexity_penalty": complexity_penalty,
                                "oracle_update_applied": False,
                            }
                        )
    return {
        "acquisition_events": acquisition_events,
        "compositional_probe_events": compositional_probes,
        "novel_feature_probe_events": novel_probes,
        "oracle_acquisition_evidence": oracle_acquisition,
        "oracle_probe_evidence": oracle_probes,
        "learner_frozen_oracle_state": frozen_states,
        "learners": learners,
    }


def audit_compositional_simulation(
    rows: dict[str, list[dict[str, Any]]],
    item_by_id: dict[str, dict[str, Any]],
    protocol: dict[str, Any],
) -> dict[str, Any]:
    acquisition = rows["acquisition_events"]
    comp = rows["compositional_probe_events"]
    novel = rows["novel_feature_probe_events"]
    probes = comp + novel
    errors: list[str] = []
    for row in acquisition + probes:
        try:
            compositional_base_event(row, label=row["event_id"])
        except ValueError as error:
            errors.append(str(error))
    if any(row["canonical_split"] != "development" for row in acquisition):
        errors.append("held-out item occurred in development acquisition")
    expected_development = {
        item_id
        for item_id, item in item_by_id.items()
        if item["canonical_split"] == "development"
    }
    expected_comp = {
        item_id
        for item_id, item in item_by_id.items()
        if item["canonical_split"] == "compositional_holdout"
    }
    expected_novel = {
        item_id
        for item_id, item in item_by_id.items()
        if item["canonical_split"] == "novel_feature_holdout"
    }
    learner_ids = {row["learner_id"] for row in rows["learners"]}
    repetitions = int(protocol.get("probe_repetitions", 1))
    acquisition_passes = int(protocol["acquisition_passes"])
    for learner_id in learner_ids:
        learner_acq = [row for row in acquisition if row["learner_id"] == learner_id]
        learner_comp = [row for row in comp if row["learner_id"] == learner_id]
        learner_novel = [row for row in novel if row["learner_id"] == learner_id]
        if Counter(row["item_id"] for row in learner_acq) != Counter(
            {item_id: acquisition_passes for item_id in expected_development}
        ):
            errors.append(f"{learner_id}: development acquisition schedule invalid")
        if Counter(row["item_id"] for row in learner_comp) != Counter(
            {item_id: repetitions for item_id in expected_comp}
        ):
            errors.append(f"{learner_id}: compositional probe schedule invalid")
        if Counter(row["item_id"] for row in learner_novel) != Counter(
            {item_id: repetitions for item_id in expected_novel}
        ):
            errors.append(f"{learner_id}: novel probe schedule invalid")
    oracle_probe_by_event = {row["event_id"]: row for row in rows["oracle_probe_evidence"]}
    if set(oracle_probe_by_event) != {row["event_id"] for row in probes}:
        errors.append("observable/private probe alignment mismatch")
    if any(row["oracle_update_applied"] for row in rows["oracle_probe_evidence"]):
        errors.append("a held-out probe updated frozen oracle mastery")
    return {
        "status": "PASS" if not errors else "FAIL",
        "errors": errors[:100],
        "error_count": len(errors),
        "protocol_id": protocol["protocol_id"],
        "learners": len(learner_ids),
        "development_items": len(expected_development),
        "compositional_items": len(expected_comp),
        "novel_feature_items": len(expected_novel),
        "acquisition_events": len(acquisition),
        "compositional_probe_events": len(comp),
        "novel_feature_probe_events": len(novel),
        "acquisition_event_stream_sha256": event_stream_fingerprint(acquisition),
        "compositional_probe_stream_sha256": event_stream_fingerprint(comp),
        "novel_feature_probe_stream_sha256": event_stream_fingerprint(novel),
        "all_probe_stream_sha256": event_stream_fingerprint(probes),
        "holdout_in_acquisition": False,
        "probe_oracle_updates": False,
        "observable_contains_candidate_kcs": any(
            {"kc_ids", "opportunity_indices"} & set(row) for row in acquisition + probes
        ),
    }


def audit_simulation(
    observed: list[dict[str, Any]],
    oracle: list[dict[str, Any]],
    learners: list[dict[str, Any]],
    items: dict[str, dict[str, Any]],
    oracle_by_item: dict[str, list[str]],
    expected_events: int,
) -> dict[str, Any]:
    errors: list[str] = []
    by_learner: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in observed:
        try:
            observable_base_event(row, label=row["event_id"])
        except ValueError as error:
            errors.append(str(error))
        by_learner[row["learner_id"]].append(row)
    for row in oracle:
        try:
            oracle_interaction(row, label=row["event_id"])
        except ValueError as error:
            errors.append(str(error))
        if row["oracle_feature_ids"] != oracle_by_item.get(row["item_id"]):
            errors.append(f"{row['event_id']}: oracle features differ from fixed item projection")
    for learner_id, rows in by_learner.items():
        rows.sort(key=lambda row: row["sequence_index"])
        if len(rows) != expected_events or [row["sequence_index"] for row in rows] != list(
            range(1, expected_events + 1)
        ):
            errors.append(f"{learner_id}: sequence shape invalid")
        if any(
            rows[index]["timestamp"] >= rows[index + 1]["timestamp"]
            for index in range(len(rows) - 1)
        ):
            errors.append(f"{learner_id}: timestamps not strictly increasing")
        item_counts = Counter(row["item_id"] for row in rows)
        if set(item_counts) != set(items) or len(set(item_counts.values())) != 1:
            errors.append(f"{learner_id}: complete item passes invalid")
    if [row["event_id"] for row in observed] != [row["event_id"] for row in oracle]:
        errors.append("observable/oracle event alignment mismatch")
    return {
        "status": "PASS" if not errors else "FAIL",
        "errors": errors[:100],
        "error_count": len(errors),
        "learners": len(learners),
        "interactions": len(observed),
        "items": len(items),
        "all_items_retained": all(
            set(row["item_id"] for row in rows) == set(items) for rows in by_learner.values()
        ),
        "oracle_rows": len(oracle),
        "observable_oracle_alignment": [row["event_id"] for row in observed]
        == [row["event_id"] for row in oracle],
        "observable_contains_candidate_kcs": any(
            {"kc_ids", "opportunity_indices"} & set(row) for row in observed
        ),
        "evaluated_ontology_inputs_read": False,
    }


# Full stage

def run(run_dir: Path, settings: dict[str, Any]) -> dict[str, Any]:
    output = run_dir / "simulation"
    output.mkdir(parents=True, exist_ok=False)
    params = load_simulation_parameters(settings["parameters"])
    params["seed"] = int(settings["seed"])
    items = read_jsonl(run_dir / "items" / "validation" / "accepted_items.jsonl")
    cells = read_jsonl(run_dir / "canonical" / "canonical_cells.jsonl")
    manifest = load_fold(fold_path(settings))
    items = annotate_items(items, assignment_for_cells(cells, manifest))
    item_by_id = {row["item_id"]: row for row in items}
    projections, feature_ids = project_oracle_items(items, cells, params)
    oracle_by_item = {row["item_id"]: row["oracle_feature_ids"] for row in projections}
    event_total = len(items) * int(params["item_passes_per_learner"])
    train_end, validation_end = split_boundaries(
        event_total,
        float(params["train_fraction"]),
        float(params["validation_fraction"]),
    )
    observed, oracle, learners, learner_oracle = simulate_records(
        params,
        item_by_id,
        oracle_by_item,
        feature_ids,
        train_end,
        validation_end,
    )
    audit = audit_simulation(
        observed, oracle, learners, item_by_id, oracle_by_item, event_total
    )
    audit.update(
        {
            "oracle_representation_id": params["oracle_representation_id"],
            "oracle_feature_ids": feature_ids,
            "oracle_feature_item_support": dict(
                sorted(
                    Counter(
                        feature_id
                        for row in projections
                        for feature_id in row["oracle_feature_ids"]
                    ).items()
                )
            ),
            "intrinsic_item_bank_sha256": item_bank_fingerprint(items),
            "fold_id": manifest["fold_id"],
            "base_event_stream_sha256": event_stream_fingerprint(observed),
            "temporal_split_warning": (
                "two complete shuffled item passes are split chronologically; canonical holdout items "
                "can occur in temporal training, so this ordinary stream is only a technical benchmark; "
                "use simulation/compositional for development-only compositional evaluation"
            ),
            "claim_boundary": (
                "Simulation primitives are controlled structural data-generating dimensions, "
                "not claimed human knowledge components."
            ),
        }
    )
    if audit["status"] != "PASS":
        raise RuntimeError(f"simulation audit failed: {audit['errors'][:5]}")
    compositional_rows = simulate_compositional_records(
        params, item_by_id, oracle_by_item, feature_ids
    )
    compositional_audit = audit_compositional_simulation(
        compositional_rows, item_by_id, params["compositional_protocol"]
    )
    if compositional_audit["status"] != "PASS":
        raise RuntimeError(
            f"compositional simulation audit failed: {compositional_audit['errors'][:5]}"
        )
    write_jsonl(output / "oracle_item_projection.jsonl", projections)
    write_jsonl(output / "base_events.jsonl", observed)
    write_jsonl(output / "observable_interactions.jsonl", observed)
    write_jsonl(output / "oracle_interactions.jsonl", oracle)
    write_jsonl(output / "learners.jsonl", learners)
    write_jsonl(output / "learner_parameters.oracle.jsonl", learner_oracle)
    write_json(output / "audit.json", audit)
    compositional_output = output / "compositional"
    for name, rows in compositional_rows.items():
        write_jsonl(compositional_output / f"{name}.jsonl", rows)
    write_json(
        compositional_output / "audit.json",
        {
            **compositional_audit,
            "intrinsic_item_bank_sha256": audit["intrinsic_item_bank_sha256"],
            "fold_id": manifest["fold_id"],
            "oracle_representation_id": params["oracle_representation_id"],
            "fixed_post_development_oracle_state": True,
            "probe_draws_order_independent": True,
            "candidate_ontology_inputs_read": False,
            "claim_boundary": audit["claim_boundary"],
        },
    )
    return {
        "seed": params["seed"],
        "oracle_representation_id": params["oracle_representation_id"],
        "oracle_features": len(feature_ids),
        "learners": len(learners),
        "items": len(items),
        "events_per_learner": event_total,
        "split_boundaries": {"train_end": train_end, "validation_end": validation_end},
        "interactions": len(observed),
        "base_event_stream_sha256": audit["base_event_stream_sha256"],
        "observable_oracle_separate": True,
        "compositional_protocol_id": compositional_audit["protocol_id"],
        "development_acquisition_events": compositional_audit["acquisition_events"],
        "compositional_probe_events": compositional_audit[
            "compositional_probe_events"
        ],
        "novel_feature_probe_events": compositional_audit[
            "novel_feature_probe_events"
        ],
        "all_probe_stream_sha256": compositional_audit["all_probe_stream_sha256"],
    }
