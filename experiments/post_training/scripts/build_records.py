#!/usr/bin/env python3
"""Build transparent post-training views from existing deterministic artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from grammar_kt import qmatrix, simulation
from grammar_kt.folds import annotate_items, assignment_for_cells, load_fold
from grammar_kt.io import ROOT, read_json, read_jsonl, stable_id, write_json, write_jsonl
from grammar_kt.item_validation import deterministic_results
from grammar_kt.items import (
    build_item_opportunities,
    construct_items,
    nuisance_signature,
)
from grammar_kt.kc import load_policy, project_items


SCRIPT_VERSION = "POST_TRAINING_RECORD_BUILDER_v0"
DIMENSION_ORDER = ("tense", "aspect", "voice", "polarity", "clause", "modal")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


def git_state() -> dict[str, Any]:
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
        dirty = bool(
            subprocess.check_output(
                ["git", "status", "--porcelain"], cwd=ROOT, text=True
            )
        )
        return {"commit": commit, "dirty": dirty}
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "dirty": None}


def provenance(
    item: dict[str, Any],
    *,
    target_kcs: list[str],
    policy_id: str,
    source_run: str,
) -> dict[str, Any]:
    return {
        "source_run": source_run,
        "source_descriptor_ids": item["source_descriptor_ids"],
        "canonical_cell_id": item["canonical_cell_id"],
        "realization_id": item["realization_spec"]["realization_id"],
        "item_opportunity_id": item["item_opportunity_id"],
        "item_id": item["item_id"],
        "kc_policy_id": policy_id,
        "target_kc_ids": target_kcs,
        "builder_version": SCRIPT_VERSION,
    }


def data_split_for(*splits: str) -> str:
    if "novel_feature_holdout" in splits:
        return "evaluation_novel_feature"
    if "compositional_holdout" in splits:
        return "evaluation_compositional"
    return "train_development"


def common_record(
    record_type: str,
    task: str,
    item: dict[str, Any],
    *,
    target_kcs: list[str],
    policy_id: str,
    source_run: str,
    identity_parts: tuple[object, ...],
    split: str | None = None,
) -> dict[str, Any]:
    return {
        "record_id": stable_id("PT", record_type, task, *identity_parts),
        "record_type": record_type,
        "task": task,
        "data_split": split or data_split_for(item["canonical_split"]),
        "interaction_format": "controlled_transformation",
        "provenance": provenance(
            item,
            target_kcs=target_kcs,
            policy_id=policy_id,
            source_run=source_run,
        ),
    }


def build_preferences(
    items: list[dict[str, Any]],
    cells_by_id: dict[str, dict[str, str]],
    kc_by_item: dict[str, list[str]],
    *,
    policy_id: str,
    source_run: str,
) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        groups[nuisance_signature(item["realization_spec"])].append(item)

    records: list[dict[str, Any]] = []
    for group_index, signature in enumerate(sorted(groups, key=repr), 1):
        rows = sorted(groups[signature], key=lambda row: row["item_id"])
        for chosen in rows:
            chosen_cell = cells_by_id[chosen["canonical_cell_id"]]
            for rejected in rows:
                if chosen["item_id"] == rejected["item_id"]:
                    continue
                rejected_cell = cells_by_id[rejected["canonical_cell_id"]]
                differing = [
                    key for key in DIMENSION_ORDER if chosen_cell[key] != rejected_cell[key]
                ]
                if len(differing) != 1:
                    continue
                dimension = differing[0]
                chosen_kcs = kc_by_item[chosen["item_id"]]
                rejected_kcs = kc_by_item[rejected["item_id"]]
                record = common_record(
                    "preference",
                    "grammar_controlled_generation",
                    chosen,
                    target_kcs=chosen_kcs,
                    policy_id=policy_id,
                    source_run=source_run,
                    identity_parts=(chosen["item_id"], rejected["item_id"], dimension),
                    split=data_split_for(
                        chosen["canonical_split"], rejected["canonical_split"]
                    ),
                )
                record.update(
                    {
                        "context": {
                            "instruction": "Produce exactly one sentence satisfying the target grammar and fixed realization constraints.",
                            "canonical_structure": chosen_cell,
                            "target_kcs": chosen_kcs,
                            "exercise_prompt": chosen["prompt"],
                        },
                        "chosen": chosen["target_answer"],
                        "rejected": rejected["target_answer"],
                        "preference_label": {
                            "relation": "chosen_over_rejected",
                            "distinction": f"canonical_dimension:{dimension}",
                            "differing_dimension": dimension,
                            "target_value": chosen_cell[dimension],
                            "rejected_value": rejected_cell[dimension],
                            "chosen_exact_target": True,
                            "rejected_exact_target": False,
                            "rejected_is_valid_for_alternative_cell": True,
                            "same_realization_nuisance_signature": True,
                            "hamming_distance": 1,
                            "missing_target_kcs": sorted(set(chosen_kcs) - set(rejected_kcs)),
                            "extraneous_kcs": sorted(set(rejected_kcs) - set(chosen_kcs)),
                        },
                        "hidden_generation_metadata": {
                            "rejected_item_id": rejected["item_id"],
                            "rejected_canonical_cell_id": rejected["canonical_cell_id"],
                            "nuisance_group_id": f"NUISANCE_{group_index:03d}",
                        },
                    }
                )
                records.append(record)
    return sorted(records, key=lambda row: row["record_id"])


def build_sft_records(
    items: list[dict[str, Any]],
    preferences: list[dict[str, Any]],
    cells_by_id: dict[str, dict[str, str]],
    kc_by_item: dict[str, list[str]],
    *,
    policy_id: str,
    source_run: str,
) -> list[dict[str, Any]]:
    by_item = {item["item_id"]: item for item in items}
    records: list[dict[str, Any]] = []
    for item in items:
        cell = cells_by_id[item["canonical_cell_id"]]
        target_kcs = kc_by_item[item["item_id"]]
        base = common_record(
            "sft",
            "grammar_controlled_generation",
            item,
            target_kcs=target_kcs,
            policy_id=policy_id,
            source_run=source_run,
            identity_parts=(item["item_id"], "generation"),
        )
        records.append(
            {
                **base,
                "model_input": {
                    "instruction": "Generate one sentence for this canonical grammar opportunity.",
                    "canonical_structure": cell,
                    "realization_spec": item["realization_spec"],
                    "target_kcs": target_kcs,
                },
                "response": item["target_answer"],
                "labels": {"exact_realization": item["target_answer"]},
                "evaluation_only": {"exercise_prompt": item["prompt"]},
            }
        )
        solve = common_record(
            "sft",
            "exercise_solving",
            item,
            target_kcs=target_kcs,
            policy_id=policy_id,
            source_run=source_run,
            identity_parts=(item["item_id"], "solve"),
        )
        records.append(
            {
                **solve,
                "model_input": {"exercise": item["prompt"]},
                "response": item["target_answer"],
                "labels": {"accepted_answers": item["accepted_answers"]},
                "evaluation_only": {
                    "canonical_structure": cell,
                    "target_kcs": target_kcs,
                },
            }
        )

    for preference in preferences:
        item = by_item[preference["provenance"]["item_id"]]
        target_kcs = kc_by_item[item["item_id"]]
        learner_response = preference["rejected"]
        distinction = preference["preference_label"]
        pair_split = preference["data_split"]
        diagnosis = common_record(
            "sft",
            "error_diagnosis",
            item,
            target_kcs=target_kcs,
            policy_id=policy_id,
            source_run=source_run,
            identity_parts=(preference["record_id"], "diagnosis"),
            split=pair_split,
        )
        records.append(
            {
                **diagnosis,
                "model_input": {
                    "exercise": item["prompt"],
                    "learner_response": learner_response,
                },
                "response": {
                    "correct": False,
                    "error_dimension": distinction["differing_dimension"],
                    "target_kcs": target_kcs,
                    "missing_target_kcs": distinction["missing_target_kcs"],
                    "extraneous_kcs": distinction["extraneous_kcs"],
                },
                "labels": {
                    "label_source": "deterministic_hamming_one_contrast",
                    "gold_answer_hidden_from_model": True,
                },
                "evaluation_only": {"gold_answer": preference["chosen"]},
            }
        )
        correction = common_record(
            "sft",
            "error_correction",
            item,
            target_kcs=target_kcs,
            policy_id=policy_id,
            source_run=source_run,
            identity_parts=(preference["record_id"], "correction"),
            split=pair_split,
        )
        records.append(
            {
                **correction,
                "model_input": {
                    "exercise": item["prompt"],
                    "learner_response": learner_response,
                    "instruction": "Return the corrected sentence only.",
                },
                "response": preference["chosen"],
                "labels": {
                    "error_dimension": distinction["differing_dimension"],
                    "accepted_answers": item["accepted_answers"],
                },
            }
        )
        for candidate_role, candidate, correct in (
            ("chosen", preference["chosen"], True),
            ("rejected", preference["rejected"], False),
        ):
            judgement = common_record(
                "sft",
                "grammar_judgement",
                item,
                target_kcs=target_kcs,
                policy_id=policy_id,
                source_run=source_run,
                identity_parts=(preference["record_id"], "judgement", candidate_role),
                split=pair_split,
            )
            records.append(
                {
                    **judgement,
                    "model_input": {
                        "canonical_structure": cells_by_id[item["canonical_cell_id"]],
                        "realization_spec": item["realization_spec"],
                        "candidate": candidate,
                    },
                    "response": {
                        "realizes_requested_structure": correct,
                        "error_dimension": None
                        if correct
                        else distinction["differing_dimension"],
                    },
                    "labels": {"candidate_role": candidate_role},
                }
            )
    return sorted(records, key=lambda row: row["record_id"])


def build_verifier_records(
    preferences: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    records = []
    for preference in preferences:
        for role, candidate, exact in (
            ("chosen", preference["chosen"], True),
            ("rejected", preference["rejected"], False),
        ):
            records.append(
                {
                    "record_id": stable_id(
                        "PT", "verifier", preference["record_id"], role
                    ),
                    "record_type": "verifier",
                    "task": "grammar_controlled_generation",
                    "data_split": preference["data_split"],
                    "context": preference["context"],
                    "candidate": candidate,
                    "reward_dimensions": {
                        "exact_requested_realization": int(exact),
                        "target_kc_alignment": int(exact),
                        "grammatical_under_some_controlled_cell": 1,
                        "pedagogical_quality": None,
                        "difficulty_appropriateness": None,
                    },
                    "rubric_sources": {
                        "exact_requested_realization": "deterministic_realizer",
                        "target_kc_alignment": "deterministic_KC_projection",
                        "grammatical_under_some_controlled_cell": "alternative deterministic realizer",
                        "pedagogical_quality": "requires human or validated model judge",
                        "difficulty_appropriateness": "not identified by current artifacts",
                    },
                    "labels": {
                        "candidate_role": role,
                        "differing_dimension": preference["preference_label"][
                            "differing_dimension"
                        ],
                    },
                    "provenance": preference["provenance"],
                }
            )
    return sorted(records, key=lambda row: row["record_id"])


def build_dialogues(
    preferences: list[dict[str, Any]],
    items_by_id: dict[str, dict[str, Any]],
    *,
    per_dimension: int,
) -> list[dict[str, Any]]:
    hints = {
        "tense": "Check which finite time form the exercise requests, then try again without changing the supplied words.",
        "aspect": "Check the requested auxiliary chain and verb form, then try the sentence again.",
        "voice": "Check which participant should be the grammatical subject and which verb form the voice requires.",
        "polarity": "Check whether the requested sentence is affirmative or negative and where the marker belongs.",
        "clause": "Check the requested clause type and the position of the finite operator, then try again.",
        "modal": "Check the requested modal and the form of the verb that follows it.",
    }
    chosen: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for preference in preferences:
        dimension = preference["preference_label"]["differing_dimension"]
        if counts[dimension] >= per_dimension:
            continue
        item = items_by_id[preference["provenance"]["item_id"]]
        chosen.append(
            {
                "record_id": stable_id("PT", "dialogue", preference["record_id"]),
                "record_type": "dialogue",
                "task": "corrective_feedback",
                "data_split": preference["data_split"],
                "model_input": {
                    "system": "You are tutoring an English learner. Give a targeted hint without revealing the answer.",
                    "exercise": item["prompt"],
                    "learner_response": preference["rejected"],
                    "learner_state": None,
                },
                "response": hints[dimension],
                "labels": {
                    "actual_error_dimension": dimension,
                    "reveals_answer": False,
                    "feedback_target_match": True,
                    "label_strength": "weak_template_demonstration",
                    "pedagogical_quality_validated": False,
                },
                "evaluation_only": {"gold_answer": preference["chosen"]},
                "provenance": preference["provenance"],
            }
        )
        counts[dimension] += 1
    return chosen


def build_trajectories(
    items: list[dict[str, Any]],
    cells: list[dict[str, Any]],
    kc_by_item: dict[str, list[str]],
    *,
    params_path: Path,
    seed: int,
    maximum: int,
    policy_id: str,
    source_run: str,
) -> list[dict[str, Any]]:
    params = simulation.load_simulation_parameters(params_path)
    params["seed"] = seed
    projections, feature_ids = simulation.project_oracle_items(items, cells, params)
    oracle_by_item = {row["item_id"]: row["oracle_feature_ids"] for row in projections}
    event_total = len(items) * int(params["item_passes_per_learner"])
    train_end, validation_end = simulation.split_boundaries(
        event_total,
        float(params["train_fraction"]),
        float(params["validation_fraction"]),
    )
    observed, oracle, _learners, _private = simulation.simulate_records(
        params,
        {row["item_id"]: row for row in items},
        oracle_by_item,
        feature_ids,
        train_end,
        validation_end,
        target_learner="L0001",
    )
    oracle_by_event = {row["event_id"]: row for row in oracle}
    items_by_id = {row["item_id"]: row for row in items}
    attempts: Counter[str] = Counter()
    successes: Counter[str] = Counter()
    records: list[dict[str, Any]] = []
    for event in observed[:maximum]:
        item = items_by_id[event["item_id"]]
        active = kc_by_item[item["item_id"]]
        pre_state = {
            kc_id: (successes[kc_id] + 1.0) / (attempts[kc_id] + 2.0)
            for kc_id in sorted(set(kc_by_item_value for values in kc_by_item.values() for kc_by_item_value in values))
        }
        for kc_id in active:
            attempts[kc_id] += 1
            successes[kc_id] += event["correct"]
        post_state = {
            kc_id: (successes[kc_id] + 1.0) / (attempts[kc_id] + 2.0)
            for kc_id in pre_state
        }
        record = common_record(
            "trajectory",
            "observed_tutoring_transition",
            item,
            target_kcs=active,
            policy_id=policy_id,
            source_run=source_run,
            identity_parts=(event["event_id"],),
        )
        record.update(
            {
                "learner_state_t": {
                    "estimator": "Beta(1,1)-smoothed observable KC success rate",
                    "kc_mastery_proxy": pre_state,
                    "history_length": event["sequence_index"] - 1,
                },
                "teaching_action_t": {
                    "action_type": "present_existing_item",
                    "item_id": item["item_id"],
                    "target_kcs": active,
                    "item_format": item["item_family"],
                    "selection_policy": "simulator shuffled pass; not an expert action",
                },
                "learner_response_t": {"correct": event["correct"]},
                "learner_state_t_plus_1": {
                    "estimator": "Beta(1,1)-smoothed observable KC success rate",
                    "kc_mastery_proxy": post_state,
                    "history_length": event["sequence_index"],
                },
                "evaluation_only": {
                    "oracle_feature_ids": oracle_by_event[event["event_id"]][
                        "oracle_feature_ids"
                    ],
                    "oracle_pre_mastery": oracle_by_event[event["event_id"]][
                        "pre_mastery"
                    ],
                    "action_optimality_label_available": False,
                },
            }
        )
        records.append(record)
    return records


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "experiments/post_training/configs/feasibility_v0.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "experiments/post_training/data/feasibility_v0",
    )
    args = parser.parse_args()
    config = read_json(args.config)
    output = args.output
    output.mkdir(parents=True, exist_ok=True)

    cells_path = ROOT / config["canonical_cells"]
    cells = read_jsonl(cells_path)
    cells_by_id = {row["canonical_cell_id"]: row["cell"] for row in cells}
    frames = {
        row["predicate_frame_id"]: row
        for row in read_jsonl(ROOT / config["lexicon"])
    }
    opportunities = build_item_opportunities(
        cells,
        frames,
        read_json(ROOT / config["item_bank_config"]),
    )
    template = (ROOT / config["item_template"]).read_text(encoding="utf-8")
    intrinsic_items = construct_items(opportunities, frames, template)

    hard = deterministic_results(
        intrinsic_items,
        cells=cells_by_id,
        edge_sources={
            row["canonical_cell_id"]: set(row["source_descriptor_ids"])
            for row in cells
        },
        mappings={
            source_id: {"egp_id": source_id, "note": row["source_mapping_notes"][source_id]}
            for row in cells
            for source_id in row["source_descriptor_ids"]
        },
        frames=frames,
        template=template,
    )
    failures = [row for row in hard if row["status"] != "accepted"]
    if failures:
        raise RuntimeError(f"current deterministic item checks failed: {failures[:3]}")

    fold = load_fold(ROOT / config["fold_manifest"])
    items = annotate_items(intrinsic_items, assignment_for_cells(cells, fold))
    policy = load_policy(ROOT / config["kc_policy"])
    item_projection, kc_cards = project_items(items, cells, policy)
    kc_by_item = {row["item_id"]: row["kc_ids"] for row in item_projection}
    _kc_ids, _q_rows, q_edges, q_audit = qmatrix.build(
        items, kc_cards, item_projection
    )
    if q_audit["status"] != "PASS":
        raise RuntimeError(q_audit["structural_errors"])

    preferences = build_preferences(
        items,
        cells_by_id,
        kc_by_item,
        policy_id=policy["policy_id"],
        source_run=config["source_run"],
    )
    sft = build_sft_records(
        items,
        preferences,
        cells_by_id,
        kc_by_item,
        policy_id=policy["policy_id"],
        source_run=config["source_run"],
    )
    verifier = build_verifier_records(preferences)
    dialogue = build_dialogues(
        preferences,
        {row["item_id"]: row for row in items},
        per_dimension=int(config["dialogue_records_per_error_dimension"]),
    )
    trajectories = build_trajectories(
        items,
        cells,
        kc_by_item,
        params_path=ROOT / config["simulation_parameters"],
        seed=int(config["seed"]),
        maximum=int(config["trajectory_records"]),
        policy_id=policy["policy_id"],
        source_run=config["source_run"],
    )

    write_jsonl(output / "items.jsonl", items)
    write_jsonl(output / "item_kc_projection.jsonl", item_projection)
    write_jsonl(output / "kc_inventory.jsonl", kc_cards)
    write_jsonl(output / "qmatrix_edges.jsonl", q_edges)
    write_jsonl(output / "sft.jsonl", sft)
    write_jsonl(output / "preference.jsonl", preferences)
    write_jsonl(output / "verifier.jsonl", verifier)
    write_jsonl(output / "dialogue.jsonl", dialogue)
    write_jsonl(output / "trajectory.jsonl", trajectories)

    artifacts = [
        "items.jsonl",
        "item_kc_projection.jsonl",
        "kc_inventory.jsonl",
        "qmatrix_edges.jsonl",
        "sft.jsonl",
        "preference.jsonl",
        "verifier.jsonl",
        "dialogue.jsonl",
        "trajectory.jsonl",
    ]
    manifest = {
        "experiment_id": config["experiment_id"],
        "builder_version": SCRIPT_VERSION,
        "git": git_state(),
        "implementation": {
            "config": {
                "path": display_path(args.config),
                "sha256": sha256(args.config),
            },
            "builder": {
                "path": display_path(Path(__file__)),
                "sha256": sha256(Path(__file__).resolve()),
            },
        },
        "inputs": {
            key: {"path": config[key], "sha256": sha256(ROOT / config[key])}
            for key in (
                "canonical_cells",
                "fold_manifest",
                "kc_policy",
                "item_bank_config",
                "item_template",
                "lexicon",
                "simulation_parameters",
            )
        },
        "seed": config["seed"],
        "counts": {
            "canonical_cells": len(cells),
            "items": len(items),
            "kcs": len(kc_cards),
            "qmatrix_edges": len(q_edges),
            "sft": len(sft),
            "preference": len(preferences),
            "verifier": len(verifier),
            "dialogue": len(dialogue),
            "trajectory": len(trajectories),
        },
        "artifact_sha256": {name: sha256(output / name) for name in artifacts},
        "qmatrix_audit": q_audit,
        "claim_boundary": config["claim_boundary"],
        "exact_command": ".venv/bin/python experiments/post_training/scripts/build_records.py",
    }
    write_json(output / "manifest.json", manifest)
    print(json.dumps(manifest["counts"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
