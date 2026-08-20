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

from .io import read_json, read_jsonl, repo_path, write_json, write_jsonl
from .items import item_bank_fingerprint
from .records import oracle_interaction, observable_base_event


ORACLE_RULES = {
    "ORACLE_FINITE_FORM",
    "ORACLE_FINITE_AGREEMENT",
    "ORACLE_PERFECT_DEPENDENCY",
    "ORACLE_PROGRESSIVE_DEPENDENCY",
    "ORACLE_PASSIVE_DEPENDENCY",
    "ORACLE_NEGATION",
    "ORACLE_OPERATOR_INVERSION",
    "ORACLE_DO_SUPPORT",
    "ORACLE_CENTRAL_MODAL",
    "ORACLE_IMPERATIVE",
}


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


def _feature_active(
    feature_id: str, item: dict[str, Any], cell: dict[str, str]
) -> tuple[bool, str]:
    operations = set(item["realization_evidence"]["operations"])
    agreement_site = item["realization_evidence"]["agreement_site"]
    frame_type = _frame_type(item)
    if feature_id == "ORACLE_FINITE_FORM":
        active = cell["tense"] in {"present", "past"}
        return active, f"tense={cell['tense']}"
    if feature_id == "ORACLE_FINITE_AGREEMENT":
        active = (
            agreement_site == "be"
            or (
                cell["tense"] == "present"
                and agreement_site in {"main_verb", "do", "have"}
            )
            or (frame_type == "copular" and cell["tense"] == "past")
        )
        return active, (
            f"tense={cell['tense']};agreement_site={agreement_site};frame_type={frame_type}"
        )
    if feature_id == "ORACLE_PERFECT_DEPENDENCY":
        active = cell["aspect"] in {"perfect", "perfect_progressive"}
        return active, f"aspect={cell['aspect']}"
    if feature_id == "ORACLE_PROGRESSIVE_DEPENDENCY":
        active = cell["aspect"] in {"progressive", "perfect_progressive"}
        return active, f"aspect={cell['aspect']}"
    if feature_id == "ORACLE_PASSIVE_DEPENDENCY":
        return cell["voice"] == "passive", f"voice={cell['voice']}"
    if feature_id == "ORACLE_NEGATION":
        return cell["polarity"] == "negative", f"polarity={cell['polarity']}"
    if feature_id == "ORACLE_OPERATOR_INVERSION":
        return "operator_inversion" in operations, f"operations={sorted(operations)}"
    if feature_id == "ORACLE_DO_SUPPORT":
        active = bool({"do_support", "do_support_negation"} & operations)
        return active, f"operations={sorted(operations)}"
    if feature_id == "ORACLE_CENTRAL_MODAL":
        return cell["modal"] != "none", f"modal={cell['modal']}"
    if feature_id == "ORACLE_IMPERATIVE":
        return cell["clause"] == "imperative", f"clause={cell['clause']}"
    raise ValueError(f"unknown simulation primitive: {feature_id}")


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
    if set(feature_ids) != ORACLE_RULES:
        raise ValueError(
            "structural oracle config must declare exactly the implemented v0 primitives: "
            f"missing={sorted(ORACLE_RULES - set(feature_ids))}, "
            f"unknown={sorted(set(feature_ids) - ORACLE_RULES)}"
        )
    cell_by_id = {row["canonical_cell_id"]: row["cell"] for row in cells}
    projections = []
    for item in sorted(items, key=lambda row: row["item_id"]):
        cell = cell_by_id.get(item["canonical_cell_id"])
        if cell is None:
            raise RuntimeError(f"oracle item projection has unknown cell: {item['item_id']}")
        evidence = {}
        active = []
        for feature_id in feature_ids:
            activated, reason = _feature_active(feature_id, item, cell)
            evidence[feature_id] = {"activated": activated, "reason": reason}
            if activated:
                active.append(feature_id)
        if not active:
            raise RuntimeError(f"fixed simulation oracle leaves item uncovered: {item['item_id']}")
        projections.append(
            {
                "item_id": item["item_id"],
                "canonical_cell_id": item["canonical_cell_id"],
                "canonical_split": item["generation_metadata"]["canonical_split"],
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
                            "canonical_split": item["generation_metadata"]["canonical_split"],
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
    params = read_json(repo_path(settings["parameters"]))
    params["seed"] = int(settings["seed"])
    items = read_jsonl(run_dir / "items" / "validation" / "accepted_items.jsonl")
    cells = read_jsonl(run_dir / "canonical" / "canonical_cells.jsonl")
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
            "item_bank_sha256": item_bank_fingerprint(items),
            "base_event_stream_sha256": event_stream_fingerprint(observed),
            "temporal_split_warning": (
                "two complete shuffled item passes are split chronologically; canonical holdout items "
                "can occur in temporal training and Phase D must change this before compositional KT claims"
            ),
            "claim_boundary": (
                "Simulation primitives are controlled structural data-generating dimensions, "
                "not claimed human knowledge components."
            ),
        }
    )
    if audit["status"] != "PASS":
        raise RuntimeError(f"simulation audit failed: {audit['errors'][:5]}")
    write_jsonl(output / "oracle_item_projection.jsonl", projections)
    write_jsonl(output / "base_events.jsonl", observed)
    write_jsonl(output / "observable_interactions.jsonl", observed)
    write_jsonl(output / "oracle_interactions.jsonl", oracle)
    write_jsonl(output / "learners.jsonl", learners)
    write_jsonl(output / "learner_parameters.oracle.jsonl", learner_oracle)
    write_json(output / "audit.json", audit)
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
    }
