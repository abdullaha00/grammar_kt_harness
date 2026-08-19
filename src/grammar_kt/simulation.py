"""Generate the current transparent synthetic chronological interaction process."""

from __future__ import annotations

import csv
import hashlib
import math
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np

from .io import read_json, read_jsonl, repo_path, write_json, write_jsonl
from .records import FORBIDDEN_OBSERVABLE_FIELDS, observable_interaction


# Response and learning equations

def difficulty(item_id: str, low: float, high: float) -> float:
    fraction = int(hashlib.sha256(item_id.encode()).hexdigest()[:16], 16) / float(0xFFFFFFFFFFFFFFFF)
    return low + (high - low) * fraction


def sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-value))


def logit(value: float) -> float:
    value = min(max(value, 0.001), 0.999)
    return math.log(value / (1.0 - value))


def split_boundaries(event_count: int, train_fraction: float, validation_fraction: float) -> tuple[int, int]:
    if event_count < 1:
        raise ValueError("simulation requires at least one event per learner")
    if train_fraction <= 0 or validation_fraction <= 0 or train_fraction + validation_fraction >= 1:
        raise ValueError("train and validation fractions must be positive and sum to less than one")
    train_end = int(event_count * train_fraction)
    validation_end = int(event_count * (train_fraction + validation_fraction))
    if event_count >= 3:
        train_end = min(max(train_end, 1), event_count - 2)
        validation_end = min(max(validation_end, train_end + 1), event_count - 1)
    else:
        train_end = max(train_end, 1)
        validation_end = event_count
    return train_end, validation_end


# Q-matrix input and simulation audit

def read_q_matrix(path: Path) -> tuple[list[str], dict[str, list[str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows or "item_id" not in rows[0]:
        raise RuntimeError("Q-matrix is empty or lacks item_id")
    kc_ids = [key for key in rows[0] if key != "item_id"]
    return kc_ids, {
        row["item_id"]: [kc_id for kc_id in kc_ids if row[kc_id] == "1"]
        for row in rows
    }


def audit_simulation(observed: list[dict[str, Any]], oracle: list[dict[str, Any]], learners: list[dict[str, Any]], items: dict[str, dict[str, Any]], expected_events: int) -> dict[str, Any]:
    errors: list[str] = []
    by_learner: dict[str, list[dict[str, Any]]] = defaultdict(list)
    multi_kc_rows = 0
    for row in observed:
        by_learner[row["learner_id"]].append(row)
        leaked = FORBIDDEN_OBSERVABLE_FIELDS & set(row)
        if leaked:
            errors.append(f"{row['event_id']}: oracle/content leakage {sorted(leaked)}")
        if row["correct"] not in {0, 1}:
            errors.append(f"{row['event_id']}: nonbinary outcome")
        multi_kc_rows += int(len(row["kc_ids"]) > 1)
    minimum = None
    for learner_id, rows in by_learner.items():
        rows.sort(key=lambda row: row["sequence_index"])
        if len(rows) != expected_events or [row["sequence_index"] for row in rows] != list(range(1, expected_events + 1)):
            errors.append(f"{learner_id}: sequence shape invalid")
        if any(rows[index]["timestamp"] >= rows[index + 1]["timestamp"] for index in range(len(rows) - 1)):
            errors.append(f"{learner_id}: timestamps not strictly increasing")
        item_counts = Counter(row["item_id"] for row in rows)
        if set(item_counts) != set(items) or len(set(item_counts.values())) != 1:
            errors.append(f"{learner_id}: complete item passes invalid")
        counts: Counter[str] = Counter()
        for row in rows:
            expected = {kc: counts[kc] + 1 for kc in row["kc_ids"]}
            if row["opportunity_indices"] != expected:
                errors.append(f"{row['event_id']}: opportunity index is not prior count + 1")
            counts.update(row["kc_ids"])
        current = min(counts.values()) if counts else 0
        minimum = current if minimum is None else min(minimum, current)
    if [row["event_id"] for row in observed] != [row["event_id"] for row in oracle]:
        errors.append("observable/oracle event alignment mismatch")
    return {
        "status": "PASS" if not errors else "FAIL",
        "errors": errors[:100],
        "error_count": len(errors),
        "learners": len(learners),
        "interactions": len(observed),
        "items": len(items),
        "multi_kc_rows": multi_kc_rows,
        "minimum_opportunities_per_learner_kc": minimum,
        "oracle_rows": len(oracle),
        "observable_oracle_alignment": not any("alignment" in error for error in errors),
        "observable_forbidden_keys": sorted(FORBIDDEN_OBSERVABLE_FIELDS),
        "leakage_errors": sum("leakage" in error for error in errors),
    }


# Chronological learner events

def simulate_records(
    params: dict[str, Any],
    item_by_id: dict[str, dict[str, Any]],
    q_by_item: dict[str, list[str]],
    kc_ids: list[str],
    train_end_sequence: int,
    validation_end_sequence: int,
    *,
    target_learner: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Execute the reference RNG stream, optionally retaining one learner only."""

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
                kc: float(rng.beta(profile["beta_alpha"], profile["beta_beta"]))
                for kc in kc_ids
            }
            initial = dict(mastery)
            order: list[str] = []
            for _pass in range(int(params["item_passes_per_learner"])):
                item_ids = sorted(item_by_id)
                rng.shuffle(item_ids)
                order.extend(item_ids)
            opportunities: Counter[str] = Counter()
            if retain:
                found = True
                learners.append({"learner_id": learner_id, "interaction_count": len(order), "stable_learner": True})
                learner_oracle.append(
                    {
                        "learner_id": learner_id,
                        "profile": profile_name,
                        "learning_rate": profile["learning_rate"],
                        "initial_mastery": initial,
                    }
                )
            for sequence, item_id_value in enumerate(order, 1):
                item = item_by_id[item_id_value]
                active = q_by_item[item_id_value]
                pre = {kc: mastery[kc] for kc in active}
                item_difficulty = difficulty(item_id_value, params["difficulty_min"], params["difficulty_max"])
                z = (
                    sum(logit(pre[kc]) for kc in active) / len(active)
                    - item_difficulty
                    - params["multi_kc_penalty"] * (len(active) - 1)
                )
                probability = params["probability_floor"] + params["probability_span"] * sigmoid(z)
                draw = float(rng.random())
                correct = int(draw < probability)
                current_opportunities = {kc: opportunities[kc] + 1 for kc in active}
                split = (
                    "train" if sequence <= train_end_sequence
                    else "validation" if sequence <= validation_end_sequence
                    else "test"
                )
                event_id = f"EVENT_{learner_id}_{sequence:03d}"
                timestamp = (base_time + timedelta(days=learner_number, minutes=sequence)).isoformat()
                if retain:
                    observed.append(
                        {
                            "event_id": event_id,
                            "learner_id": learner_id,
                            "item_id": item_id_value,
                            "sequence_index": sequence,
                            "timestamp": timestamp,
                            "correct": correct,
                            "kc_ids": active,
                            "opportunity_indices": current_opportunities,
                            "canonical_cell_id": item["canonical_cell_id"],
                            "item_difficulty": round(item_difficulty, 8),
                            "dataset_split": split,
                        }
                    )
                gain = params["correct_gain"] if correct else params["incorrect_gain"]
                for kc in active:
                    mastery[kc] = min(
                        0.999,
                        max(0.001, mastery[kc] + profile["learning_rate"] * (1.0 - mastery[kc]) * gain),
                    )
                    opportunities[kc] += 1
                if retain:
                    oracle.append(
                        {
                            "event_id": event_id,
                            "learner_id": learner_id,
                            "item_id": item_id_value,
                            "profile": profile_name,
                            "pre_mastery": pre,
                            "response_probability": probability,
                            "random_draw": draw,
                            "post_mastery": {kc: mastery[kc] for kc in active},
                        }
                    )
            if target_learner is not None and found:
                return observed, oracle, learners, learner_oracle
    if target_learner is not None and not found:
        raise KeyError(f"learner outside configured population: {target_learner}")
    return observed, oracle, learners, learner_oracle


# Full stage

def run(run_dir: Path, settings: dict[str, Any]) -> dict[str, Any]:
    output = run_dir / "simulation"
    output.mkdir(parents=True, exist_ok=False)
    items_path = run_dir / "items" / "validation" / "accepted_items.jsonl"
    q_path = run_dir / "qmatrix" / "q_matrix.csv"
    params = read_json(repo_path(settings["parameters"]))
    params["seed"] = int(settings["seed"])
    items = read_jsonl(items_path)
    item_by_id = {row["item_id"]: row for row in items}
    q_kcs, q_by_item = read_q_matrix(q_path)
    if not q_kcs or set(q_by_item) != set(item_by_id):
        raise RuntimeError("Q-matrix dimensions do not match the accepted item inputs")
    if any(not active for active in q_by_item.values()):
        raise RuntimeError("Q-matrix contains an item with no active KC")
    for item_id_value, item in item_by_id.items():
        if item["all_kc_ids"] != q_by_item[item_id_value]:
            raise RuntimeError(f"accepted item labels differ from Q row: {item_id_value}")
    event_total = len(items) * int(params["item_passes_per_learner"])
    train_end, validation_end = split_boundaries(
        event_total,
        float(params["train_fraction"]),
        float(params["validation_fraction"]),
    )

    observed, oracle, learners, learner_oracle = simulate_records(
        params, item_by_id, q_by_item, q_kcs, train_end, validation_end
    )
    audit = audit_simulation(observed, oracle, learners, item_by_id, event_total)
    if audit["status"] != "PASS":
        raise RuntimeError(f"simulation audit failed: {audit['errors'][:5]}")
    observed_path = output / "observable_interactions.jsonl"
    oracle_path = output / "oracle_interactions.jsonl"
    learners_path = output / "learners.jsonl"
    learner_oracle_path = output / "learner_parameters.oracle.jsonl"
    audit_path = output / "audit.json"
    write_jsonl(observed_path, observed)
    write_jsonl(oracle_path, oracle)
    write_jsonl(learners_path, learners)
    write_jsonl(learner_oracle_path, learner_oracle)
    write_json(audit_path, audit)
    for row in observed:
        observable_interaction(row, label=row["event_id"])
    return {
        "seed": params["seed"],
        "learners": len(learners),
        "events_per_learner": event_total,
        "split_boundaries": {"train_end": train_end, "validation_end": validation_end},
        "interactions": len(observed),
        "observable_oracle_separate": True,
    }
