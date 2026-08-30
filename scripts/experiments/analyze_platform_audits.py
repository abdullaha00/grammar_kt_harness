#!/usr/bin/env python3
"""Deterministically synthesize the two full-v1 platform-item audits.

The strict census is a single role-separated Codex review.  The live audit is
four independent role prompts aggregated by a preregistered plurality rule.
Neither is human or expert gold.  This script maps their five disposition
labels, verifies exact item coverage, and writes a cross-audit JSON artifact
plus the final platform-plausibility report.  It never writes into full-v1.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_STRICT_LEDGER = (
    ROOT
    / "experiments/measurement_realism/audits/item_audit/item_level_audit.jsonl"
)
DEFAULT_STRICT_SUMMARY = (
    ROOT / "experiments/measurement_realism/audits/item_audit/summary.json"
)
DEFAULT_LIVE_AGGREGATES = (
    ROOT
    / "experiments/measurement_realism/audits/full_v1_items_v2/item_aggregates.jsonl"
)
DEFAULT_LIVE_JUDGMENTS = (
    ROOT
    / "experiments/measurement_realism/audits/full_v1_items_v2/judgments.jsonl"
)
DEFAULT_LIVE_SUMMARY = (
    ROOT / "experiments/measurement_realism/audits/full_v1_items_v2/summary.json"
)
DEFAULT_LIVE_PLAN = (
    ROOT / "experiments/measurement_realism/audits/full_v1_items_v2/study_plan.json"
)
DEFAULT_ITEMS = ROOT / "data/grammar_kt_full_v1/items/items.jsonl"
DEFAULT_DATASET_MANIFEST = ROOT / "data/grammar_kt_full_v1/manifest.json"
DEFAULT_JSON_OUTPUT = (
    ROOT
    / "experiments/measurement_realism/audits/platform_audit_synthesis.json"
)
DEFAULT_REPORT_OUTPUT = ROOT / "reports/platform_plausibility_audit.md"


CATEGORY_MAPPING: tuple[dict[str, Any], ...] = (
    {
        "canonical": "usable",
        "strict": "usable_as_stored",
        "live": "usable_as_is",
        "operational_severity_rank": 0,
        "meaning": "No material stored-task problem was identified under the audit's stated UI/scoring assumptions.",
    },
    {
        "canonical": "local_change",
        "strict": "minor_ui_or_context_change",
        "live": "minor_ui_or_answer_set_change",
        "operational_severity_rank": 1,
        "meaning": "A local UI, wording, context, or accepted-answer change may suffice.",
    },
    {
        "canonical": "artificial",
        "strict": "technically_valid_but_artificial",
        "live": "pedagogically_artificial",
        "operational_severity_rank": 2,
        "meaning": "The form is answerable but the interaction is pedagogically or platform-wise artificial as stored.",
    },
    {
        "canonical": "answer_space",
        "strict": "answer_space_problem",
        "live": "problematic_answer_space",
        "operational_severity_rank": 3,
        "meaning": "A salient reasonable response or construction is not fairly excluded or credited.",
    },
    {
        "canonical": "withhold",
        "strict": "rewrite_or_withhold",
        "live": "probably_not_deployable",
        "operational_severity_rank": 4,
        "meaning": "The task requires substantive redesign or withholding, not ordinary copy-editing.",
    },
)

CATEGORIES = tuple(row["canonical"] for row in CATEGORY_MAPPING)
STRICT_TO_CANONICAL = {row["strict"]: row["canonical"] for row in CATEGORY_MAPPING}
LIVE_TO_CANONICAL = {row["live"]: row["canonical"] for row in CATEGORY_MAPPING}
CANONICAL_RANK = {
    row["canonical"]: row["operational_severity_rank"] for row in CATEGORY_MAPPING
}
LIVE_ROLES = ("learner", "teacher", "platform_product", "measurement")

REPRESENTATIVE_ITEMS: tuple[tuple[str, str], ...] = (
    ("shared_clear_pass", "candidate_gc_0397fa37f2228649_02"),
    ("shared_answer_space_failure", "candidate_gc_0397fa37f2228649_01"),
    (
        "shared_artificial_interface",
        "cue_bounded_imperative_gc_04a854582c08aa84_01",
    ),
    (
        "strict_measurement_purity_escalation",
        "unchanged_rescue_gc_fac1ce90011b677c_02",
    ),
    ("live_temporal_determinacy_escalation", "candidate_gc_19ed2b72505b3a96_01"),
    ("shared_modal_answer_space_failure", "unchanged_rescue_gc_8a330fc9e496e359_02"),
)


HARD_GATES: tuple[dict[str, str], ...] = (
    {
        "gate": "linguistic_fidelity",
        "requirement": "The visible task and keyed answer instantiate the declared GrammarCell; the context must not favor a different cell.",
        "failure_action": "Rewrite or withhold; do not repair by accepting an answer that changes the intended Q row.",
    },
    {
        "gate": "task_and_ui_completeness",
        "requirement": "Instruction, context/stimulus, response component, and learner action are explicit and executable rather than described through annotation-like prose.",
        "failure_action": "Supply the missing UI/media or redesign the interaction before validation.",
    },
    {
        "gate": "answer_determinacy",
        "requirement": "The information shown selects the intended response mechanism and construction without requiring the learner to guess author intent.",
        "failure_action": "Add a natural constraint or redesign; an extra answer is insufficient when it changes the measured GrammarCell.",
    },
    {
        "gate": "response_space_fairness",
        "requirement": "The executable scorer covers licensed contractions, punctuation/whitespace normalization, and salient valid responses appropriate to the displayed slot or options.",
        "failure_action": "Expand the scoring policy or replace the task; retain every change as append-only provenance.",
    },
    {
        "gate": "kc_measurement_purity",
        "requirement": "Success supplies defensible evidence about the declared active KCs without a major undeclared operation or obvious shortcut.",
        "failure_action": "Redesign the item or explicitly revise the successor measurement/KC declaration before learner simulation.",
    },
    {
        "gate": "crossed_measurement_design",
        "requirement": "KCs are crossed with formats and semantic families so no KC is wholly confounded with one campaign or interface; report support, anchors, crossings, nesting, and rank separately.",
        "failure_action": "Add diagnostically distinct families or retain the bank as a bounded pilot rather than a release.",
    },
    {
        "gate": "independent_revalidation",
        "requirement": "Every corrected or newly rendered item passes deterministic checks and independent role-specific validation; critic disagreement remains visible.",
        "failure_action": "Escalate unresolved major concerns and all cross-audit category changes to targeted review.",
    },
    {
        "gate": "claim_boundary",
        "requirement": "Automated audits may support stress-test and triage claims only; deployability, learner comprehension, and proficiency appropriateness require rendered human/expert evidence.",
        "failure_action": "Use 'platform-oriented' or 'automatically audited', not 'platform-validated' or 'learner-validated'.",
    },
)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError(f"expected JSON objects in {path}")
    return rows


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def relpath(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


def indexed(rows: Iterable[Mapping[str, Any]], label: str) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for raw in rows:
        row = dict(raw)
        item_id = str(row.get("item_id", ""))
        if not item_id:
            raise ValueError(f"{label} contains a row without item_id")
        if item_id in output:
            raise ValueError(f"duplicate {label} item_id: {item_id}")
        output[item_id] = row
    return output


def count_block(values: Iterable[str], order: Sequence[str]) -> dict[str, Any]:
    counter = Counter(values)
    total = sum(counter.values())
    return {
        key: {
            "count": counter.get(key, 0),
            "fraction": round(counter.get(key, 0) / total, 9) if total else 0.0,
        }
        for key in order
    }


def item_group(item_ids: Iterable[str], total: int) -> dict[str, Any]:
    ordered = sorted(item_ids)
    return {
        "count": len(ordered),
        "fraction": round(len(ordered) / total, 9) if total else 0.0,
        "item_ids": ordered,
    }


def validate_inputs(
    strict_rows: Sequence[Mapping[str, Any]],
    strict_summary: Mapping[str, Any],
    live_rows: Sequence[Mapping[str, Any]],
    live_judgments: Sequence[Mapping[str, Any]],
    live_summary: Mapping[str, Any],
    live_plan: Mapping[str, Any],
    item_rows: Sequence[Mapping[str, Any]],
    dataset_manifest: Mapping[str, Any],
) -> tuple[
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[tuple[str, str], dict[str, Any]],
]:
    strict = indexed(strict_rows, "strict audit")
    live = indexed(live_rows, "live audit")
    items = indexed(item_rows, "frozen item bank")
    if set(strict) != set(live) or set(strict) != set(items):
        raise ValueError(
            "strict/live/frozen item IDs differ: "
            f"strict_only={sorted(set(strict) - set(live))}, "
            f"live_only={sorted(set(live) - set(strict))}, "
            f"not_in_frozen={sorted((set(strict) | set(live)) - set(items))}"
        )
    if len(strict) != 113:
        raise ValueError(f"expected 113 full-v1 items, observed {len(strict)}")

    expected_item_hash = dataset_manifest["artifact_inventory"][
        "items/items.jsonl"
    ]["sha256"]
    if strict_summary["scope"]["items_reviewed"] != 113:
        raise ValueError("strict summary item count changed")
    if live_summary["scale"] != {"items": 113, "roles": 4, "judgments": 452}:
        raise ValueError("live summary scale changed")
    if live_plan["items"] != 113 or tuple(live_plan["roles"]) != LIVE_ROLES:
        raise ValueError("live plan coverage or role order changed")
    if live_plan["human_or_expert_gold"] is not False:
        raise ValueError("live plan evidence boundary changed")
    if strict_summary["scope"]["human_or_learner_evidence"] is not False:
        raise ValueError("strict audit evidence boundary changed")

    strict_counts = Counter()
    live_counts = Counter()
    for item_id in sorted(strict):
        strict_row = strict[item_id]
        live_row = live[item_id]
        frozen = items[item_id]
        if strict_row["prompt"] != frozen["prompt"]:
            raise ValueError(f"strict prompt differs from full-v1: {item_id}")
        if strict_row["target_answer"] != frozen["target_answer"]:
            raise ValueError(f"strict target differs from full-v1: {item_id}")
        if strict_row["accepted_answers"] != frozen["accepted_answers"]:
            raise ValueError(f"strict accepted answers differ from full-v1: {item_id}")
        strict_label = strict_row["audit"]["primary_disposition"]
        live_label = live_row["disposition"]
        if strict_label not in STRICT_TO_CANONICAL:
            raise ValueError(f"unknown strict disposition: {strict_label}")
        if live_label not in LIVE_TO_CANONICAL:
            raise ValueError(f"unknown live disposition: {live_label}")
        strict_counts[strict_label] += 1
        live_counts[live_label] += 1
        dispositions = live_row["disposition_by_role"]
        if set(dispositions) != set(LIVE_ROLES):
            raise ValueError(f"live role dispositions changed for {item_id}")
        expected_disagreement = len(set(dispositions.values())) > 1
        if bool(live_row["disposition_disagreement"]) != expected_disagreement:
            raise ValueError(f"live disagreement flag mismatch for {item_id}")

    expected_strict_counts = {
        key: int(value)
        for key, value in strict_summary["categorical_results"][
            "primary_disposition"
        ].items()
    }
    if dict(strict_counts) != expected_strict_counts:
        raise ValueError("strict summary dispositions disagree with item ledger")
    expected_live_counts = {
        key: int(value["count"])
        for key, value in live_summary["aggregate_dispositions"].items()
    }
    if dict(live_counts) != expected_live_counts:
        raise ValueError("live summary dispositions disagree with item aggregates")

    judgments: dict[tuple[str, str], dict[str, Any]] = {}
    for raw in live_judgments:
        row = dict(raw)
        key = (str(row.get("item_id", "")), str(row.get("role", "")))
        if key in judgments:
            raise ValueError(f"duplicate live judgment: {key}")
        if key[0] not in live or key[1] not in LIVE_ROLES:
            raise ValueError(f"unexpected live judgment key: {key}")
        if row["disposition"] != live[key[0]]["disposition_by_role"][key[1]]:
            raise ValueError(f"live judgment/aggregate mismatch: {key}")
        judgments[key] = row
    expected_keys = {(item_id, role) for item_id in live for role in LIVE_ROLES}
    if set(judgments) != expected_keys:
        raise ValueError("live role judgment coverage changed")

    # The caller verifies the actual file digest because it owns the input path.
    if len(expected_item_hash) != 64:
        raise ValueError("full-v1 manifest item digest is malformed")
    return strict, live, items, judgments


def analyze(
    strict: Mapping[str, Mapping[str, Any]],
    live: Mapping[str, Mapping[str, Any]],
    judgments: Mapping[tuple[str, str], Mapping[str, Any]],
    *,
    inputs: Mapping[str, Any],
) -> dict[str, Any]:
    item_ids = sorted(strict)
    total = len(item_ids)
    confusion_counts = {
        strict_category: {live_category: 0 for live_category in CATEGORIES}
        for strict_category in CATEGORIES
    }
    confusion_ids = {
        strict_category: {live_category: [] for live_category in CATEGORIES}
        for strict_category in CATEGORIES
    }
    item_level: list[dict[str, Any]] = []
    strict_disagreement_ids: list[str] = []
    live_disagreement_ids: list[str] = []
    exact_ids: list[str] = []
    strict_more_ids: list[str] = []
    live_more_ids: list[str] = []
    delta_ids: dict[int, list[str]] = {delta: [] for delta in range(-4, 5)}
    threshold_groups: dict[str, list[str]] = {
        "both_usable": [],
        "strict_only_requires_action": [],
        "live_only_requires_action": [],
        "both_require_action": [],
    }
    critical_groups: dict[str, list[str]] = {
        "both_critical": [],
        "strict_only_critical": [],
        "live_only_critical": [],
        "neither_critical": [],
    }
    role_comparisons: dict[str, dict[str, list[str]]] = {
        role: {"exact": [], "strict_more": [], "live_role_more": []}
        for role in LIVE_ROLES
    }
    role_counts: dict[str, Counter[str]] = {role: Counter() for role in LIVE_ROLES}
    distinct_live_role_count = Counter()
    live_aggregate_usable_with_disagreement: list[str] = []

    for item_id in item_ids:
        strict_row = strict[item_id]
        live_row = live[item_id]
        strict_raw = str(strict_row["audit"]["primary_disposition"])
        live_raw = str(live_row["disposition"])
        strict_category = STRICT_TO_CANONICAL[strict_raw]
        live_category = LIVE_TO_CANONICAL[live_raw]
        strict_rank = CANONICAL_RANK[strict_category]
        live_rank = CANONICAL_RANK[live_category]
        delta = strict_rank - live_rank
        confusion_counts[strict_category][live_category] += 1
        confusion_ids[strict_category][live_category].append(item_id)
        delta_ids[delta].append(item_id)
        if delta > 0:
            strict_more_ids.append(item_id)
        elif delta < 0:
            live_more_ids.append(item_id)
        else:
            exact_ids.append(item_id)

        strict_usable = strict_category == "usable"
        live_usable = live_category == "usable"
        if strict_usable and live_usable:
            threshold_groups["both_usable"].append(item_id)
        elif not strict_usable and live_usable:
            threshold_groups["strict_only_requires_action"].append(item_id)
        elif strict_usable and not live_usable:
            threshold_groups["live_only_requires_action"].append(item_id)
        else:
            threshold_groups["both_require_action"].append(item_id)

        strict_critical = strict_category in {"answer_space", "withhold"}
        live_critical = live_category in {"answer_space", "withhold"}
        if strict_critical and live_critical:
            critical_groups["both_critical"].append(item_id)
        elif strict_critical:
            critical_groups["strict_only_critical"].append(item_id)
        elif live_critical:
            critical_groups["live_only_critical"].append(item_id)
        else:
            critical_groups["neither_critical"].append(item_id)

        strict_disagreement = bool(strict_row["audit"]["role_disagreement"])
        live_disagreement = bool(live_row["disposition_disagreement"])
        if strict_disagreement:
            strict_disagreement_ids.append(item_id)
        if live_disagreement:
            live_disagreement_ids.append(item_id)
        if live_category == "usable" and live_disagreement:
            live_aggregate_usable_with_disagreement.append(item_id)

        role_canonical: dict[str, str] = {}
        for role in LIVE_ROLES:
            raw_role_disposition = str(live_row["disposition_by_role"][role])
            role_category = LIVE_TO_CANONICAL[raw_role_disposition]
            role_canonical[role] = role_category
            role_counts[role][role_category] += 1
            role_delta = strict_rank - CANONICAL_RANK[role_category]
            if role_delta > 0:
                role_comparisons[role]["strict_more"].append(item_id)
            elif role_delta < 0:
                role_comparisons[role]["live_role_more"].append(item_id)
            else:
                role_comparisons[role]["exact"].append(item_id)
        distinct_live_role_count[len(set(role_canonical.values()))] += 1

        item_level.append(
            {
                "item_id": item_id,
                "strict_raw": strict_raw,
                "live_raw": live_raw,
                "strict_canonical": strict_category,
                "live_canonical": live_category,
                "exact_mapped_agreement": strict_category == live_category,
                "operational_severity_delta_strict_minus_live": delta,
                "strict_role_perspective_disagreement": strict_disagreement,
                "live_independent_role_disagreement": live_disagreement,
                "live_role_canonical_dispositions": role_canonical,
            }
        )

    strict_marginal = count_block(
        (STRICT_TO_CANONICAL[strict[item_id]["audit"]["primary_disposition"]] for item_id in item_ids),
        CATEGORIES,
    )
    live_marginal = count_block(
        (LIVE_TO_CANONICAL[live[item_id]["disposition"]] for item_id in item_ids),
        CATEGORIES,
    )

    strict_set = set(strict_disagreement_ids)
    live_set = set(live_disagreement_ids)
    disagreement_overlap = {
        "both": item_group(strict_set & live_set, total),
        "strict_only": item_group(strict_set - live_set, total),
        "live_only": item_group(live_set - strict_set, total),
        "neither": item_group(set(item_ids) - (strict_set | live_set), total),
    }

    role_comparison_output = {
        role: {
            key: item_group(values, total)
            for key, values in role_comparisons[role].items()
        }
        for role in LIVE_ROLES
    }
    role_marginals = {
        role: {
            category: {
                "count": role_counts[role].get(category, 0),
                "fraction": round(role_counts[role].get(category, 0) / total, 9),
            }
            for category in CATEGORIES
        }
        for role in LIVE_ROLES
    }

    representatives = []
    for panel, item_id in REPRESENTATIVE_ITEMS:
        if item_id not in strict or item_id not in live:
            raise ValueError(f"missing declared representative item: {item_id}")
        strict_row = strict[item_id]
        live_row = live[item_id]
        representatives.append(
            {
                "panel": panel,
                "item_id": item_id,
                "cell_id": strict_row["cell_id"],
                "generator_kc_ids": list(strict_row["generator_kc_ids"]),
                "prompt": strict_row["prompt"],
                "target_answer": strict_row["target_answer"],
                "accepted_answers": list(strict_row["accepted_answers"]),
                "strict": {
                    "raw_disposition": strict_row["audit"]["primary_disposition"],
                    "canonical_disposition": STRICT_TO_CANONICAL[
                        strict_row["audit"]["primary_disposition"]
                    ],
                    "learner_note": strict_row["audit"]["learner_note"],
                    "platform_note": strict_row["audit"]["platform_note"],
                    "issue_tags": list(strict_row["audit"]["issue_tags"]),
                },
                "live": {
                    "raw_disposition": live_row["disposition"],
                    "canonical_disposition": LIVE_TO_CANONICAL[
                        live_row["disposition"]
                    ],
                    "disposition_by_role": dict(live_row["disposition_by_role"]),
                    "primary_concern_by_role": dict(
                        live_row["primary_concern_by_role"]
                    ),
                },
            }
        )

    return {
        "analysis_id": "full_v1_platform_audit_cross_synthesis_v1",
        "status": "DETERMINISTIC_CROSS_AUDIT_SYNTHESIS_COMPLETE",
        "evidence_boundary": {
            "strict_audit": "single-Codex role-separated census; learner/platform disagreement is within one review, not independent inter-rater disagreement",
            "live_audit": "four independent Codex role prompts with preregistered plurality aggregation",
            "human_or_expert_gold": False,
            "interpretation": "automated qualitative stress tests and triage; no percentage estimates real learner comprehension, expert validity, or platform deployability",
            "learner_outcomes_read": False,
            "private_oracle_trajectories_read": False,
            "full_v1_mutated": False,
        },
        "inputs": dict(inputs),
        "category_mapping": [dict(row) for row in CATEGORY_MAPPING],
        "coverage": {
            "strict_items": total,
            "live_items": total,
            "common_items": total,
            "live_roles": list(LIVE_ROLES),
            "live_judgments": total * len(LIVE_ROLES),
        },
        "marginals": {
            "strict_canonical": strict_marginal,
            "live_canonical": live_marginal,
        },
        "agreement": {
            "exact_mapped_category": item_group(exact_ids, total),
            "different_mapped_category": item_group(
                set(item_ids) - set(exact_ids), total
            ),
            "confusion_counts_rows_strict_columns_live": confusion_counts,
            "confusion_item_ids_rows_strict_columns_live": confusion_ids,
            "action_threshold": {
                key: item_group(values, total)
                for key, values in threshold_groups.items()
            },
            "critical_redesign_threshold": {
                "definition": "canonical answer_space or withhold",
                "either_critical": item_group(
                    set(critical_groups["both_critical"])
                    | set(critical_groups["strict_only_critical"])
                    | set(critical_groups["live_only_critical"]),
                    total,
                ),
                **{
                    key: item_group(values, total)
                    for key, values in critical_groups.items()
                },
            },
        },
        "operational_strictness": {
            "definition": "Canonical ranks reproduce the live audit's declared least-to-most-severe plurality tie-break order. Artificial and answer-space failures remain qualitatively distinct; the delta is a triage diagnostic, not a psychometric scale.",
            "strict_more_severe": item_group(strict_more_ids, total),
            "same_rank_and_category": item_group(exact_ids, total),
            "live_more_severe": item_group(live_more_ids, total),
            "strict_minus_live_rank_delta": {
                str(delta): item_group(delta_ids[delta], total)
                for delta in range(-4, 5)
            },
        },
        "role_disagreement": {
            "strict_role_perspectives": {
                "definition": "learner_overall differs from platform_overall inside one Codex review",
                **item_group(strict_disagreement_ids, total),
            },
            "live_independent_roles": {
                "definition": "at least two of learner, teacher, platform_product, and measurement chose different dispositions",
                **item_group(live_disagreement_ids, total),
                "distinct_canonical_disposition_count": {
                    str(key): value
                    for key, value in sorted(distinct_live_role_count.items())
                },
                "aggregate_usable_despite_role_disagreement": item_group(
                    live_aggregate_usable_with_disagreement, total
                ),
            },
            "overlap": disagreement_overlap,
            "live_role_marginals": role_marginals,
            "strict_vs_each_live_role": role_comparison_output,
        },
        "representative_items": representatives,
        "extension_hard_gates": [dict(row) for row in HARD_GATES],
        "item_level": item_level,
    }


def percent(block: Mapping[str, Any]) -> str:
    return f"{100 * float(block['fraction']):.1f}%"


def category_label(category: str) -> str:
    return category.replace("_", " ")


def render_report(result: Mapping[str, Any]) -> str:
    marginals = result["marginals"]
    agreement = result["agreement"]
    operational = result["operational_strictness"]
    disagreement = result["role_disagreement"]
    lines: list[str] = [
        "# Platform plausibility audit of the frozen full-v1 item bank",
        "",
        "Status: final deterministic cross-audit synthesis  ",
        "Dataset: `data/grammar_kt_full_v1/`  ",
        "Scope: all 113 fixed items, all 75 GrammarCells, all 18 generator KCs  ",
        "Mutation policy: full-v1 was read only and remains unchanged",
        "",
        "## Finding in one paragraph",
        "",
        (
            "Two separately constructed automated audits agree that full-v1 is a "
            "useful clean Q-driven control bank but do not establish a platform-validated "
            "measurement bank. After an explicit five-category mapping, they assign the "
            f"same category to {agreement['exact_mapped_category']['count']}/113 items "
            f"({percent(agreement['exact_mapped_category'])}). Both call "
            f"{agreement['action_threshold']['both_usable']['count']} items usable under "
            "their stated UI/scoring assumptions; the stricter census alone requests "
            f"action on {agreement['action_threshold']['strict_only_requires_action']['count']}, "
            "the four-role live audit alone requests action on "
            f"{agreement['action_threshold']['live_only_requires_action']['count']}, and "
            f"both request action on {agreement['action_threshold']['both_require_action']['count']}. "
            "The cross-audit differences and substantial role disagreement are evidence "
            "against one opaque realism score: every non-usable item and every disputed "
            "item should remain visible during extension design."
        ),
        "",
        "These counts are automated stress-test results, not estimates of how real "
        "learners, teachers, or platform teams would judge the items.",
        "",
        "## What the two audits are",
        "",
        "The **strict census** is the all-item ledger in "
        "`experiments/measurement_realism/audits/item_audit/`. One Codex review "
        "applied separate learner and platform perspectives under an explicit rubric. "
        "Its 19 perspective disagreements are useful, but they are not independent "
        "inter-rater disagreements.",
        "",
        "The **live four-role audit** is the preregistered evidence in "
        "`experiments/measurement_realism/audits/full_v1_items_v2/`. Four independent "
        "critic roles—learner, teacher, platform-product, and measurement—judged each "
        "item without seeing one another's outputs across 16 audited batch calls. Its "
        "aggregate uses plurality plus "
        "the frozen tie-break rule. The 452 role judgments, rendered prompts, raw "
        "outputs, parsed outputs, settings, and hashes are retained.",
        "",
        "Neither audit read learner outcomes or private learner trajectories. The "
        "learner-role critic did not see GrammarCell/KC oracle annotations. The other "
        "live roles did, because their task included measurement critique. Neither "
        "audit is human or expert gold.",
        "",
        "## Explicit five-category mapping",
        "",
        "The source labels differ, so agreement is computed only after this declared "
        "mapping. The operational rank reproduces the live audit's least-to-most-severe "
        "tie-break order; it is not a psychometric scale.",
        "",
        "| Canonical category | Strict census label | Live four-role label | Rank | Meaning |",
        "|---|---|---|---:|---|",
    ]
    for row in result["category_mapping"]:
        lines.append(
            f"| `{row['canonical']}` | `{row['strict']}` | `{row['live']}` | "
            f"{row['operational_severity_rank']} | {row['meaning']} |"
        )

    lines.extend(
        [
            "",
            "`artificial` and `answer_space` name different failure mechanisms even "
            "though the declared tie-break places one before the other. Exact-category "
            "agreement and the usable/action threshold are therefore more interpretable "
            "than treating the five categories as equal numerical intervals.",
            "",
            "## Marginal results",
            "",
            "| Canonical category | Strict census | Live four-role aggregate |",
            "|---|---:|---:|",
        ]
    )
    for category in CATEGORIES:
        strict_block = marginals["strict_canonical"][category]
        live_block = marginals["live_canonical"][category]
        lines.append(
            f"| `{category}` | {strict_block['count']} ({percent(strict_block)}) | "
            f"{live_block['count']} ({percent(live_block)}) |"
        )

    lines.extend(
        [
            "",
            "The strict census is more intervention-sensitive in aggregate: it marks "
            f"{marginals['strict_canonical']['usable']['count']} usable, versus "
            f"{marginals['live_canonical']['usable']['count']} in the live plurality. "
            "That does not make it ground truth. The live plurality can also hide a "
            "minority critic's material concern.",
            "",
            "## Exact cross-audit confusion",
            "",
            "Rows are strict-census categories and columns are live-aggregate categories.",
            "",
            "| Strict \\ Live | usable | local change | artificial | answer space | withhold | Row total |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    confusion = agreement["confusion_counts_rows_strict_columns_live"]
    for strict_category in CATEGORIES:
        row_values = [confusion[strict_category][category] for category in CATEGORIES]
        lines.append(
            f"| {category_label(strict_category)} | "
            + " | ".join(str(value) for value in row_values)
            + f" | {sum(row_values)} |"
        )
    column_totals = [sum(confusion[row][col] for row in CATEGORIES) for col in CATEGORIES]
    lines.append(
        "| Column total | "
        + " | ".join(str(value) for value in column_totals)
        + f" | {sum(column_totals)} |"
    )
    lines.extend(
        [
            "",
            f"Exact mapped agreement is {agreement['exact_mapped_category']['count']}/113 "
            f"({percent(agreement['exact_mapped_category'])}); "
            f"{agreement['different_mapped_category']['count']} items move category. "
            "All cell-level item-ID lists are stored in "
            "`platform_audit_synthesis.json`, so no confusion cell is represented only "
            "by an aggregate count.",
            "",
            "At the simpler action threshold:",
            "",
            "| Cross-audit action status | Items | Percent |",
            "|---|---:|---:|",
        ]
    )
    for key in (
        "both_usable",
        "strict_only_requires_action",
        "live_only_requires_action",
        "both_require_action",
    ):
        block = agreement["action_threshold"][key]
        lines.append(f"| {category_label(key)} | {block['count']} | {percent(block)} |")

    lines.extend(
        [
            "",
            "The intersection of 60 usable judgments is a conservative positive-control "
            "pool, not a validated deployable subset. The union of concerns contains 53 "
            "items and is the appropriate review queue for a wording-dependent extension.",
            "",
            "## Stricter-versus-live differences",
            "",
            f"Using only the declared operational tie-break order, the strict census is "
            f"more severe for {operational['strict_more_severe']['count']} items "
            f"({percent(operational['strict_more_severe'])}), the mapped category is the "
            f"same for {operational['same_rank_and_category']['count']} "
            f"({percent(operational['same_rank_and_category'])}), and the live aggregate "
            f"is more severe for {operational['live_more_severe']['count']} "
            f"({percent(operational['live_more_severe'])}). This is audit-process "
            "sensitivity, not accuracy against gold.",
            "",
            "Important asymmetries include:",
            "",
            "- twelve strict `artificial` items become live `local_change`; these are mostly intervention prompts whose constraints could plausibly move into UI;",
            "- six strict `answer_space` items become live `usable`, showing that plurality can miss an alternative-response concern;",
            "- two strict `withhold` items become live `usable`, including the reported-speech/Q-purity example below; and",
            "- four strict `usable` items become live `answer_space`, so the stricter census is not uniformly more severe item by item.",
            "",
            "Exact IDs and every rank delta from -4 through +4 are retained in the JSON "
            "artifact. Because category mechanisms differ, extension curation should read "
            "the rationales, not sort mechanically by delta.",
            "",
            "## Role disagreement is evidence, not noise to average away",
            "",
            f"The strict census records {disagreement['strict_role_perspectives']['count']}/113 "
            f"({percent(disagreement['strict_role_perspectives'])}) learner/platform-"
            "perspective differences within one review. The live audit records "
            f"{disagreement['live_independent_roles']['count']}/113 "
            f"({percent(disagreement['live_independent_roles'])}) items with at least two "
            "different role dispositions. These disagreement notions are deliberately not "
            "treated as interchangeable reliability coefficients.",
            "",
            "| Live role | usable | local change | artificial | answer space | withhold |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for role in LIVE_ROLES:
        role_marginal = disagreement["live_role_marginals"][role]
        lines.append(
            f"| `{role}` | "
            + " | ".join(str(role_marginal[category]["count"]) for category in CATEGORIES)
            + " |"
        )
    overlap = disagreement["overlap"]
    lines.extend(
        [
            "",
            f"The two disagreement flags overlap on {overlap['both']['count']} items; "
            f"{overlap['strict_only']['count']} are strict-only, "
            f"{overlap['live_only']['count']} live-only, and "
            f"{overlap['neither']['count']} show neither form. The live aggregate calls "
            f"{disagreement['live_independent_roles']['aggregate_usable_despite_role_disagreement']['count']} "
            "items usable even though at least one independent role chose another "
            "disposition. Aggregate usability must therefore never erase role records.",
            "",
            "## Representative exact learner-facing items",
            "",
            "These examples quote the frozen prompt, target, accepted spans, and audit "
            "records. They are not reconstructed paraphrases.",
        ]
    )
    for item in result["representative_items"]:
        lines.extend(
            [
                "",
                f"### `{item['panel']}` — `{item['item_id']}`",
                "",
                f"> {item['prompt']}",
                "",
                f"Target: `{item['target_answer']}`  ",
                "Accepted response span(s): "
                + ", ".join(f"`{answer}`" for answer in item["accepted_answers"])
                + "  ",
                "Active generator KCs: "
                + ", ".join(f"`{kc}`" for kc in item["generator_kc_ids"]),
                "",
                f"Strict census: `{item['strict']['raw_disposition']}`. "
                f"{item['strict']['learner_note']} {item['strict']['platform_note']}",
                "",
                f"Live aggregate: `{item['live']['raw_disposition']}`. Role dispositions: "
                + "; ".join(
                    f"{role}=`{item['live']['disposition_by_role'][role]}`"
                    for role in LIVE_ROLES
                )
                + ".",
            ]
        )
        live_concerns = [
            f"{role}: {item['live']['primary_concern_by_role'][role]}"
            for role in LIVE_ROLES
            if item["live"]["primary_concern_by_role"][role] != "none"
        ]
        if live_concerns:
            lines.extend(["", "Live role concerns: " + " | ".join(live_concerns)])

    lines.extend(
        [
            "",
            "## Actionable hard gates for the measurement extension",
            "",
            "These are gates, not dimensions to average into a realism score.",
            "",
            "| Gate | Requirement | Failure action |",
            "|---|---|---|",
        ]
    )
    for gate in result["extension_hard_gates"]:
        lines.append(
            f"| `{gate['gate']}` | {gate['requirement']} | {gate['failure_action']} |"
        )
    lines.extend(
        [
            "",
            "Operationally, the extension should begin with the 60-item shared-usable "
            "pool as positive controls and the 53-item union-of-concerns queue as "
            "mandatory review—not silently discard one audit. All "
            f"{agreement['critical_redesign_threshold']['either_critical']['count']} items flagged at "
            "the union of the two audits' critical `answer_space`/`withhold` threshold "
            "must be rewritten or explicitly adjudicated before wording-dependent "
            "simulation. Artificial prompts should be re-expressed through an actual "
            "response component (for example tiles) rather than longer instructions.",
            "",
            "For matched-format families, every retained format must independently pass "
            "the first five gates. Full Q rank, item count, or aggregate critic plurality "
            "cannot rescue a failed task, scorer, or measurement claim.",
            "",
            "## What the audit supports",
            "",
            "The defensible description of full-v1 remains:",
            "",
            "> a frozen clean-control grammar-KT benchmark with an auditable intended",
            "> item surface and automated platform-plausibility stress tests.",
            "",
            "It is not yet defensible to call full-v1 a platform-validated item bank, a "
            "learner-validated assessment, or a realistic simulation of linguistic "
            "production. Prompt strings do not cause full-v1 responses after Q is fixed; "
            "the baseline has no rendered UI, executable scorer, intended proficiency "
            "field, surface learner response, item difficulty, or platform-like assignment "
            "policy.",
            "",
            "## Reproduction and integrity",
            "",
            "Run:",
            "",
            "```bash",
            ".venv/bin/python scripts/experiments/analyze_platform_audits.py",
            "```",
            "",
            "The script validates a one-to-one 113-item match across the strict ledger, "
            "live aggregates, 452 role judgments, and frozen item bank; validates the "
            "stored prompts/targets/accepted spans; reconciles both source summaries; and "
            "regenerates:",
            "",
            "- `experiments/measurement_realism/audits/platform_audit_synthesis.json`; and",
            "- `reports/platform_plausibility_audit.md`.",
            "",
            "The JSON records SHA-256 hashes for every input and exact item IDs for every "
            "confusion, threshold, severity-delta, and disagreement cell. It also retains "
            "all 113 item-level mapped outcomes. The final report is generated from the "
            "same in-memory analysis, so its aggregate values are not hand-copied.",
            "",
            "## Limitations",
            "",
            "- Both audits are automated Codex judgments, not real learner responses, qualified teacher ratings, platform review, or psychometric validation.",
            "- The strict audit is one role-separated review; its role disagreement is not inter-rater disagreement.",
            "- The live roles are independent calls but use one model family and one frozen prompting design; plurality is not truth.",
            "- The category mapping is declared and plausible but the source rubrics are not identical. Rank differences are triage diagnostics only.",
            "- No intended CEFR/proficiency field, rendered UI, executable scoring normalizer, or learner response corpus exists for full-v1.",
            "- Counts describe this exact 113-item bank and do not estimate prevalence for EGP, English-learning platforms, or human learners.",
            "- Human/expert validation remains required for deployability, response process, accessibility, fairness, and educational-use claims.",
            "",
        ]
    )
    return "\n".join(lines)


def input_record(path: Path, rows: int | None = None) -> dict[str, Any]:
    value: dict[str, Any] = {
        "path": relpath(path),
        "sha256": file_sha256(path),
        "bytes": path.stat().st_size,
    }
    if rows is not None:
        value["rows"] = rows
    return value


def write_outputs(result: Mapping[str, Any], json_output: Path, report_output: Path) -> None:
    json_payload = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    report_payload = render_report(result)
    json_output.parent.mkdir(parents=True, exist_ok=True)
    report_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(json_payload, encoding="utf-8")
    report_output.write_text(report_payload, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict-ledger", type=Path, default=DEFAULT_STRICT_LEDGER)
    parser.add_argument("--strict-summary", type=Path, default=DEFAULT_STRICT_SUMMARY)
    parser.add_argument("--live-aggregates", type=Path, default=DEFAULT_LIVE_AGGREGATES)
    parser.add_argument("--live-judgments", type=Path, default=DEFAULT_LIVE_JUDGMENTS)
    parser.add_argument("--live-summary", type=Path, default=DEFAULT_LIVE_SUMMARY)
    parser.add_argument("--live-plan", type=Path, default=DEFAULT_LIVE_PLAN)
    parser.add_argument("--items", type=Path, default=DEFAULT_ITEMS)
    parser.add_argument("--dataset-manifest", type=Path, default=DEFAULT_DATASET_MANIFEST)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT_OUTPUT)
    args = parser.parse_args()

    strict_rows = read_jsonl(args.strict_ledger)
    strict_summary = read_json(args.strict_summary)
    live_rows = read_jsonl(args.live_aggregates)
    live_judgments = read_jsonl(args.live_judgments)
    live_summary = read_json(args.live_summary)
    live_plan = read_json(args.live_plan)
    item_rows = read_jsonl(args.items)
    dataset_manifest = read_json(args.dataset_manifest)
    if file_sha256(args.live_aggregates) != live_summary["item_aggregates_sha256"]:
        raise ValueError("live item aggregates differ from their retained summary hash")
    if file_sha256(args.live_judgments) != live_summary["judgments_sha256"]:
        raise ValueError("live judgments differ from their retained summary hash")
    strict, live, _items, judgments = validate_inputs(
        strict_rows,
        strict_summary,
        live_rows,
        live_judgments,
        live_summary,
        live_plan,
        item_rows,
        dataset_manifest,
    )
    expected_item_hash = dataset_manifest["artifact_inventory"]["items/items.jsonl"][
        "sha256"
    ]
    if file_sha256(args.items) != expected_item_hash:
        raise ValueError("full-v1 item bank differs from its frozen manifest")

    input_paths = {
        "strict_item_ledger": (args.strict_ledger, len(strict_rows)),
        "strict_summary": (args.strict_summary, None),
        "live_item_aggregates": (args.live_aggregates, len(live_rows)),
        "live_role_judgments": (args.live_judgments, len(live_judgments)),
        "live_summary": (args.live_summary, None),
        "live_study_plan": (args.live_plan, None),
        "frozen_items": (args.items, len(item_rows)),
        "frozen_dataset_manifest": (args.dataset_manifest, None),
        "analysis_script": (Path(__file__).resolve(), None),
    }
    inputs = {
        key: input_record(path, rows)
        for key, (path, rows) in sorted(input_paths.items())
    }
    result = analyze(strict, live, judgments, inputs=inputs)
    write_outputs(result, args.json_output, args.report_output)
    print(
        canonical_json(
            {
                "status": result["status"],
                "items": result["coverage"]["common_items"],
                "exact_agreement": result["agreement"]["exact_mapped_category"][
                    "count"
                ],
                "json_output": relpath(args.json_output),
                "report_output": relpath(args.report_output),
            }
        )
    )


if __name__ == "__main__":
    main()
