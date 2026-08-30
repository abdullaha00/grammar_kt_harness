#!/usr/bin/env python3
"""Replay and package the matched-bank v0 negative result.

This analyzer is deliberately downstream of the frozen run.  It never edits
raw model evidence, curation decisions, or full-v1.  It reports separate gate
and rubric dimensions; it does not construct a realism score.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "experiments/measurement_realism/design/bank_protocol/runs"
DEFAULT_RUN = RUNS / "matched_bank_v0_2_20260830"
DEFAULT_PROVIDER_PREFLIGHT = RUNS / "matched_bank_v0_20260830"
DEFAULT_RECONSTRUCTION_PREFLIGHT = RUNS / "matched_bank_v0_1_20260830"
FORMATS = (
    "constrained_cloze",
    "dialogue_completion",
    "multiple_choice",
    "sentence_transformation",
)
ROLES = ("linguistic", "measurement", "platform_product")
MUST_PASS = {
    "linguistic": {
        "grammar_cell_fidelity",
        "target_grammaticality",
        "accepted_response_linguistic_equivalence",
        "shared_target_proposition",
        "target_construction_consistency",
    },
    "measurement": {
        "active_kc_evidence",
        "no_target_avoiding_shortcut",
        "answer_determinacy",
        "accepted_response_coverage",
        "construct_equivalence_across_formats",
        "no_format_specific_kc_redefinition",
    },
    "platform_product": {
        "task_comprehensibility",
        "ui_response_mechanism_coherence",
        "platform_deployability",
        "plausible_format_crossing",
    },
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def file_record(path: Path, base: Path = ROOT) -> dict[str, Any]:
    return {
        "path": path.relative_to(base).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_path(path),
    }


def tree_record(path: Path, base: Path = ROOT) -> dict[str, Any]:
    files = sorted(row for row in path.rglob("*") if row.is_file())
    digest = hashlib.sha256()
    total = 0
    for row in files:
        relative = row.relative_to(path).as_posix()
        size = row.stat().st_size
        value = sha256_path(row)
        digest.update(relative.encode("utf-8") + b"\0")
        digest.update(str(size).encode("ascii") + b"\0")
        digest.update(value.encode("ascii") + b"\n")
        total += size
    return {
        "path": path.relative_to(base).as_posix(),
        "files": len(files),
        "bytes": total,
        "tree_sha256": digest.hexdigest(),
    }


def exact_rank(rows: Sequence[Sequence[int]]) -> int:
    """Exact Gaussian rank over rationals for the small binary Q matrices."""

    from fractions import Fraction

    matrix = [[Fraction(value) for value in row] for row in rows]
    if not matrix:
        return 0
    rank = 0
    columns = len(matrix[0])
    for column in range(columns):
        pivot = next(
            (index for index in range(rank, len(matrix)) if matrix[index][column]),
            None,
        )
        if pivot is None:
            continue
        matrix[rank], matrix[pivot] = matrix[pivot], matrix[rank]
        divisor = matrix[rank][column]
        matrix[rank] = [value / divisor for value in matrix[rank]]
        for index in range(len(matrix)):
            if index == rank or not matrix[index][column]:
                continue
            factor = matrix[index][column]
            matrix[index] = [
                left - factor * right
                for left, right in zip(matrix[index], matrix[rank])
            ]
        rank += 1
        if rank == len(matrix):
            break
    return rank


def _cell_catalog(selected: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        row["cell_id"]: dict(row)
        for row in [*selected["seen_cells"], *selected["held_out_cells"]]
    }


def _family_cell(family_id: str, cells: Mapping[str, Any]) -> str:
    matches = [cell_id for cell_id in cells if cell_id in family_id]
    if len(matches) != 1:
        raise ValueError(f"cannot resolve family cell exactly: {family_id}")
    return matches[0]


def _counter_rows(counter: Mapping[str, int], key: str) -> list[dict[str, Any]]:
    return [{key: name, "count": counter[name]} for name in sorted(counter)]


def _solver_item_gate(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    failures: list[str] = []
    if len(rows) != 2:
        failures.append("two_solver_replicates")
    if sum(bool(row.get("keyed_match")) for row in rows) < 1:
        failures.append("minimum_keyed_matches")
    if any(
        not row.get("task_understood", False)
        or not row.get("response_mechanism_clear", False)
        for row in rows
    ):
        failures.append("task_not_understood")
    if any(row.get("major_ambiguity", False) for row in rows):
        failures.append("major_ambiguity")
    pending = any(row.get("reasonable_unkeyed_responses", []) for row in rows)
    return {"passed": not failures, "failures": sorted(failures), "pending": pending}


def _stage_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return {
        "candidates_evaluated": len(rows),
        "deterministic_gate_pass": sum(bool(row["deterministic_checks_pass"]) for row in rows),
        "solver_family_gate_pass": sum(bool(row["solver_gates_pass"]) for row in rows),
        "critic_family_gate_pass": sum(bool(row["critic_gates_pass"]) for row in rows),
        "families_accepted_at_candidate": sum(row["decision"] == "accept" for row in rows),
    }


def _group_funnel(
    decisions: Sequence[Mapping[str, Any]],
    key_for: Any,
    key_name: str,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in decisions:
        for key in key_for(row):
            grouped[str(key)].append(row)
    return [
        {key_name: key, **_stage_counts(grouped[key])}
        for key in sorted(grouped)
    ]


def _critic_rows(run_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for role in ROLES:
        for path in sorted((run_root / "parsed/validation" / role).glob("*.json")):
            rows.append(read_json(path))
    return rows


def _preflight_analysis(
    provider_root: Path, reconstruction_root: Path, scientific_root: Path
) -> dict[str, Any]:
    provider_calls = [
        read_json(path)
        for path in sorted((provider_root / "provenance/calls").glob("*.json"))
    ]
    provider_attempts = sorted(
        (provider_root / "raw/generation").glob("*/attempt_*")
    )
    error = ""
    if provider_attempts:
        stderr = (provider_attempts[0] / "cli_stderr.txt").read_text(
            encoding="utf-8", errors="replace"
        )
        match = re.search(r'"message":\s*"([^"]+)"', stderr)
        error = match.group(1) if match else stderr.strip().splitlines()[-1]
    property_schema: dict[str, Any] = {}
    if provider_attempts:
        property_schema = read_json(provider_attempts[0] / "output_schema.json")[
            "properties"
        ]["protocol_id"]

    reconstruction_calls = read_jsonl(
        reconstruction_root / "provenance/call_records.jsonl"
    )
    checks = [
        read_json(path)
        for path in sorted(
            (reconstruction_root / "provenance/deterministic_checks").glob("*.json")
        )
    ]
    generated = [
        read_json(path)
        for path in sorted((reconstruction_root / "parsed/generation").glob("*.json"))
    ]
    old_config = (reconstruction_root / "frozen/config.yaml").read_text(encoding="utf-8")
    new_config = (scientific_root / "frozen/config.yaml").read_text(encoding="utf-8")
    old_prompt = (
        reconstruction_root / "frozen/prompts/generate_family.txt"
    ).read_text(encoding="utf-8")
    new_prompt = (scientific_root / "frozen/prompts/generate_family.txt").read_text(
        encoding="utf-8"
    )
    return {
        "provider_schema_preflight": {
            "run_id": provider_root.name,
            "classification": "infrastructure_failure_before_model_inference",
            "request_id": provider_calls[0]["request_id"] if provider_calls else None,
            "attempts": len(provider_calls),
            "technical_failures": sum(
                row.get("status") == "technical_failure" for row in provider_calls
            ),
            "identical_request_input_hash": len(
                {row.get("input_sha256") for row in provider_calls}
            )
            == 1,
            "identical_prompt_hash": len(
                {row.get("prompt_sha256") for row in provider_calls}
            )
            == 1,
            "identical_output_schema_hash": len(
                {row.get("output_schema_sha256") for row in provider_calls}
            )
            == 1,
            "provider_error": error,
            "offending_protocol_id_schema": property_schema,
            "parsed_outputs": sum(
                row.get("parsed_output_sha256") is not None for row in provider_calls
            ),
            "scientific_judgments": 0,
            "interpretation": (
                "The provider rejected a dynamic const-only property without an "
                "explicit type. All three byte-identical retries failed before an "
                "inference result, so this run contains no item-quality evidence."
            ),
        },
        "dialogue_reconstruction_preflight": {
            "run_id": reconstruction_root.name,
            "classification": "deterministic_reconstruction_infrastructure_failure",
            "calls": len(reconstruction_calls),
            "complete_calls": sum(
                row.get("status") == "complete" for row in reconstruction_calls
            ),
            "candidate_id": checks[0]["candidate_id"] if checks else None,
            "failed_checks": checks[0]["failed_checks"] if checks else [],
            "canonical_target_sentence": (
                generated[0]["canonical_target_sentence"] if generated else None
            ),
            "dialogue_incomplete_turn_template": (
                generated[0]["items"][1]["format_payload"][
                    "incomplete_turn_template"
                ]
                if generated
                else None
            ),
            "old_config_declared_speaker_label_exclusion": (
                "dialogue_speaker_label_excluded_from_target_reconstruction"
                in old_config
            ),
            "scientific_run_declared_speaker_label_exclusion": (
                "dialogue_speaker_label_excluded_from_target_reconstruction"
                in new_config
            ),
            "old_prompt_explained_speaker_label": (
                "interface metadata and is excluded" in old_prompt
            ),
            "scientific_prompt_explained_speaker_label": (
                "interface metadata and is excluded" in new_prompt
            ),
            "scientific_judgments": 0,
            "interpretation": (
                "One valid structured generation exposed that a visible Speaker: "
                "label was being compared as part of the target utterance. The "
                "preflight stopped before solver or critic judgment; v0_2 explicitly "
                "declared and froze the interface-metadata exclusion."
            ),
        },
    }


def analyze(
    run_root: Path = DEFAULT_RUN,
    provider_preflight: Path = DEFAULT_PROVIDER_PREFLIGHT,
    reconstruction_preflight: Path = DEFAULT_RECONSTRUCTION_PREFLIGHT,
) -> dict[str, Any]:
    selected = read_json(run_root / "frozen/selected_cells.json")
    cells = _cell_catalog(selected)
    kc_order = list(selected["kc_order"])
    decisions = read_jsonl(run_root / "curation/family_decisions.jsonl")
    rejections = read_jsonl(run_root / "curation/rejections.jsonl")
    call_records = read_jsonl(run_root / "provenance/call_records.jsonl")
    if decisions != sorted(decisions, key=lambda row: row["candidate_round"]):
        # The within-round order is the frozen selection order, not lexical ID.
        rounds = [row["candidate_round"] for row in decisions]
        if rounds != sorted(rounds):
            raise ValueError("curation decisions are not round-monotonic")
    if [row for row in decisions if row["decision"] == "reject"] != rejections:
        raise ValueError("rejection ledger does not exactly project decisions")

    generations = {
        path.stem: read_json(path)
        for path in sorted((run_root / "parsed/generation").glob("*.json"))
    }
    deterministic = {
        path.stem: read_json(path)
        for path in sorted(
            (run_root / "provenance/deterministic_checks").glob("*.json")
        )
    }
    solver_rows = [
        read_json(path)
        for path in sorted((run_root / "parsed/solver").glob("*.json"))
    ]
    critics = _critic_rows(run_root)
    decision_by_candidate = {row["candidate_id"]: row for row in decisions}
    if set(decision_by_candidate) != set(generations) or set(generations) != set(
        deterministic
    ):
        raise ValueError("candidate generation/check/decision coverage differs")

    family_ids = sorted({row["family_id"] for row in decisions})
    accepted_decisions = [row for row in decisions if row["decision"] == "accept"]
    accepted_ids = {row["family_id"] for row in accepted_decisions}
    family_to_cell = {
        family_id: _family_cell(family_id, cells) for family_id in family_ids
    }
    candidate_to_cell = {
        row["candidate_id"]: family_to_cell[row["family_id"]] for row in decisions
    }

    def decision_regime(row: Mapping[str, Any]) -> list[str]:
        return [cells[candidate_to_cell[row["candidate_id"]]]["grammar_regime"]]

    def decision_cell(row: Mapping[str, Any]) -> list[str]:
        return [candidate_to_cell[row["candidate_id"]]]

    def decision_kcs(row: Mapping[str, Any]) -> list[str]:
        return list(cells[candidate_to_cell[row["candidate_id"]]]["generator_kc_ids"])

    rounds = []
    for round_index in (1, 2, 3):
        subset = [row for row in decisions if row["candidate_round"] == round_index]
        rounds.append({"candidate_round": round_index, **_stage_counts(subset)})
    overall = _stage_counts(decisions)
    overall.update(
        {
            "candidate_requests_preregistered": read_json(run_root / "plan.json")[
                "counts"
            ]["generation_requests"],
            "families_preregistered": 38,
            "families_accepted": len(accepted_ids),
            "families_exhausted_after_round_3": len(set(family_ids) - accepted_ids),
        }
    )

    # Candidate-item and solver funnels by format.
    solver_by_item: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in solver_rows:
        solver_by_item[row["item_id"]].append(row)
    format_stats: dict[str, Counter[str]] = {name: Counter() for name in FORMATS}
    solver_failure_examples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    all_solver_failure_ids: dict[str, set[str]] = defaultdict(set)
    item_format_by_id: dict[str, str] = {}
    for decision in decisions:
        family = generations[decision["candidate_id"]]
        for item in family["items"]:
            item_id = item["candidate_item_id"]
            item_format = item["format"]
            item_format_by_id[item_id] = item_format
            counter = format_stats[item_format]
            counter["candidate_items"] += 1
            counter["family_deterministic_gate_pass"] += int(
                decision["deterministic_checks_pass"]
            )
            attempts = solver_by_item.get(item_id, [])
            if attempts:
                counter["solver_items_attempted"] += 1
                counter["solver_attempts"] += len(attempts)
                counter["keyed_attempts"] += sum(
                    bool(row["keyed_match"]) for row in attempts
                )
                counter["major_ambiguity_attempts"] += sum(
                    bool(row["major_ambiguity"]) for row in attempts
                )
                counter["task_or_mechanism_unclear_attempts"] += sum(
                    not row["task_understood"]
                    or not row["response_mechanism_clear"]
                    for row in attempts
                )
                gate = _solver_item_gate(attempts)
                counter["solver_item_gate_pass"] += int(gate["passed"])
                counter["reasonable_unkeyed_pending_items"] += int(gate["pending"])
                for failure in gate["failures"]:
                    counter[f"solver_failure:{failure}"] += 1
                    all_solver_failure_ids[failure].add(item_id)
                    if len(solver_failure_examples[failure]) < 5:
                        solver_failure_examples[failure].append(
                            {
                                "item_id": item_id,
                                "family_id": decision["family_id"],
                                "candidate_id": decision["candidate_id"],
                                "cell_id": candidate_to_cell[decision["candidate_id"]],
                                "format": item_format,
                                "canonical_target_sentence": family[
                                    "canonical_target_sentence"
                                ],
                                "attempts": [
                                    {
                                        "solver_attempt_id": row[
                                            "solver_attempt_id"
                                        ],
                                        "replicate": row["replicate"],
                                        "submitted_response": row[
                                            "submitted_response"
                                        ],
                                        "keyed_match": row["keyed_match"],
                                        "task_understood": row["task_understood"],
                                        "response_mechanism_clear": row[
                                            "response_mechanism_clear"
                                        ],
                                        "major_ambiguity": row[
                                            "major_ambiguity"
                                        ],
                                        "ambiguity_explanation": row[
                                            "ambiguity_explanation"
                                        ],
                                        "reasonable_unkeyed_responses": row[
                                            "reasonable_unkeyed_responses"
                                        ],
                                    }
                                    for row in sorted(
                                        attempts, key=lambda value: value["replicate"]
                                    )
                                ],
                            }
                        )
            if decision["solver_gates_pass"]:
                counter["reached_all_critics"] += 1
            counter["family_critic_gate_pass"] += int(
                decision["critic_gates_pass"]
            )
            counter["accepted_items"] += int(decision["decision"] == "accept")

    # Deterministic failure taxonomy.
    deterministic_counter: Counter[str] = Counter()
    deterministic_examples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate_id, row in sorted(deterministic.items()):
        for check in row["failed_checks"]:
            deterministic_counter[check] += 1
            if len(deterministic_examples[check]) < 5:
                deterministic_examples[check].append(
                    {
                        "candidate_id": candidate_id,
                        "family_id": row["family_id"],
                        "cell_id": candidate_to_cell[candidate_id],
                        "canonical_target_sentence": generations[candidate_id][
                            "canonical_target_sentence"
                        ],
                    }
                )

    # Critic concern and disagreement ledgers.
    critic_by_candidate: dict[str, list[dict[str, Any]]] = defaultdict(list)
    criteria: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    format_disagreements: list[dict[str, Any]] = []
    for row in critics:
        candidate_id = row["candidate_id"]
        critic_by_candidate[candidate_id].append(row)
        per_criterion_formats: dict[str, dict[str, str]] = defaultdict(dict)
        judgments: list[tuple[str, str | None, Mapping[str, Any]]] = []
        for item in row["item_judgments"]:
            item_format = item_format_by_id[item["item_id"]]
            for judgment in item["criteria"]:
                judgments.append(("item", item_format, judgment))
                per_criterion_formats[judgment["criterion"]][item_format] = judgment[
                    "severity"
                ]
        for judgment in row["family_judgments"]:
            judgments.append(("family", None, judgment))
        for scope, item_format, judgment in judgments:
            key = (row["role"], scope, judgment["criterion"], item_format or "all_formats")
            record = criteria.setdefault(
                key,
                {
                    "role": row["role"],
                    "scope": scope,
                    "criterion": judgment["criterion"],
                    "format": item_format,
                    "judgments": 0,
                    "severity_counts": Counter(),
                    "blocking_judgments": 0,
                    "concern_candidate_ids": set(),
                    "examples": [],
                },
            )
            record["judgments"] += 1
            record["severity_counts"][judgment["severity"]] += 1
            record["blocking_judgments"] += int(judgment["blocking"])
            if judgment["severity"] != "pass" or judgment["blocking"]:
                record["concern_candidate_ids"].add(candidate_id)
                if len(record["examples"]) < 3:
                    record["examples"].append(
                        {
                            "candidate_id": candidate_id,
                            "family_id": row["family_id"],
                            "item_id": (
                                next(
                                    item["item_id"]
                                    for item in row["item_judgments"]
                                    if item_format
                                    and item_format_by_id[item["item_id"]]
                                    == item_format
                                )
                                if item_format
                                else None
                            ),
                            "severity": judgment["severity"],
                            "blocking": judgment["blocking"],
                            "evidence": judgment["evidence"],
                        }
                    )
        for criterion, severity_by_format in sorted(per_criterion_formats.items()):
            if len(set(severity_by_format.values())) > 1:
                format_disagreements.append(
                    {
                        "candidate_id": candidate_id,
                        "family_id": row["family_id"],
                        "role": row["role"],
                        "criterion": criterion,
                        "severity_by_format": dict(sorted(severity_by_format.items())),
                    }
                )

    role_summary = []
    for role in ROLES:
        subset = [row for row in critics if row["role"] == role]
        role_summary.append(
            {
                "role": role,
                "family_judgments": len(subset),
                "overall_accept": sum(bool(row["overall_accept"]) for row in subset),
                "overall_reject": sum(not row["overall_accept"] for row in subset),
                "candidates_with_any_major_concern": sum(
                    any(
                        value["severity"] == "major_concern"
                        for value in [
                            *row["family_judgments"],
                            *[
                                criterion
                                for item in row["item_judgments"]
                                for criterion in item["criteria"]
                            ],
                        ]
                    )
                    for row in subset
                ),
                "candidates_with_any_blocking_judgment": sum(
                    any(
                        value["blocking"]
                        for value in [
                            *row["family_judgments"],
                            *[
                                criterion
                                for item in row["item_judgments"]
                                for criterion in item["criteria"]
                            ],
                        ]
                    )
                    for row in subset
                ),
            }
        )

    role_disagreements: list[dict[str, Any]] = []
    unanimous_accept_but_gate_failed: list[dict[str, Any]] = []
    role_patterns: Counter[str] = Counter()
    for candidate_id, rows in sorted(critic_by_candidate.items()):
        accepts = sorted(row["role"] for row in rows if row["overall_accept"])
        rejects = sorted(row["role"] for row in rows if not row["overall_accept"])
        if not rejects:
            pattern = "all_roles_accept"
        elif not accepts:
            pattern = "all_roles_reject"
        else:
            pattern = "mixed_role_decision"
            role_disagreements.append(
                {
                    "candidate_id": candidate_id,
                    "family_id": rows[0]["family_id"],
                    "accepting_roles": accepts,
                    "rejecting_roles": rejects,
                }
            )
        role_patterns[pattern] += 1
        decision = decision_by_candidate[candidate_id]
        if pattern == "all_roles_accept" and not decision["critic_gates_pass"]:
            unanimous_accept_but_gate_failed.append(
                {
                    "candidate_id": candidate_id,
                    "family_id": rows[0]["family_id"],
                    "failed_critic_gates": [
                        gate
                        for gate in decision["failed_gates"]
                        if gate.startswith("critic:")
                    ],
                    "explanation": (
                        "All roles set overall_accept=true, but at least one "
                        "preregistered must-pass criterion was minor rather than pass."
                    ),
                }
            )

    criterion_rows = []
    for key in sorted(criteria):
        record = criteria[key]
        severity = record.pop("severity_counts")
        candidate_ids = sorted(record.pop("concern_candidate_ids"))
        criterion_rows.append(
            {
                **record,
                "severity_counts": {
                    name: severity.get(name, 0)
                    for name in ("pass", "minor_concern", "major_concern")
                },
                "concern_candidates": len(candidate_ids),
                "concern_candidate_ids": candidate_ids,
                "must_pass": record["criterion"] in MUST_PASS[record["role"]],
            }
        )

    # Cell/KC/regime family coverage and accepted Q geometry.
    cell_rows = []
    for cell_id, cell in sorted(cells.items(), key=lambda value: value[1]["selection_order"]):
        cell_families = sorted(fid for fid in family_ids if family_to_cell[fid] == cell_id)
        cell_decisions = [
            row for row in decisions if candidate_to_cell[row["candidate_id"]] == cell_id
        ]
        accepted = sorted(set(cell_families) & accepted_ids)
        cell_rows.append(
            {
                "cell_id": cell_id,
                "grammar_regime": cell["grammar_regime"],
                "features": cell["features"],
                "generator_kc_ids": cell["generator_kc_ids"],
                "q_row": cell["q_row"],
                "families_required": len(cell_families),
                "families_accepted": len(accepted),
                "accepted_family_ids": accepted,
                "complete_cell_family_coverage": len(accepted) == len(cell_families),
                **_stage_counts(cell_decisions),
            }
        )

    kc_rows = []
    for kc_index, kc_id in enumerate(kc_order):
        active_cells = [
            cell_id
            for cell_id, cell in cells.items()
            if cell["q_row"][kc_index] == 1
        ]
        required = sorted(fid for fid in family_ids if family_to_cell[fid] in active_cells)
        accepted = sorted(set(required) & accepted_ids)
        kc_decisions = [
            row
            for row in decisions
            if candidate_to_cell[row["candidate_id"]] in active_cells
        ]
        kc_rows.append(
            {
                "kc_id": kc_id,
                "active_selected_cell_ids": sorted(active_cells),
                "required_families": len(required),
                "accepted_families": len(accepted),
                "accepted_family_ids": accepted,
                "has_accepted_measurement_support": bool(accepted),
                **_stage_counts(kc_decisions),
            }
        )

    accepted_examples = []
    for decision in accepted_decisions:
        family = generations[decision["candidate_id"]]
        cell_id = candidate_to_cell[decision["candidate_id"]]
        accepted_examples.append(
            {
                "family_id": decision["family_id"],
                "candidate_id": decision["candidate_id"],
                "selected_candidate_round": decision["candidate_round"],
                "cell_id": cell_id,
                "grammar_regime": cells[cell_id]["grammar_regime"],
                "generator_kc_ids": cells[cell_id]["generator_kc_ids"],
                "q_row": cells[cell_id]["q_row"],
                "canonical_target_sentence": family["canonical_target_sentence"],
                "learner_facing_items": [
                    {
                        "item_id": item["candidate_item_id"],
                        "format": item["format"],
                        "instruction": item["instruction"],
                        "context": item["context"],
                        "target_response": item["scoring"]["target_response"],
                    }
                    for item in family["items"]
                ],
            }
        )

    accepted_seen = [
        row
        for row in accepted_examples
        if row["grammar_regime"] == "seen"
    ]
    accepted_q_rows = [row["q_row"] for row in accepted_examples]
    accepted_seen_q_rows = [row["q_row"] for row in accepted_seen]
    active_kcs = [
        kc_id
        for index, kc_id in enumerate(kc_order)
        if any(row[index] for row in accepted_q_rows)
    ]
    accepted_cell_ids = sorted({row["cell_id"] for row in accepted_examples})
    accepted_seen_cells = sorted({row["cell_id"] for row in accepted_seen})

    gate_counter = Counter(
        gate for row in rejections for gate in row["failed_gates"]
    )
    call_stage_status = Counter(
        (row["stage"], row["status"]) for row in call_records
    )
    analysis = {
        "analysis_schema": "measurement_realism_matched_bank_negative_result_v1",
        "run_id": run_root.name,
        "status": "FAILED_PREREGISTERED_BANK_FREEZE_GATE",
        "scientific_boundaries": {
            "full_v1_modified": False,
            "learner_outcomes_read": False,
            "simulator_or_kt_results_read": False,
            "raw_evidence_modified": False,
            "automated_judgments_are_human_evidence": False,
            "numeric_average_or_composite_realism_score": False,
            "unit_of_acceptance": "whole four-format semantic family",
        },
        "preflight_failures": _preflight_analysis(
            provider_preflight, reconstruction_preflight, run_root
        ),
        "execution_integrity": {
            "call_records": len(call_records),
            "calls_by_stage_and_status": [
                {"stage": key[0], "status": key[1], "calls": count}
                for key, count in sorted(call_stage_status.items())
            ],
            "generation_outputs": len(generations),
            "deterministic_check_records": len(deterministic),
            "solver_attempt_records": len(solver_rows),
            "critic_family_role_records": len(critics),
            "curation_decisions": len(decisions),
            "rejection_rows": len(rejections),
            "scientific_run_technical_failures": sum(
                row["status"] != "complete" for row in call_records
            ),
        },
        "pass_funnel": {
            "overall": overall,
            "by_candidate_round": rounds,
            "by_grammar_regime": _group_funnel(
                decisions, decision_regime, "grammar_regime"
            ),
            "by_cell": cell_rows,
            "by_kc": kc_rows,
            "by_format": [
                {"format": name, **dict(sorted(format_stats[name].items()))}
                for name in FORMATS
            ],
        },
        "deterministic_failures": {
            "candidate_families_with_failure": sum(
                not row["passed"] for row in deterministic.values()
            ),
            "failure_occurrences_by_check": _counter_rows(
                deterministic_counter, "check"
            ),
            "examples_by_check": {
                key: deterministic_examples[key]
                for key in sorted(deterministic_examples)
            },
        },
        "solver_stress_test": {
            "attempts": len(solver_rows),
            "candidate_items_attempted": len(solver_by_item),
            "keyed_match_attempts": sum(
                bool(row["keyed_match"]) for row in solver_rows
            ),
            "major_ambiguity_attempts": sum(
                bool(row["major_ambiguity"]) for row in solver_rows
            ),
            "task_or_response_mechanism_unclear_attempts": sum(
                not row["task_understood"]
                or not row["response_mechanism_clear"]
                for row in solver_rows
            ),
            "reasonable_unkeyed_response_attempts": sum(
                bool(row["reasonable_unkeyed_responses"]) for row in solver_rows
            ),
            "failing_item_ids_by_type": {
                key: sorted(value) for key, value in sorted(all_solver_failure_ids.items())
            },
            "examples_by_failure_type": {
                key: solver_failure_examples[key]
                for key in sorted(solver_failure_examples)
            },
        },
        "critics": {
            "role_separation": (
                "Each role used a separate prompt/context and could not see other "
                "role outputs; batched families within a call are not independent annotators."
            ),
            "by_role": role_summary,
            "criteria": criterion_rows,
            "overall_role_decision_patterns": _counter_rows(
                role_patterns, "pattern"
            ),
            "mixed_role_decisions": role_disagreements,
            "all_roles_overall_accept_but_hard_gate_failed": (
                unanimous_accept_but_gate_failed
            ),
            "within_role_item_criterion_format_disagreements": sorted(
                format_disagreements,
                key=lambda row: (
                    row["candidate_id"], row["role"], row["criterion"]
                ),
            ),
        },
        "rejection_gate_occurrences": _counter_rows(gate_counter, "gate"),
        "accepted_family_geometry": {
            "accepted_family_count": len(accepted_examples),
            "required_families": 38,
            "accepted_item_slots": len(accepted_examples) * 4,
            "required_item_slots": 152,
            "accepted_cell_ids": accepted_cell_ids,
            "selected_cells_covered": len(accepted_cell_ids),
            "selected_cells_required": 20,
            "accepted_seen_cell_ids": accepted_seen_cells,
            "seen_cells_covered": len(accepted_seen_cells),
            "seen_cells_required": 18,
            "seen_cells_with_both_variants_accepted": sum(
                row["grammar_regime"] == "seen"
                and row["complete_cell_family_coverage"]
                for row in cell_rows
            ),
            "seen_cells_requiring_both_variants": 18,
            "held_out_regimes_covered": sorted(
                {
                    row["grammar_regime"]
                    for row in accepted_examples
                    if row["grammar_regime"] != "seen"
                }
            ),
            "active_kc_ids": active_kcs,
            "active_kcs_covered": len(active_kcs),
            "generator_kcs_required": len(kc_order),
            "accepted_seen_q_rank": exact_rank(accepted_seen_q_rows),
            "required_seen_q_rank": 18,
            "accepted_all_regimes_q_rank": exact_rank(accepted_q_rows),
            "accepted_family_examples": accepted_examples,
        },
        "release_gate_failure": {
            "freeze_permitted": False,
            "bank_directory_present": (run_root / "bank").is_dir(),
            "failed_requirements": [
                {
                    "requirement": "all_preregistered_families_pass",
                    "observed": f"{len(accepted_ids)}/38",
                },
                {
                    "requirement": "exact_152_item_complete_crossing",
                    "observed": f"{len(accepted_ids) * 4}/152 accepted slots",
                },
                {
                    "requirement": "both_seen_variants_for_every_seen_cell",
                    "observed": (
                        f"{sum(row['grammar_regime'] == 'seen' and row['complete_cell_family_coverage'] for row in cell_rows)}/18 cells"
                    ),
                },
                {
                    "requirement": "every_selected_cell_covered",
                    "observed": f"{len(accepted_cell_ids)}/20 cells",
                },
                {
                    "requirement": "seen_q_basis_retains_rank_18",
                    "observed": f"rank {exact_rank(accepted_seen_q_rows)}/18",
                },
                {
                    "requirement": "both_held_out_probe_regimes_covered",
                    "observed": (
                        ", ".join(
                            sorted(
                                {
                                    row["grammar_regime"]
                                    for row in accepted_examples
                                    if row["grammar_regime"] != "seen"
                                }
                            )
                        )
                        or "none"
                    ),
                },
            ],
            "interpretation": (
                "The successful v0_2 execution is a negative construction result: "
                "the strict whole-family protocol did not yield a releasable bank. "
                "The five passing families remain evidence/examples, not a partial "
                "152-item release and not a full-rank confirmatory instrument."
            ),
        },
        "next_method_recommendation": {
            "smallest_scientifically_defensible_method": (
                "Create a separately versioned declared-correction layer for the 33 "
                "exhausted whole families. Link every edit to its raw candidate and an "
                "explicit failure; prohibit silent repair and cross-round format "
                "cherry-picking; then rerun deterministic reconstruction, both solver "
                "replicates, and all three role critics. Do not spend another blind "
                "no-feedback generation round under the exhausted v0 protocol."
            ),
            "expert_validation_requirement": (
                "Before calling a successor bank deployable or platform-validated, "
                "render the learner interaction and obtain independent language-teacher/"
                "measurement and product review, followed by a small learner answerability "
                "pilot. Automated passing is stress-test evidence only."
            ),
            "controlled_scenario_use": (
                "A transparently corrected, fully crossed bank can support planted "
                "format/item-effect sensitivity worlds once its structural and automated "
                "gates pass. It must be labelled a controlled measurement scenario until "
                "external validation is collected. The current five-family subset is too "
                "sparse (seen Q rank 3) for ontology-wide confirmatory claims."
            ),
            "release_validity": (
                "Dataset release additionally requires all 38 families, 152 slots, full "
                "seen rank, both probes, executable scoring, and external rendered-item "
                "validation. Declared correction can repair construction evidence; it "
                "cannot by itself establish human answerability or platform deployability."
            ),
        },
    }
    return analysis


def _pct(numerator: int, denominator: int) -> str:
    return f"{100 * numerator / denominator:.1f}%" if denominator else "NA"


def render_report(result: Mapping[str, Any]) -> str:
    funnel = result["pass_funnel"]
    overall = funnel["overall"]
    geometry = result["accepted_family_geometry"]
    solver = result["solver_stress_test"]
    critics = result["critics"]
    lines = [
        "# Matched-format bank v0: deterministic negative-result audit",
        "",
        "## Result",
        "",
        (
            f"The preregistered v0 construction **did not freeze**: "
            f"{geometry['accepted_family_count']}/38 whole semantic families "
            f"({geometry['accepted_item_slots']}/152 item slots) passed all gates. "
            f"The remaining {overall['families_exhausted_after_round_3']} families "
            "exhausted three no-feedback generation rounds. This is a successful "
            "execution with a negative construction result, not a technical failure."
        ),
        "",
        "No realism score is computed. Linguistic, solver, measurement, product, "
        "coverage, and Q-geometry evidence remain separate.",
        "",
        "## Run integrity and preflights",
        "",
        (
            f"The scientific run retained {result['execution_integrity']['call_records']} "
            "complete audited calls, "
            f"{result['execution_integrity']['generation_outputs']} generated candidates, "
            f"{result['execution_integrity']['solver_attempt_records']} solver attempts, "
            f"and {result['execution_integrity']['critic_family_role_records']} "
            "family-role critic records, with zero technical failures."
        ),
        "",
        "Two earlier preflights are excluded from scientific counts:",
        "",
        (
            "- `matched_bank_v0_20260830`: three byte-identical calls were rejected "
            "by the provider because a dynamic `const` property lacked an explicit "
            "JSON-schema `type`; no inference output or scientific judgment exists."
        ),
        (
            "- `matched_bank_v0_1_20260830`: one complete generation exposed an "
            "orchestrator reconstruction bug: a visible `Speaker:` label was treated "
            "as part of the target utterance. It stopped before solvers/critics. The "
            "v0_2 prompt and gate explicitly froze the speaker-label exclusion."
        ),
        "",
        "## Candidate pass funnel",
        "",
        "| Round | Evaluated | Deterministic | Solver-family | All critics | Accepted |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for row in funnel["by_candidate_round"]:
        lines.append(
            f"| {row['candidate_round']} | {row['candidates_evaluated']} | "
            f"{row['deterministic_gate_pass']} | {row['solver_family_gate_pass']} | "
            f"{row['critic_family_gate_pass']} | {row['families_accepted_at_candidate']} |"
        )
    lines.extend(
        [
            (
                f"| **All** | **{overall['candidates_evaluated']}** | "
                f"**{overall['deterministic_gate_pass']}** | "
                f"**{overall['solver_family_gate_pass']}** | "
                f"**{overall['critic_family_gate_pass']}** | "
                f"**{overall['families_accepted_at_candidate']}** |"
            ),
            "",
            "A family reaches critics only after every one of its four items passes "
            "the deterministic and two-replicate solver gates. Formats were never "
            "cherry-picked across rounds.",
            "",
            "## Solver evidence by format",
            "",
            "| Format | Items attempted | Item gate pass | No keyed match | Major ambiguity | Task/UI unclear | Reasonable unkeyed pending |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in funnel["by_format"]:
        lines.append(
            f"| {row['format']} | {row.get('solver_items_attempted', 0)} | "
            f"{row.get('solver_item_gate_pass', 0)} | "
            f"{row.get('solver_failure:minimum_keyed_matches', 0)} | "
            f"{row.get('solver_failure:major_ambiguity', 0)} | "
            f"{row.get('solver_failure:task_not_understood', 0)} | "
            f"{row.get('reasonable_unkeyed_pending_items', 0)} |"
        )
    lines.extend(
        [
            "",
            (
                f"Across {solver['attempts']} attempts, "
                f"{solver['keyed_match_attempts']} matched a keyed answer, "
                f"{solver['major_ambiguity_attempts']} flagged major ambiguity, and "
                f"{solver['reasonable_unkeyed_response_attempts']} proposed at least "
                "one reasonable unkeyed response. These are automated stress tests, "
                "not learner success rates."
            ),
            "",
            "## Independent critic evidence",
            "",
            "| Role | Families judged | Overall accept | Overall reject | Any major concern | Any blocking judgment |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in critics["by_role"]:
        lines.append(
            f"| {row['role']} | {row['family_judgments']} | "
            f"{row['overall_accept']} | {row['overall_reject']} | "
            f"{row['candidates_with_any_major_concern']} | "
            f"{row['candidates_with_any_blocking_judgment']} |"
        )
    pattern = {row["pattern"]: row["count"] for row in critics["overall_role_decision_patterns"]}
    lines.extend(
        [
            "",
            (
                f"Role decisions were unanimous accepts for "
                f"{pattern.get('all_roles_accept', 0)}/30 critic-reached candidates, "
                f"unanimous rejects for {pattern.get('all_roles_reject', 0)}/30, and "
                f"mixed for {pattern.get('mixed_role_decision', 0)}/30. Disagreements "
                "and criterion evidence are retained by exact candidate/item ID in the JSON."
            ),
            (
                f"Of the {pattern.get('all_roles_accept', 0)} unanimous overall accepts, "
                f"{len(critics['all_roles_overall_accept_but_hard_gate_failed'])} still "
                "failed the preregistered critic gate because a must-pass criterion was "
                "rated `minor_concern` rather than `pass`; overall labels never overrode "
                "criterion gates."
            ),
            "",
            "The most frequent non-pass criterion/format records were:",
            "",
            "| Role | Scope | Criterion | Format | Minor | Major | Concern candidates |",
            "|---|---|---|---|---:|---:|---:|",
        ]
    )
    concern_rows = sorted(
        (
            row
            for row in critics["criteria"]
            if row["severity_counts"]["minor_concern"]
            or row["severity_counts"]["major_concern"]
        ),
        key=lambda row: (
            -row["severity_counts"]["major_concern"],
            -row["severity_counts"]["minor_concern"],
            row["role"],
            row["criterion"],
            row["format"] or "",
        ),
    )[:15]
    for row in concern_rows:
        lines.append(
            f"| {row['role']} | {row['scope']} | {row['criterion']} | "
            f"{row['format'] or 'all formats'} | "
            f"{row['severity_counts']['minor_concern']} | "
            f"{row['severity_counts']['major_concern']} | "
            f"{row['concern_candidates']} |"
        )
    lines.extend(
        [
            "",
            "## Accepted coverage and Q geometry",
            "",
            (
                f"The five passing families cover {geometry['selected_cells_covered']}/20 "
                f"selected cells, {geometry['seen_cells_covered']}/18 seen cells, and "
                f"{geometry['active_kcs_covered']}/18 generator KCs. Only "
                f"{geometry['seen_cells_with_both_variants_accepted']}/18 seen cells "
                "has both required semantic variants. The accepted seen Q rows have "
                f"exact rank {geometry['accepted_seen_q_rank']}, not 18; adding the "
                f"accepted unseen-combination probe raises all-regime rank to "
                f"{geometry['accepted_all_regimes_q_rank']}."
            ),
            "",
            "| Family | Round | Regime | Cell | KCs | Target |",
            "|---|---:|---|---|---|---|",
        ]
    )
    for row in geometry["accepted_family_examples"]:
        lines.append(
            f"| `{row['family_id']}` | {row['selected_candidate_round']} | "
            f"{row['grammar_regime']} | `{row['cell_id']}` | "
            f"{', '.join(row['generator_kc_ids'])} | "
            f"{row['canonical_target_sentence']} |"
        )
    lines.extend(
        [
            "",
            "The full JSON includes every cell and KC funnel, all accepted learner-facing "
            "item IDs/examples, every solver-failure item ID, deterministic examples, "
            "critic disagreements, and criterion-level evidence. Counts that activate "
            "multiple KCs are deliberately non-exclusive.",
            "",
            "## Why the release gate failed",
            "",
        ]
    )
    for row in result["release_gate_failure"]["failed_requirements"]:
        lines.append(f"- `{row['requirement']}`: {row['observed']}.")
    lines.extend(
        [
            "",
            "Consequently, no `bank/` release was frozen. Treating the 20 accepted "
            "slots as a partial release would violate the preregistered family, coverage, "
            "held-out, and full-rank design.",
            "",
            "## Smallest defensible successor method",
            "",
            result["next_method_recommendation"]["smallest_scientifically_defensible_method"],
            "",
            result["next_method_recommendation"]["expert_validation_requirement"],
            "",
            "A corrected fully crossed bank may be used as a **controlled measurement "
            "scenario** for planted format/item-effect experiments once all structural "
            "and automated gates replay. That is distinct from **release validity**: "
            "human/expert rendered-item review and a learner answerability pilot remain "
            "necessary before platform-deployability claims.",
            "",
            "## Reproduction",
            "",
            "```bash",
            ".venv/bin/python scripts/experiments/analyze_measurement_realism_bank_failure.py analyze",
            ".venv/bin/python scripts/experiments/analyze_measurement_realism_bank_failure.py verify",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def source_records(
    run_root: Path, provider_preflight: Path, reconstruction_preflight: Path
) -> dict[str, Any]:
    files = [
        run_root / "plan.json",
        run_root / "frozen/config.yaml",
        run_root / "frozen/selected_cells.json",
        run_root / "frozen/prompts/generate_family.txt",
        run_root / "curation/family_decisions.jsonl",
        run_root / "curation/rejections.jsonl",
        run_root / "provenance/call_records.jsonl",
        run_root / "provenance/call_evidence_manifest.json",
        run_root / "provenance/call_evidence_bundle.jsonl",
    ]
    trees = [
        run_root / "parsed/generation",
        run_root / "parsed/solver",
        run_root / "parsed/validation",
        run_root / "provenance/deterministic_checks",
        provider_preflight,
        reconstruction_preflight,
    ]
    return {
        "files": [file_record(path) for path in files],
        "trees": [tree_record(path) for path in trees],
    }


def write_outputs(
    run_root: Path,
    provider_preflight: Path,
    reconstruction_preflight: Path,
) -> dict[str, Any]:
    output_root = run_root / "analysis"
    output_root.mkdir(parents=True, exist_ok=True)
    result = analyze(run_root, provider_preflight, reconstruction_preflight)
    json_path = output_root / "failure_analysis.json"
    report_path = output_root / "failure_analysis.md"
    json_path.write_text(pretty_json(result), encoding="utf-8")
    report_path.write_text(render_report(result), encoding="utf-8")
    manifest = {
        "manifest_schema": "measurement_realism_matched_bank_negative_result_package_v1",
        "run_id": run_root.name,
        "status": "FAILED_PREREGISTERED_BANK_FREEZE_GATE",
        "source_evidence": source_records(
            run_root, provider_preflight, reconstruction_preflight
        ),
        "analysis_implementation": file_record(Path(__file__).resolve()),
        "outputs": [file_record(json_path), file_record(report_path)],
        "verification_command": (
            ".venv/bin/python scripts/experiments/"
            "analyze_measurement_realism_bank_failure.py verify"
        ),
    }
    manifest_path = output_root / "negative_result_manifest.json"
    manifest_path.write_text(pretty_json(manifest), encoding="utf-8")
    return manifest


def verify_outputs(
    run_root: Path,
    provider_preflight: Path,
    reconstruction_preflight: Path,
) -> dict[str, Any]:
    output_root = run_root / "analysis"
    manifest_path = output_root / "negative_result_manifest.json"
    manifest = read_json(manifest_path)
    expected_result = analyze(run_root, provider_preflight, reconstruction_preflight)
    expected_report = render_report(expected_result)
    json_path = output_root / "failure_analysis.json"
    report_path = output_root / "failure_analysis.md"
    checks = {
        "analysis_json_exact": json_path.read_text(encoding="utf-8")
        == pretty_json(expected_result),
        "analysis_markdown_exact": report_path.read_text(encoding="utf-8")
        == expected_report,
        "source_evidence_exact": manifest["source_evidence"]
        == source_records(run_root, provider_preflight, reconstruction_preflight),
        "implementation_hash_exact": manifest["analysis_implementation"]
        == file_record(Path(__file__).resolve()),
        "output_hashes_exact": manifest["outputs"]
        == [file_record(json_path), file_record(report_path)],
        "full_v1_not_an_analysis_output": all(
            not row["path"].startswith("data/grammar_kt_full_v1/")
            for row in manifest["outputs"]
        ),
    }
    if not all(checks.values()):
        raise RuntimeError(f"negative-result verification failed: {checks}")
    return {"status": "PASS", "run_id": run_root.name, "checks": checks}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("analyze", "verify"))
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN)
    parser.add_argument(
        "--provider-preflight", type=Path, default=DEFAULT_PROVIDER_PREFLIGHT
    )
    parser.add_argument(
        "--reconstruction-preflight",
        type=Path,
        default=DEFAULT_RECONSTRUCTION_PREFLIGHT,
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "analyze":
        result = write_outputs(
            args.run_root, args.provider_preflight, args.reconstruction_preflight
        )
    else:
        result = verify_outputs(
            args.run_root, args.provider_preflight, args.reconstruction_preflight
        )
    print(pretty_json(result), end="")


if __name__ == "__main__":
    main()
