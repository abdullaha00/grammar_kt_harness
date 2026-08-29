#!/usr/bin/env python3
"""Measure selected-KC stability over staged learner supports and seeds.

The experiment deliberately reuses the finalized GrammarCells, fixed item bank,
semantic fold, and candidate inventory.  It performs no normalisation, item
generation, validation, or model call.  The staged design has nine conditions:
five nested learner supports on the reference seed and five full-support seeds,
with the shared reference/full-support condition counted once.
"""

from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import re
import shutil
import sys
from collections import Counter
from pathlib import Path
from statistics import mean, median
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from grammar_kt.io import read_jsonl, read_yaml, write_json, write_yaml
from grammar_kt.kc_selection import select_kcs
from grammar_kt.simulate import materialize_latent_world, simulate_frozen_probes


DEFAULT_DATASET = ROOT / "data/grammar_kt_medium_v1"
DEFAULT_OUTPUT = ROOT / "reports/phase6/artifacts/selection_stability_v1"
WORLD_PATH = ROOT / "modules/simulation/worlds/phase4_mixed.yaml"
PROTOCOL_PATH = ROOT / "modules/simulation/protocol.yaml"
SELECTION_PATH = ROOT / "modules/kcs/selection.yaml"
SCHEMA_PATH = ROOT / "modules/grammar/canonical/schema.yaml"

REFERENCE_SEED = 20260827
SEEDS = (20260827, 20260828, 20260829, 20260830, 20260831)
FULL_LEARNERS = 1000
NESTED_LEARNERS = (60, 120, 240, 500, 1000)

NO_MODEL_PROVENANCE = {
    "model_calls": 0,
    "models": [],
    "description": (
        "Deterministic synthetic-event replay and learner-evidence KC selection "
        "over the already fixed, model-validated item bank; no LM is invoked."
    ),
}


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _stable_hash(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _artifact_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def _read_events(path: Path) -> tuple[list[dict[str, Any]], str]:
    """Read compressed JSONL and hash its uncompressed canonical bytes."""

    digest = hashlib.sha256()
    rows: list[dict[str, Any]] = []
    with gzip.open(path, "rb") as stream:
        for line in stream:
            if not line.strip():
                continue
            digest.update(line)
            rows.append(json.loads(line))
    return rows, digest.hexdigest()


def _write_events(
    path: Path, rows: Iterable[dict[str, Any]]
) -> tuple[str, str, int]:
    """Write deterministic gzip JSONL and return file/content hashes and count."""

    path.parent.mkdir(parents=True, exist_ok=True)
    content_digest = hashlib.sha256()
    count = 0
    with path.open("wb") as raw:
        with gzip.GzipFile(
            filename="", fileobj=raw, mode="wb", mtime=0
        ) as compressed:
            for row in rows:
                payload = (
                    json.dumps(
                        row,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    + "\n"
                ).encode("utf-8")
                compressed.write(payload)
                content_digest.update(payload)
                count += 1
    return _sha256(path), content_digest.hexdigest(), count


def _learner_number(learner_id: str) -> int:
    match = re.fullmatch(r"learner_(\d+)", learner_id)
    if match is None:
        raise ValueError(f"unexpected learner ID: {learner_id}")
    return int(match.group(1))


def selection_schedule(
    *,
    seeds: tuple[int, ...] = SEEDS,
    reference_seed: int = REFERENCE_SEED,
    nested_learners: tuple[int, ...] = NESTED_LEARNERS,
    full_learners: int = FULL_LEARNERS,
) -> list[dict[str, int | str]]:
    """Declare the staged nine-condition design without a Cartesian product."""

    if len(seeds) != len(set(seeds)) or reference_seed not in seeds:
        raise ValueError("seeds must be unique and contain the reference seed")
    if len(nested_learners) != len(set(nested_learners)):
        raise ValueError("nested learner supports must be unique")
    if tuple(sorted(nested_learners)) != nested_learners:
        raise ValueError("nested learner supports must be increasing")
    if not nested_learners or nested_learners[-1] != full_learners:
        raise ValueError("nested learner supports must end at full learner support")
    if nested_learners[0] < 2:
        raise ValueError("selection needs at least two learners")

    schedule = [
        {
            "condition_id": f"seed_{reference_seed}__learners_{learners:04d}",
            "seed": reference_seed,
            "learners": learners,
            "stage": "reference_seed_nested_support",
        }
        for learners in nested_learners
    ]
    schedule.extend(
        {
            "condition_id": f"seed_{seed}__learners_{full_learners:04d}",
            "seed": seed,
            "learners": full_learners,
            "stage": "full_support_seed_stability",
        }
        for seed in seeds
        if seed != reference_seed
    )
    if len({row["condition_id"] for row in schedule}) != len(schedule):
        raise AssertionError("selection schedule contains duplicate conditions")
    return schedule


def subset_selection_events(
    events: list[dict[str, Any]],
    candidate_inventory: dict[str, Any],
    learner_count: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Take the numeric learner prefix and only development train/validation rows."""

    if learner_count < 2:
        raise ValueError("selection needs at least two learners")
    learner_ids = sorted(
        {str(row["learner_id"]) for row in events}, key=_learner_number
    )
    if learner_count > len(learner_ids):
        raise ValueError(
            f"requested {learner_count} learners from {len(learner_ids)}"
        )
    included = set(learner_ids[:learner_count])
    development_item_ids = set(candidate_inventory["development_item_ids"])
    selected = [
        row
        for row in events
        if row["learner_id"] in included
        and row["item_id"] in development_item_ids
        and row["dataset_split"] in {"train", "validation"}
    ]
    observed_learners = {str(row["learner_id"]) for row in selected}
    if observed_learners != included:
        raise ValueError("one or more nested learners has no selection evidence")
    if any(row.get("grammar_split") != "development" for row in selected):
        raise AssertionError("KC selection subset leaked grammar holdout events")
    if any(row["dataset_split"] not in {"train", "validation"} for row in selected):
        raise AssertionError("KC selection subset leaked reserved test outcomes")
    return selected, {
        "learners": learner_count,
        "learner_ids": learner_ids[:learner_count],
        "events": len(selected),
        "dataset_split_counts": dict(
            sorted(Counter(row["dataset_split"] for row in selected).items())
        ),
        "grammar_split_counts": dict(
            sorted(Counter(row["grammar_split"] for row in selected).items())
        ),
        "holdout_events_supplied": 0,
        "reserved_test_events_supplied": 0,
    }


def _validate_final_artifacts(
    dataset_dir: Path,
) -> dict[str, Any]:
    """Load, cross-check, and hash the final artifacts without rebuilding them."""

    finalization_path = dataset_dir / "finalization_manifest.json"
    if not finalization_path.is_file():
        raise FileNotFoundError(
            f"missing finalized dataset manifest: {finalization_path}"
        )
    finalization = _read_json(finalization_path)
    if finalization.get("status") != "downstream_finalized":
        raise ValueError("selection stability requires a downstream-finalized dataset")

    paths = {
        "cells": dataset_dir / "canonical/cells.jsonl",
        "items": dataset_dir / "items/selected_bank.jsonl",
        "fold": dataset_dir / "fold/assignments.jsonl",
        "candidate_inventory": dataset_dir / "kc/candidate_inventory.json",
        "reference_events": dataset_dir / "simulation/events.jsonl.gz",
        "reference_policy": dataset_dir / "kc/policies/automated.yaml",
        "materialized_world": dataset_dir / "simulation/materialized_world.yaml",
        "finalization_manifest": finalization_path,
        "grammar_schema": SCHEMA_PATH,
        "world_design": WORLD_PATH,
        "simulation_protocol": PROTOCOL_PATH,
        "selection_design": SELECTION_PATH,
    }
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"missing selection-stability inputs: {missing}")

    cells = read_jsonl(paths["cells"])
    items = read_jsonl(paths["items"])
    fold = read_jsonl(paths["fold"])
    inventory = _read_json(paths["candidate_inventory"])
    schema = read_yaml(paths["grammar_schema"])
    world_design = read_yaml(paths["world_design"])
    protocol = read_yaml(paths["simulation_protocol"])
    selection_design = read_yaml(paths["selection_design"])
    reference_policy = read_yaml(paths["reference_policy"])

    if len(cells) != finalization["scale"]["cells"]:
        raise ValueError("canonical-cell artifact differs from finalization manifest")
    if len(items) != finalization["scale"]["selected_items"]:
        raise ValueError("selected-bank artifact differs from finalization manifest")
    cell_ids = {row["cell_id"] for row in cells}
    if {row["cell_id"] for row in fold} != cell_ids:
        raise ValueError("final fold does not assign every and only final GrammarCells")
    split_by_cell = {row["cell_id"]: row["grammar_split"] for row in fold}
    development_cell_ids = {
        cell_id for cell_id, split in split_by_cell.items() if split == "development"
    }
    development_item_ids = {
        row["item_id"]
        for row in items
        if split_by_cell[row["cell_id"]] == "development"
    }
    if set(inventory["development_cell_ids"]) != development_cell_ids:
        raise ValueError("candidate inventory does not match the retained final fold")
    if set(inventory["development_item_ids"]) != development_item_ids:
        raise ValueError("candidate inventory does not match final development items")
    if inventory["candidate_design_id"] != finalization["kc"]["candidate_design_id"]:
        raise ValueError("candidate design differs from finalization manifest")
    if world_design["world_id"] != finalization["simulation"]["world_id"]:
        raise ValueError("active mixed world differs from finalization manifest")
    if protocol["protocol_id"] != finalization["simulation"]["protocol_id"]:
        raise ValueError("simulation protocol differs from finalization manifest")
    if selection_design["selection_id"] != finalization["kc"]["selection_id"]:
        raise ValueError("selection design differs from finalization manifest")
    declared_reference_world = copy.deepcopy(world_design)
    declared_reference_world["seed"] = int(finalization["simulation"]["seed"])
    declared_reference_world["learners"] = int(finalization["scale"]["learners"])
    expected_materialized_world = materialize_latent_world(
        declared_reference_world, schema, cells
    )
    if read_yaml(paths["materialized_world"]) != expected_materialized_world:
        raise ValueError(
            "retained materialized world differs from the active mixed-world declaration"
        )

    hashes = {name: _sha256(path) for name, path in paths.items()}
    method_fingerprint = _stable_hash(
        {
            "artifact_hashes": hashes,
            "world_id": world_design["world_id"],
            "protocol_id": protocol["protocol_id"],
            "selection_id": selection_design["selection_id"],
        }
    )
    return {
        "paths": paths,
        "hashes": hashes,
        "method_fingerprint": method_fingerprint,
        "finalization": finalization,
        "cells": cells,
        "items": items,
        "fold": fold,
        "inventory": inventory,
        "schema": schema,
        "world_design": world_design,
        "protocol": protocol,
        "selection_design": selection_design,
        "reference_policy": reference_policy,
    }


def _validate_event_stream(
    events: list[dict[str, Any]],
    *,
    learners: int,
    items: list[dict[str, Any]],
    fold: list[dict[str, Any]],
    protocol: dict[str, Any],
) -> dict[str, Any]:
    item_ids = {row["item_id"] for row in items}
    split_by_cell = {row["cell_id"]: row["grammar_split"] for row in fold}
    split_by_item = {
        row["item_id"]: split_by_cell[row["cell_id"]] for row in items
    }
    development_items = {
        item_id for item_id, split in split_by_item.items() if split == "development"
    }
    expected_per_learner = (
        int(protocol["acquisition_passes"]) * len(development_items)
        + int(protocol["probe_repeats"]) * len(items)
    )
    expected_events = learners * expected_per_learner
    if len(events) != expected_events:
        raise ValueError(
            f"event stream has {len(events)} rows, expected {expected_events}"
        )
    event_ids = [str(row["event_id"]) for row in events]
    if len(event_ids) != len(set(event_ids)):
        raise ValueError("event stream contains duplicate event IDs")
    expected_learners = {f"learner_{number:03d}" for number in range(1, learners + 1)}
    observed_learners = {str(row["learner_id"]) for row in events}
    if observed_learners != expected_learners:
        raise ValueError(
            "event stream learner inventory is not the declared population"
        )
    learner_counts = Counter(str(row["learner_id"]) for row in events)
    if set(learner_counts.values()) != {expected_per_learner}:
        raise ValueError("event counts are not balanced across learners")

    for row in events:
        item_id = row["item_id"]
        if item_id not in item_ids:
            raise ValueError(f"event stream contains an unknown item: {item_id}")
        if row["grammar_split"] != split_by_item[item_id]:
            raise ValueError("event grammar split disagrees with retained final fold")
        if row["protocol_phase"] == "acquisition":
            if item_id not in development_items:
                raise ValueError("acquisition event contains holdout grammar")
            if row["dataset_split"] not in {"train", "validation"}:
                raise ValueError("acquisition event has a reserved dataset split")
            if not row["updates_mastery"] or not row["updates_history"]:
                raise ValueError("acquisition event does not update both states")
        elif row["protocol_phase"] == "probe":
            if row["dataset_split"] != "test":
                raise ValueError("probe event is not reserved for testing")
            if row["updates_mastery"] or row["updates_history"]:
                raise ValueError("frozen probe unexpectedly updates learner state")
        else:
            raise ValueError(f"unknown protocol phase: {row['protocol_phase']}")
        if row["correct"] not in {0, 1}:
            raise ValueError("event outcome is not binary")
    return {
        "events": len(events),
        "learners": learners,
        "events_per_learner": expected_per_learner,
        "phase_counts": dict(
            sorted(Counter(row["protocol_phase"] for row in events).items())
        ),
        "grammar_split_counts": dict(
            sorted(Counter(row["grammar_split"] for row in events).items())
        ),
        "dataset_split_counts": dict(
            sorted(Counter(row["dataset_split"] for row in events).items())
        ),
    }


def simulate_event_stream(
    *,
    cells: list[dict[str, Any]],
    items: list[dict[str, Any]],
    fold: list[dict[str, Any]],
    schema: dict[str, Any],
    world_design: dict[str, Any],
    protocol: dict[str, Any],
    seed: int,
    learners: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Materialize and simulate one exact mixed-world frozen-probe stream."""

    declared = copy.deepcopy(world_design)
    declared["seed"] = seed
    declared["learners"] = learners
    world = materialize_latent_world(declared, schema, cells)
    events = simulate_frozen_probes(items, fold, world, protocol)
    return events, world


def _event_manifest_matches(
    manifest: dict[str, Any], *, seed: int, learners: int, fingerprint: str
) -> bool:
    return (
        manifest.get("status") == "complete"
        and manifest.get("seed") == seed
        and manifest.get("learners") == learners
        and manifest.get("method_fingerprint") == fingerprint
    )


def _obtain_events(
    *,
    seed: int,
    learners: int,
    reference_seed: int,
    inputs: dict[str, Any],
    output: Path,
    recompute: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    event_path = output / "events" / f"seed_{seed}.jsonl.gz"
    manifest_path = output / "events" / f"seed_{seed}.manifest.json"
    fingerprint = inputs["method_fingerprint"]

    if event_path.is_file() and manifest_path.is_file() and not recompute:
        manifest = _read_json(manifest_path)
        if not _event_manifest_matches(
            manifest, seed=seed, learners=learners, fingerprint=fingerprint
        ):
            raise ValueError(
                f"retained seed {seed} event manifest differs from this study design; "
                "use --recompute"
            )
        if _sha256(event_path) != manifest["file_sha256"]:
            raise ValueError(f"retained seed {seed} event gzip hash changed")
        events, content_hash = _read_events(event_path)
        if content_hash != manifest["content_sha256"]:
            raise ValueError(f"retained seed {seed} event content hash changed")
        integrity = _validate_event_stream(
            events,
            learners=learners,
            items=inputs["items"],
            fold=inputs["fold"],
            protocol=inputs["protocol"],
        )
        if integrity != manifest["integrity"]:
            raise ValueError(f"retained seed {seed} event content summary changed")
        return events, manifest

    finalized_seed = int(inputs["finalization"]["simulation"]["seed"])
    finalized_learners = int(inputs["finalization"]["scale"]["learners"])
    source_path = inputs["paths"]["reference_events"]
    should_reuse_final = (
        not recompute
        and seed == reference_seed == finalized_seed
        and learners == finalized_learners
    )
    reference_content_hash = None
    if should_reuse_final:
        events, reference_content_hash = _read_events(source_path)
        _validate_event_stream(
            events,
            learners=learners,
            items=inputs["items"],
            fold=inputs["fold"],
            protocol=inputs["protocol"],
        )
        event_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, event_path)
        source = "finalized_reference_stream_verified_reuse"
        world = read_yaml(inputs["paths"]["materialized_world"])
    else:
        events, world = simulate_event_stream(
            cells=inputs["cells"],
            items=inputs["items"],
            fold=inputs["fold"],
            schema=inputs["schema"],
            world_design=inputs["world_design"],
            protocol=inputs["protocol"],
            seed=seed,
            learners=learners,
        )
        file_hash, content_hash, written = _write_events(event_path, events)
        if written != len(events):
            raise AssertionError("event writer changed the event count")
        source = "deterministic_mixed_world_simulation"
        if seed == reference_seed == finalized_seed and learners == finalized_learners:
            _source_events, reference_content_hash = _read_events(source_path)
            if content_hash != reference_content_hash:
                raise ValueError(
                    "recomputed reference stream differs from finalized dataset events"
                )

    integrity = _validate_event_stream(
        events,
        learners=learners,
        items=inputs["items"],
        fold=inputs["fold"],
        protocol=inputs["protocol"],
    )
    _events_check, content_hash = _read_events(event_path)
    manifest = {
        "status": "complete",
        "seed": seed,
        "learners": learners,
        "world_id": world["world_id"],
        "protocol_id": inputs["protocol"]["protocol_id"],
        "source": source,
        "event_file": f"events/{event_path.name}",
        "file_sha256": _sha256(event_path),
        "content_sha256": content_hash,
        "finalized_reference_content_sha256": reference_content_hash,
        "method_fingerprint": fingerprint,
        "integrity": integrity,
        "provenance": NO_MODEL_PROVENANCE,
    }
    write_json(manifest_path, manifest)
    return events, manifest


def _verify_policy(
    policy: dict[str, Any],
    *,
    inventory: dict[str, Any],
    selection_design: dict[str, Any],
    selection_events: list[dict[str, Any]],
) -> None:
    metadata = policy["selection_metadata"]
    if metadata["candidate_design_id"] != inventory["candidate_design_id"]:
        raise ValueError("policy candidate design differs from final inventory")
    if metadata["selection_id"] != selection_design["selection_id"]:
        raise ValueError("policy selection design differs from active selector")
    if metadata["development_cell_ids"] != inventory["development_cell_ids"]:
        raise ValueError("policy development cells differ from final inventory")
    if metadata["development_item_ids"] != inventory["development_item_ids"]:
        raise ValueError("policy development items differ from final inventory")
    if metadata["held_out_grammar_read"]:
        raise ValueError("policy reports reading held-out grammar")
    if metadata["reserved_or_holdout_outcomes_read"]:
        raise ValueError("policy reports reading reserved/holdout outcomes")
    selected_ids = set(metadata["selected_candidate_ids"])
    if selected_ids != {row["id"] for row in policy["kcs"]}:
        raise ValueError("policy KCs differ from selected candidate metadata")
    candidate_ids = {row["id"] for row in inventory["candidates"]}
    if not selected_ids <= candidate_ids:
        raise ValueError("policy contains candidates outside the final inventory")
    split_counts = Counter(row["dataset_split"] for row in selection_events)
    if metadata["split"]["train_events"] != split_counts["train"]:
        raise ValueError("policy train-event count differs from supplied evidence")
    if metadata["split"]["validation_events"] != split_counts["validation"]:
        raise ValueError("policy validation-event count differs from supplied evidence")


def _selection_record(
    policy: dict[str, Any],
    *,
    condition: dict[str, Any],
    evidence: dict[str, Any],
    event_manifest: dict[str, Any],
    policy_file: Path,
    source: str,
    reference_selected: set[str],
) -> dict[str, Any]:
    metadata = policy["selection_metadata"]
    selected = set(metadata["selected_candidate_ids"])
    initial = set(metadata["initial_candidate_ids"])
    additions = selected - initial
    return {
        **condition,
        "selection_source": source,
        "selection_events": evidence["events"],
        "selection_train_events": evidence["dataset_split_counts"].get("train", 0),
        "selection_validation_events": evidence["dataset_split_counts"].get(
            "validation", 0
        ),
        "holdout_events_supplied": evidence["holdout_events_supplied"],
        "reserved_test_events_supplied": evidence[
            "reserved_test_events_supplied"
        ],
        "selected_candidate_ids": sorted(selected),
        "initial_candidate_ids": sorted(initial),
        "selected_addition_ids": sorted(additions),
        "kc_count": len(selected),
        "addition_count": len(additions),
        "exact_selected_inventory_match_reference": selected == reference_selected,
        "event_file_sha256": event_manifest["file_sha256"],
        "event_content_sha256": event_manifest["content_sha256"],
        "policy_file": f"policies/{policy_file.name}",
        "policy_file_sha256": _sha256(policy_file),
        "final_validation_score": metadata["final_validation_score"],
    }


def _pairwise_jaccard(records: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for index, left in enumerate(records):
        left_all = set(left["selected_candidate_ids"])
        left_additions = set(left["selected_addition_ids"])
        for right in records[index + 1 :]:
            right_all = set(right["selected_candidate_ids"])
            right_additions = set(right["selected_addition_ids"])

            def jaccard(first: set[str], second: set[str]) -> float:
                union = first | second
                return len(first & second) / len(union) if union else 1.0

            rows.append(
                {
                    "left": left["condition_id"],
                    "right": right["condition_id"],
                    "all_selected_jaccard": jaccard(left_all, right_all),
                    "addition_jaccard": jaccard(left_additions, right_additions),
                    "exact_selected_inventory_match": left_all == right_all,
                    "exact_addition_inventory_match": left_additions
                    == right_additions,
                }
            )
    return {
        "pairs": rows,
        "all_selected": {
            "mean": mean(row["all_selected_jaccard"] for row in rows)
            if rows
            else None,
            "median": median(row["all_selected_jaccard"] for row in rows)
            if rows
            else None,
            "minimum": min(row["all_selected_jaccard"] for row in rows)
            if rows
            else None,
        },
        "additions": {
            "mean": mean(row["addition_jaccard"] for row in rows)
            if rows
            else None,
            "median": median(row["addition_jaccard"] for row in rows)
            if rows
            else None,
            "minimum": min(row["addition_jaccard"] for row in rows)
            if rows
            else None,
        },
    }


def _frequencies(records: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter(
        candidate_id for row in records for candidate_id in row[field]
    )
    return [
        {
            "candidate_id": candidate_id,
            "selected_conditions": count,
            "selection_frequency": count / len(records),
            "condition_ids": [
                row["condition_id"]
                for row in records
                if candidate_id in set(row[field])
            ],
        }
        for candidate_id, count in sorted(counts.items())
    ]


def run_stability(
    dataset_dir: Path = DEFAULT_DATASET,
    output: Path = DEFAULT_OUTPUT,
    *,
    seeds: tuple[int, ...] = SEEDS,
    reference_seed: int = REFERENCE_SEED,
    full_learners: int = FULL_LEARNERS,
    nested_learners: tuple[int, ...] = NESTED_LEARNERS,
    recompute: bool = False,
    exact_command: str = "direct Python call",
) -> dict[str, Any]:
    """Execute or safely resume the staged selection-stability experiment."""

    dataset_dir = dataset_dir.resolve()
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    inputs = _validate_final_artifacts(dataset_dir)
    schedule = selection_schedule(
        seeds=seeds,
        reference_seed=reference_seed,
        nested_learners=nested_learners,
        full_learners=full_learners,
    )
    conditions_by_seed: dict[int, list[dict[str, Any]]] = {}
    for condition in schedule:
        conditions_by_seed.setdefault(int(condition["seed"]), []).append(condition)

    study_design = {
        "experiment_id": "phase6_selection_stability_v1",
        "design": {
            "reference_seed": reference_seed,
            "simulation_seeds": list(seeds),
            "full_support_learners": full_learners,
            "reference_nested_learners": list(nested_learners),
            "selection_conditions": schedule,
            "selection_count": len(schedule),
            "design_type": (
                "nested_reference_support_plus_full_support_seed_stability; "
                "not_a_Cartesian_product"
            ),
        },
        "fixed_artifacts": {
            name: {
                "path": _artifact_path(inputs["paths"][name]),
                "sha256": inputs["hashes"][name],
            }
            for name in (
                "cells",
                "items",
                "fold",
                "candidate_inventory",
                "grammar_schema",
                "world_design",
                "simulation_protocol",
                "selection_design",
            )
        },
        "method_fingerprint": inputs["method_fingerprint"],
        "selection_boundary": (
            "Only development acquisition events labelled train/validation enter "
            "select_kcs; frozen probes and all grammar holdouts are excluded."
        ),
        "provenance": NO_MODEL_PROVENANCE,
        "exact_command": exact_command,
    }
    write_json(output / "study_design.json", study_design)

    reference_policy = inputs["reference_policy"]
    reference_selected = set(
        reference_policy["selection_metadata"]["selected_candidate_ids"]
    )
    records: list[dict[str, Any]] = []
    event_manifests: list[dict[str, Any]] = []
    for seed in seeds:
        events, event_manifest = _obtain_events(
            seed=seed,
            learners=full_learners,
            reference_seed=reference_seed,
            inputs=inputs,
            output=output,
            recompute=recompute,
        )
        event_manifests.append(event_manifest)
        for condition in conditions_by_seed[seed]:
            learner_count = int(condition["learners"])
            selection_events, evidence = subset_selection_events(
                events, inputs["inventory"], learner_count
            )
            condition_id = str(condition["condition_id"])
            policy_file = output / "policies" / f"{condition_id}.yaml"
            selection_file = output / "selections" / f"{condition_id}.json"
            retained = None
            if policy_file.is_file() and selection_file.is_file() and not recompute:
                selection_manifest = _read_json(selection_file)
                if (
                    selection_manifest.get("method_fingerprint")
                    == inputs["method_fingerprint"]
                    and selection_manifest.get("event_content_sha256")
                    == event_manifest["content_sha256"]
                    and selection_manifest.get("learner_count") == learner_count
                    and _sha256(policy_file)
                    == selection_manifest.get("policy_file_sha256")
                ):
                    retained = read_yaml(policy_file)
            if retained is not None:
                policy = retained
                selection_source = "verified_retained_stability_policy"
            elif (
                not recompute
                and seed == reference_seed
                and learner_count == full_learners
                and int(inputs["finalization"]["simulation"]["seed"])
                == reference_seed
                and int(inputs["finalization"]["scale"]["learners"])
                == full_learners
            ):
                policy = copy.deepcopy(reference_policy)
                selection_source = "verified_finalized_reference_policy_reuse"
            else:
                policy = select_kcs(
                    inputs["inventory"],
                    selection_events,
                    inputs["selection_design"],
                )
                selection_source = "deterministic_active_selector"
            _verify_policy(
                policy,
                inventory=inputs["inventory"],
                selection_design=inputs["selection_design"],
                selection_events=selection_events,
            )
            selected_ids = set(
                policy["selection_metadata"]["selected_candidate_ids"]
            )
            exact_reference_match = selected_ids == reference_selected
            if (
                seed == reference_seed
                and learner_count == full_learners
                and not exact_reference_match
            ):
                raise ValueError(
                    "reference/full-support selection differs from finalized policy"
                )
            write_yaml(policy_file, policy)
            selection_manifest = {
                "status": "complete",
                "condition_id": condition_id,
                "simulation_seed": seed,
                "learner_count": learner_count,
                "selection_source": selection_source,
                "method_fingerprint": inputs["method_fingerprint"],
                "event_content_sha256": event_manifest["content_sha256"],
                "selection_events": evidence["events"],
                "holdout_events_supplied": evidence["holdout_events_supplied"],
                "reserved_test_events_supplied": evidence[
                    "reserved_test_events_supplied"
                ],
                "selected_candidate_ids": sorted(selected_ids),
                "selected_addition_ids": sorted(
                    selected_ids
                    - set(policy["selection_metadata"]["initial_candidate_ids"])
                ),
                "exact_selected_inventory_match_finalized_reference": (
                    exact_reference_match
                ),
                "policy_file": f"policies/{policy_file.name}",
                "policy_file_sha256": _sha256(policy_file),
                "provenance": NO_MODEL_PROVENANCE,
            }
            write_json(selection_file, selection_manifest)
            records.append(
                _selection_record(
                    policy,
                    condition=condition,
                    evidence=evidence,
                    event_manifest=event_manifest,
                    policy_file=policy_file,
                    source=selection_source,
                    reference_selected=reference_selected,
                )
            )
        del events

    nested_records = [row for row in records if row["seed"] == reference_seed]
    seed_records = [row for row in records if row["learners"] == full_learners]
    results = {
        "experiment_id": "phase6_selection_stability_v1",
        "status": "complete",
        "scale": {
            "cells": len(inputs["cells"]),
            "items": len(inputs["items"]),
            "candidate_counts": inputs["inventory"]["candidate_counts"],
            "simulation_seeds": len(seeds),
            "full_support_learners": full_learners,
            "selection_conditions": len(records),
        },
        "fixed_artifact_integrity": {
            "candidate_inventory_and_fold_read_from_final_dataset": True,
            "method_fingerprint": inputs["method_fingerprint"],
            "finalized_reference_selected_candidate_ids": sorted(reference_selected),
        },
        "event_streams": event_manifests,
        "selections": records,
        "frequencies": {
            "all_conditions": {
                "selected": _frequencies(records, "selected_candidate_ids"),
                "additions": _frequencies(records, "selected_addition_ids"),
            },
            "reference_nested_support": {
                "selected": _frequencies(nested_records, "selected_candidate_ids"),
                "additions": _frequencies(nested_records, "selected_addition_ids"),
            },
            "five_seed_full_support": {
                "selected": _frequencies(seed_records, "selected_candidate_ids"),
                "additions": _frequencies(seed_records, "selected_addition_ids"),
            },
        },
        "jaccard": {
            "all_conditions": _pairwise_jaccard(records),
            "reference_nested_support": _pairwise_jaccard(nested_records),
            "five_seed_full_support": _pairwise_jaccard(seed_records),
        },
        "exact_inventory_matches": {
            "reference_condition_id": (
                f"seed_{reference_seed}__learners_{full_learners:04d}"
            ),
            "conditions_matching_finalized_reference": sum(
                row["exact_selected_inventory_match_reference"] for row in records
            ),
            "full_support_seeds_matching_finalized_reference": sum(
                row["exact_selected_inventory_match_reference"]
                for row in seed_records
            ),
            "all_conditions_identical": len(
                {tuple(row["selected_candidate_ids"]) for row in records}
            )
            == 1,
            "all_full_support_seeds_identical": len(
                {tuple(row["selected_candidate_ids"]) for row in seed_records}
            )
            == 1,
        },
        "boundary_checks": {
            "holdout_events_supplied_to_any_selection": sum(
                row["holdout_events_supplied"] for row in records
            ),
            "reserved_test_events_supplied_to_any_selection": sum(
                row["reserved_test_events_supplied"] for row in records
            ),
        },
        "provenance": NO_MODEL_PROVENANCE,
        "exact_command": exact_command,
    }
    write_json(output / "results.json", results)
    # Keep the compact stability result with the finalized dataset as well as the
    # full inspectable study directory.  Downstream paper-table generation reads
    # this dataset-local copy and never needs to infer a reports/ path.
    write_json(dataset_dir / "kc/selection_stability.json", results)
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--learners", type=int, default=FULL_LEARNERS)
    parser.add_argument("--reference-seed", type=int, default=REFERENCE_SEED)
    parser.add_argument("--seeds", type=int, nargs="+", default=list(SEEDS))
    parser.add_argument(
        "--nested-learners", type=int, nargs="+", default=list(NESTED_LEARNERS)
    )
    parser.add_argument(
        "--recompute",
        action="store_true",
        help="regenerate streams and policies, verifying the finalized reference",
    )
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    results = run_stability(
        arguments.dataset_dir,
        arguments.output_dir,
        seeds=tuple(arguments.seeds),
        reference_seed=arguments.reference_seed,
        full_learners=arguments.learners,
        nested_learners=tuple(arguments.nested_learners),
        recompute=arguments.recompute,
        exact_command=" ".join([sys.executable, *sys.argv]),
    )
    print(json.dumps(results["scale"], ensure_ascii=False, indent=2))
    print(arguments.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
