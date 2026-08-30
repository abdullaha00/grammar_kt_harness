#!/usr/bin/env python3
"""Analyze future ecological-precision continuum critic judgments.

Every ecology and measurement-precision dimension is reported separately.
This script deliberately emits no scalar realism score or weighted composite.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


PROTOCOL_ROOT = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[3]

CONCERN = {"pass": 0, "minor_concern": 1, "major_concern": 2}
DETERMINACY = {"determinate": 0, "bounded_multiple": 1, "materially_ambiguous": 2}
COVERAGE = {"complete": 0, "minor_gap": 1, "major_gap": 2}
LEXICAL = {"low": 0, "moderate": 1, "high": 2}
ATTRIBUTION = {"clear": 0, "partial": 1, "weak": 2, "not_attributable": 3}
INCIDENTAL_OPERATIONS = {
    "tense_selection",
    "aspect_selection",
    "voice_argument_structure",
    "negation",
    "auxiliary_selection",
    "do_support",
    "operator_inversion",
    "wh_fronting",
    "modal_semantics",
    "agreement",
    "participle_morphology",
    "progressive_morphology",
    "reported_speech",
    "pronoun_reference",
    "lexical_choice",
    "discourse_pragmatics",
    "other",
}
RATING_KEYS = (
    "task_comprehensibility",
    "context_naturalness",
    "interaction_naturalness",
    "platform_plausibility",
    "answer_determinacy",
    "accepted_response_coverage",
    "lexical_nuisance",
    "kc_attribution",
)
RATING_ALLOWED = {
    "task_comprehensibility": set(CONCERN) | {"not_applicable"},
    "context_naturalness": set(CONCERN) | {"not_applicable"},
    "interaction_naturalness": set(CONCERN) | {"not_applicable"},
    "platform_plausibility": set(CONCERN) | {"not_applicable"},
    "answer_determinacy": set(DETERMINACY) | {"not_applicable"},
    "accepted_response_coverage": set(COVERAGE) | {"not_applicable"},
    "lexical_nuisance": set(LEXICAL) | {"not_applicable"},
    "kc_attribution": set(ATTRIBUTION) | {"not_applicable"},
}
RISK_METRICS = {
    "context_naturalness_risk": ("rating", "context_naturalness", CONCERN),
    "interaction_naturalness_risk": ("rating", "interaction_naturalness", CONCERN),
    "platform_plausibility_risk": ("rating", "platform_plausibility", CONCERN),
    "determinacy_risk": ("rating", "answer_determinacy", DETERMINACY),
    "accepted_response_coverage_risk": (
        "rating",
        "accepted_response_coverage",
        COVERAGE,
    ),
    "lexical_nuisance_risk": ("rating", "lexical_nuisance", LEXICAL),
    "kc_attribution_risk": ("rating", "kc_attribution", ATTRIBUTION),
    "plausible_response_lower_bound": ("numeric", "plausible_response_lower_bound", None),
    "incidental_grammar_count": ("incidental_count", "incidental_grammar_operations", None),
    "target_avoiding_shortcut": ("boolean", "target_avoiding_shortcut", None),
}


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
        raise ValueError(f"expected JSON objects: {path}")
    return rows


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def relative(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


def distribution(values: Iterable[Any]) -> dict[str, int]:
    return {str(key): value for key, value in sorted(Counter(values).items())}


def numeric_summary(values: Iterable[float]) -> dict[str, Any]:
    data = [float(value) for value in values]
    if not data:
        return {"count": 0, "min": None, "max": None, "mean": None, "median": None}
    return {
        "count": len(data),
        "min": min(data),
        "max": max(data),
        "mean": round(statistics.fmean(data), 9),
        "median": round(statistics.median(data), 9),
    }


def metric_value(row: Mapping[str, Any], metric: str) -> float | None:
    kind, field, mapping = RISK_METRICS[metric]
    if kind == "rating":
        raw = row["ratings"][field]
        if raw == "not_applicable":
            return None
        assert mapping is not None
        return float(mapping[raw])
    if kind == "numeric":
        value = row[field]
        return None if value is None else float(value)
    if kind == "incidental_count":
        return float(len(row[field]))
    if kind == "boolean":
        value = row[field]
        return None if value is None else float(bool(value))
    raise AssertionError(kind)


def summarize_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    opportunity_ids = sorted({str(row["opportunity_id"]) for row in rows})
    operation_counts = Counter(
        operation for row in rows for operation in row["incidental_grammar_operations"]
    )
    applicable_shortcuts = [
        bool(row["target_avoiding_shortcut"])
        for row in rows
        if row["target_avoiding_shortcut"] is not None
    ]
    return {
        "opportunities": len(opportunity_ids),
        "opportunity_ids": opportunity_ids,
        "judgments": len(rows),
        "rating_distributions": {
            key: distribution(row["ratings"][key] for row in rows)
            for key in RATING_KEYS
        },
        "plausible_response_lower_bound": numeric_summary(
            row["plausible_response_lower_bound"]
            for row in rows
            if row["plausible_response_lower_bound"] is not None
        ),
        "incidental_grammar": {
            "count_per_judgment": numeric_summary(
                len(row["incidental_grammar_operations"]) for row in rows
            ),
            "judgments_with_any": sum(
                bool(row["incidental_grammar_operations"]) for row in rows
            ),
            "operation_counts": dict(sorted(operation_counts.items())),
        },
        "target_avoiding_shortcut": {
            "applicable_judgments": len(applicable_shortcuts),
            "true": sum(applicable_shortcuts),
            "false": len(applicable_shortcuts) - sum(applicable_shortcuts),
            "rate": (
                round(sum(applicable_shortcuts) / len(applicable_shortcuts), 9)
                if applicable_shortcuts
                else None
            ),
        },
    }


def validate(
    plan: Mapping[str, Any],
    judgments: Sequence[Mapping[str, Any]],
    *,
    allow_incomplete: bool,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    formats = list(plan["format_order"])
    roles = list(plan["critic_roles"])
    if formats != [
        "constrained_cloze",
        "sentence_transformation",
        "contextual_production",
        "dialogue_completion",
        "open_dialogue",
    ]:
        raise ValueError("format order changed")
    opportunities: dict[str, dict[str, Any]] = {}
    for cell in plan["selected_cells"]:
        for slot in cell["opportunity_slots"]:
            opportunity_id = str(slot["opportunity_id"])
            if opportunity_id in opportunities:
                raise ValueError(f"duplicate planned opportunity: {opportunity_id}")
            opportunities[opportunity_id] = {
                "family_id": cell["family_id"],
                "pilot_stratum": cell["pilot_stratum"],
                "format": slot["format"],
                "cell_id": cell["cell_id"],
            }
    if len(opportunities) != 20:
        raise ValueError("pilot plan must contain 20 opportunities")

    exact_fields = {
        "judgment_schema",
        "critic_id",
        "critic_role",
        "family_id",
        "opportunity_id",
        "format",
        "ratings",
        "plausible_response_lower_bound",
        "incidental_grammar_operations",
        "target_avoiding_shortcut",
        "primary_concern",
    }
    observed_keys: set[tuple[str, str]] = set()
    clean: list[dict[str, Any]] = []
    for raw in judgments:
        row = dict(raw)
        if set(row) != exact_fields:
            raise ValueError(f"critic fields changed for {row.get('opportunity_id')}")
        if row["judgment_schema"] != "dialogue_continuum_critic_v1":
            raise ValueError("critic judgment schema changed")
        opportunity_id = str(row["opportunity_id"])
        role = str(row["critic_role"])
        if opportunity_id not in opportunities:
            raise ValueError(f"unknown opportunity: {opportunity_id}")
        if role not in roles:
            raise ValueError(f"unknown critic role: {role}")
        key = (opportunity_id, role)
        if key in observed_keys:
            raise ValueError(f"duplicate opportunity/role judgment: {key}")
        observed_keys.add(key)
        planned = opportunities[opportunity_id]
        if row["family_id"] != planned["family_id"] or row["format"] != planned["format"]:
            raise ValueError(f"judgment/plan identity mismatch: {opportunity_id}")
        if set(row["ratings"]) != set(RATING_KEYS):
            raise ValueError(f"rating dimensions changed: {opportunity_id}/{role}")
        for rating, allowed in RATING_ALLOWED.items():
            if row["ratings"][rating] not in allowed:
                raise ValueError(f"unknown {rating}: {opportunity_id}/{role}")
        lower_bound = row["plausible_response_lower_bound"]
        if lower_bound is not None and (
            not isinstance(lower_bound, int)
            or isinstance(lower_bound, bool)
            or lower_bound < 1
        ):
            raise ValueError(f"invalid response lower bound: {opportunity_id}/{role}")
        operations = row["incidental_grammar_operations"]
        if not isinstance(operations, list) or len(operations) != len(set(operations)):
            raise ValueError(f"incidental operations must be a unique list: {key}")
        if set(operations) - INCIDENTAL_OPERATIONS:
            raise ValueError(f"unknown incidental operation: {key}")
        shortcut = row["target_avoiding_shortcut"]
        if shortcut is not None and not isinstance(shortcut, bool):
            raise ValueError(f"invalid shortcut flag: {key}")
        if not isinstance(row["primary_concern"], str) or not row["primary_concern"].strip():
            raise ValueError(f"missing primary concern: {key}")
        row["pilot_stratum"] = planned["pilot_stratum"]
        row["cell_id"] = planned["cell_id"]
        clean.append(row)

    expected_keys = {(opportunity_id, role) for opportunity_id in opportunities for role in roles}
    missing = sorted(expected_keys - observed_keys)
    if missing and not allow_incomplete:
        raise ValueError(f"missing {len(missing)} opportunity/role judgments")
    return sorted(clean, key=lambda row: (row["opportunity_id"], row["critic_role"])), opportunities


def delta_summary(values: Sequence[float]) -> dict[str, Any]:
    return {
        **numeric_summary(values),
        "increase": sum(value > 0 for value in values),
        "equal": sum(value == 0 for value in values),
        "decrease": sum(value < 0 for value in values),
    }


def monotone(values: Sequence[float], direction: str) -> bool:
    if direction == "nondecreasing":
        return all(right >= left for left, right in zip(values, values[1:]))
    if direction == "nonincreasing":
        return all(right <= left for left, right in zip(values, values[1:]))
    raise ValueError(direction)


def analyze(
    plan: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    opportunities: Mapping[str, Mapping[str, Any]],
    *,
    input_records: Mapping[str, Any],
) -> dict[str, Any]:
    formats = list(plan["format_order"])
    roles = list(plan["critic_roles"])
    by_format = {
        format_id: summarize_rows([row for row in rows if row["format"] == format_id])
        for format_id in formats
    }
    strata = [cell["pilot_stratum"] for cell in plan["selected_cells"]]
    by_stratum = {
        stratum: summarize_rows([row for row in rows if row["pilot_stratum"] == stratum])
        for stratum in strata
    }
    by_role = {
        role: summarize_rows([row for row in rows if row["critic_role"] == role])
        for role in roles
    }
    by_opportunity: dict[str, Any] = {}
    disagreement_dimensions = (
        "task_comprehensibility",
        "context_naturalness",
        "interaction_naturalness",
        "platform_plausibility",
        "answer_determinacy",
        "accepted_response_coverage",
        "lexical_nuisance",
        "kc_attribution",
    )
    disagreement_ids: dict[str, list[str]] = {
        dimension: [] for dimension in disagreement_dimensions
    }
    for opportunity_id in sorted(opportunities):
        subset = [row for row in rows if row["opportunity_id"] == opportunity_id]
        summary = summarize_rows(subset)
        summary["family_id"] = opportunities[opportunity_id]["family_id"]
        summary["pilot_stratum"] = opportunities[opportunity_id]["pilot_stratum"]
        summary["format"] = opportunities[opportunity_id]["format"]
        summary["role_disagreement"] = {}
        for dimension in disagreement_dimensions:
            applicable = {
                row["ratings"][dimension]
                for row in subset
                if row["ratings"][dimension] != "not_applicable"
            }
            disagrees = len(applicable) > 1
            summary["role_disagreement"][dimension] = disagrees
            if disagrees:
                disagreement_ids[dimension].append(opportunity_id)
        by_opportunity[opportunity_id] = summary

    row_index = {
        (row["family_id"], row["format"], row["critic_role"]): row for row in rows
    }
    reference = formats[0]
    matched_deltas: dict[str, Any] = {}
    for target_format in formats[1:]:
        metric_deltas: dict[str, list[float]] = {metric: [] for metric in RISK_METRICS}
        pair_ids: list[str] = []
        for cell in plan["selected_cells"]:
            family_id = cell["family_id"]
            for role in roles:
                left = row_index.get((family_id, reference, role))
                right = row_index.get((family_id, target_format, role))
                if left is None or right is None:
                    continue
                pair_ids.append(f"{family_id}::{role}")
                for metric in RISK_METRICS:
                    left_value = metric_value(left, metric)
                    right_value = metric_value(right, metric)
                    if left_value is not None and right_value is not None:
                        metric_deltas[metric].append(right_value - left_value)
        matched_deltas[target_format] = {
            "reference_format": reference,
            "matched_family_role_pairs": len(pair_ids),
            "pair_ids": sorted(pair_ids),
            "separate_metric_deltas_target_minus_reference": {
                metric: delta_summary(values)
                for metric, values in metric_deltas.items()
            },
        }

    direction_specs = {
        "interaction_naturalness_risk": "nonincreasing",
        "platform_plausibility_risk": "nonincreasing",
        "determinacy_risk": "nondecreasing",
        "plausible_response_lower_bound": "nondecreasing",
        "incidental_grammar_count": "nondecreasing",
        "lexical_nuisance_risk": "nondecreasing",
        "kc_attribution_risk": "nondecreasing",
    }
    direction_checks: dict[str, Any] = {}
    for metric, direction in direction_specs.items():
        complete_sequences: list[str] = []
        monotone_sequences: list[str] = []
        for cell in plan["selected_cells"]:
            family_id = cell["family_id"]
            for role in roles:
                values: list[float] = []
                for format_id in formats:
                    row = row_index.get((family_id, format_id, role))
                    value = None if row is None else metric_value(row, metric)
                    if value is None:
                        values = []
                        break
                    values.append(value)
                if len(values) == len(formats):
                    sequence_id = f"{family_id}::{role}"
                    complete_sequences.append(sequence_id)
                    if monotone(values, direction):
                        monotone_sequences.append(sequence_id)
        direction_checks[metric] = {
            "predeclared_direction": direction,
            "complete_sequences": len(complete_sequences),
            "monotone_sequences": len(monotone_sequences),
            "fraction_monotone": (
                round(len(monotone_sequences) / len(complete_sequences), 9)
                if complete_sequences
                else None
            ),
            "monotone_sequence_ids": sorted(monotone_sequences),
        }

    return {
        "analysis_id": "ecological_precision_continuum_analysis_v1",
        "status": "CRITIC_JUDGMENTS_ANALYSED",
        "evidence_boundary": {
            "scalar_realism_score_computed": False,
            "weighted_composite_computed": False,
            "interpretation": "Separate automated critic diagnostics; not human response-process, expert-validity, or platform-deployability evidence.",
        },
        "inputs": dict(input_records),
        "scale": {
            "planned_opportunities": len(opportunities),
            "observed_opportunities": len({row["opportunity_id"] for row in rows}),
            "critic_roles": roles,
            "judgments": len(rows),
        },
        "format_order": formats,
        "by_format": by_format,
        "by_cell_stratum": by_stratum,
        "by_critic_role": by_role,
        "by_opportunity": by_opportunity,
        "role_disagreement": {
            dimension: {
                "count": len(ids),
                "opportunity_ids": sorted(ids),
            }
            for dimension, ids in disagreement_ids.items()
        },
        "matched_deltas_vs_constrained_cloze": matched_deltas,
        "continuum_direction_checks": direction_checks,
        "interpretation_rules": [
            "No dimension may be substituted for another or averaged into a realism score.",
            "An ecological improvement does not rescue material ambiguity or weak KC attribution.",
            "A constrained item may remain useful even when its interaction-naturalness rating is lower.",
            "Open dialogue is not viable for scale if its opportunity boundary or KC attribution is not defensible.",
            "Role disagreement and exact opportunity IDs remain reportable evidence.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=PROTOCOL_ROOT / "selected_cells.json")
    parser.add_argument("--judgments", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-incomplete", action="store_true")
    args = parser.parse_args()
    plan = read_json(args.plan)
    raw_rows = read_jsonl(args.judgments)
    rows, opportunities = validate(
        plan, raw_rows, allow_incomplete=bool(args.allow_incomplete)
    )
    input_records = {
        "plan": {
            "path": relative(args.plan),
            "sha256": file_sha256(args.plan),
            "bytes": args.plan.stat().st_size,
        },
        "judgments": {
            "path": relative(args.judgments),
            "sha256": file_sha256(args.judgments),
            "bytes": args.judgments.stat().st_size,
            "rows": len(raw_rows),
        },
        "analysis_script": {
            "path": relative(Path(__file__).resolve()),
            "sha256": file_sha256(Path(__file__).resolve()),
            "bytes": Path(__file__).stat().st_size,
        },
    }
    result = analyze(plan, rows, opportunities, input_records=input_records)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        canonical_json(
            {
                "status": result["status"],
                "opportunities": result["scale"]["observed_opportunities"],
                "judgments": result["scale"]["judgments"],
                "scalar_realism_score_computed": False,
            }
        )
    )


if __name__ == "__main__":
    main()
