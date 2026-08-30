#!/usr/bin/env python3
"""Audit full-v1 as learner-facing platform measurement.

The live stage uses separate audited Codex calls for four declared critic
roles.  The roles never see one another's output.  Their categorical judgments
are retained separately; the summary uses only transparent pluralities and
severity tie breaks.  This is automated stress-test evidence, not human gold.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from grammar_kt.io import read_yaml
from grammar_kt.model_evidence import audited_model_call


DEFAULT_DATASET = ROOT / "data/grammar_kt_full_v1"
DEFAULT_CONFIG = ROOT / "modules/measurement_realism/item_audit.yaml"
DEFAULT_OUTPUT = ROOT / "experiments/measurement_realism/audits/full_v1_items_v2"
DEFAULT_EVIDENCE_ROOT = ROOT / "runs/measurement_realism/full_v1_item_audit_evidence_v2"


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_frozen_text(path: Path, payload: str, label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_text(encoding="utf-8") != payload:
            raise FileExistsError(f"refusing to overwrite changed {label}: {path}")
        return
    path.write_text(payload, encoding="utf-8")


def write_frozen_json(path: Path, value: Any, label: str) -> None:
    write_frozen_text(
        path,
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        label,
    )


def repository_head() -> str | None:
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


def load_q(path: Path) -> dict[str, tuple[str, ...]]:
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or reader.fieldnames[0] != "item_id":
            raise ValueError("Q matrix must begin with item_id")
        kc_ids = reader.fieldnames[1:]
        output: dict[str, tuple[str, ...]] = {}
        for row in reader:
            item_id = str(row["item_id"])
            if item_id in output:
                raise ValueError(f"duplicate Q row: {item_id}")
            if any(row[kc_id] not in {"0", "1"} for kc_id in kc_ids):
                raise ValueError("Q matrix must be binary")
            output[item_id] = tuple(kc for kc in kc_ids if row[kc] == "1")
    return output


def load_enriched_items(dataset: Path) -> list[dict[str, Any]]:
    manifest = json.loads((dataset / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("status") != "FROZEN_BASELINE_COMPLETE":
        raise ValueError("audit requires frozen full-v1")
    items = read_jsonl(dataset / "items/items.jsonl")
    cells = {
        str(row["cell_id"]): row["features"]
        for row in read_jsonl(dataset / "grammar/cells.jsonl")
    }
    q = load_q(dataset / "q_matrix.csv")
    kc_names = {
        str(row["id"]): str(row["name"])
        for row in read_jsonl(dataset / "kcs.jsonl")
    }
    if set(q) != {str(row["item_id"]) for row in items}:
        raise ValueError("items and Q* disagree")
    output = []
    for row in sorted(items, key=lambda value: str(value["item_id"])):
        item_id = str(row["item_id"])
        cell_id = str(row["cell_id"])
        if cell_id not in cells:
            raise ValueError(f"unknown GrammarCell: {cell_id}")
        campaign = row.get("generation_metadata", {}).get("campaign", "initial")
        active = list(q[item_id])
        output.append(
            {
                "item_id": item_id,
                "cell_id": cell_id,
                "format": row["format"],
                "prompt": row["prompt"],
                "target_answer": row["target_answer"],
                "accepted_answers": row["accepted_answers"],
                "grammar_cell": cells[cell_id],
                "active_generator_kcs": [
                    {"id": kc_id, "name": kc_names[kc_id]} for kc_id in active
                ],
                "generation_campaign": campaign,
                "prompt_word_count": len(str(row["prompt"]).split()),
            }
        )
    if len(output) != 113:
        raise ValueError("full-v1 item count changed")
    return output


def plan_inputs(dataset: Path, config_path: Path) -> dict[str, dict[str, Any]]:
    paths = {
        "dataset_manifest": dataset / "manifest.json",
        "items": dataset / "items/items.jsonl",
        "cells": dataset / "grammar/cells.jsonl",
        "kcs": dataset / "kcs.jsonl",
        "q_matrix": dataset / "q_matrix.csv",
        "config": config_path,
    }
    return {
        name: {
            "path": str(path.relative_to(ROOT)),
            "sha256": file_sha256(path),
            "bytes": path.stat().st_size,
        }
        for name, path in paths.items()
    }


def create_plan(dataset: Path, config_path: Path, output: Path) -> dict[str, Any]:
    config = read_yaml(config_path)
    items = load_enriched_items(dataset)
    item_payload = "".join(canonical_json(row) + "\n" for row in items)
    write_frozen_text(output / "audit_input.jsonl", item_payload, "audit input")
    script_path = Path(__file__).resolve()
    plan = {
        "audit_id": config["audit_id"],
        "status": "PREREGISTERED_BEFORE_AUTOMATED_CRITIQUE",
        "evidence_type": "independent_non_human_codex_stress_test",
        "human_or_expert_gold": False,
        "items": len(items),
        "roles": list(config["roles"]),
        "dimensions": list(config["dimensions"]),
        "ratings": list(config["ratings"]),
        "dispositions": list(config["dispositions"]),
        "batch_size": int(config["batch_size"]),
        "model": dict(config["model"]),
        "schema_enforcement": {
            "provider_output_schema": True,
            "local_exact_key_and_item_coverage_validation": True,
            "rationale": "A retained v1 infrastructure attempt exposed one misspelled dimension key; no v1 judgment entered analysis.",
        },
        "aggregation": {
            "dimension": "plurality across non-not_applicable role ratings; severity tie break major_concern > minor_concern > pass",
            "disposition": "plurality across roles; tie broken by declared disposition_tie_break_order from least to most severe",
            "disagreement": "number of distinct non-not_applicable ratings, plus role-specific values",
            "interpretation": "diagnostic automated prevalence only; not validated population prevalence",
        },
        "scientific_boundary": {
            "learner_outcomes_read": False,
            "private_oracle_read": False,
            "generator_annotations_hidden_from_learner_role": True,
            "roles_receive_other_role_outputs": False,
            "frozen_dataset_mutated": False,
        },
        "inputs": plan_inputs(dataset, config_path),
        "audit_input": {
            "path": "audit_input.jsonl",
            "sha256": sha256_bytes(item_payload.encode("utf-8")),
            "rows": len(items),
        },
        "implementation": {
            "script": str(script_path.relative_to(ROOT)),
            "script_sha256": file_sha256(script_path),
            "audited_backend": "src/grammar_kt/model_evidence.py",
            "audited_backend_sha256": file_sha256(
                ROOT / "src/grammar_kt/model_evidence.py"
            ),
            "repository_head_at_plan": repository_head(),
            "python": sys.version.split()[0],
        },
        "exact_commands": {
            "plan": ".venv/bin/python scripts/experiments/measurement_realism_audit.py plan",
            "run": ".venv/bin/python scripts/experiments/measurement_realism_audit.py run --evidence-root runs/measurement_realism/full_v1_item_audit_evidence_v2",
            "analyse": ".venv/bin/python scripts/experiments/measurement_realism_audit.py analyse",
        },
    }
    write_frozen_json(output / "study_plan.json", plan, "audit plan")
    return plan


def validate_plan(dataset: Path, config_path: Path, output: Path) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    plan_path = output / "study_plan.json"
    if not plan_path.is_file():
        raise FileNotFoundError("run/analyse requires study_plan.json")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    config = read_yaml(config_path)
    if plan.get("status") != "PREREGISTERED_BEFORE_AUTOMATED_CRITIQUE":
        raise ValueError("invalid audit plan status")
    if plan.get("audit_id") != config.get("audit_id"):
        raise ValueError("audit ID changed")
    if plan["implementation"]["script_sha256"] != file_sha256(Path(__file__).resolve()):
        raise ValueError("audit implementation changed after plan")
    if plan["implementation"]["audited_backend_sha256"] != file_sha256(
        ROOT / plan["implementation"]["audited_backend"]
    ):
        raise ValueError("audited model backend changed after plan")
    if plan["inputs"] != plan_inputs(dataset, config_path):
        raise ValueError("audit inputs changed after plan")
    input_path = output / plan["audit_input"]["path"]
    if file_sha256(input_path) != plan["audit_input"]["sha256"]:
        raise ValueError("audit input changed after plan")
    items = read_jsonl(input_path)
    if len(items) != plan["items"]:
        raise ValueError("audit input row count changed")
    return plan, config, items


def visible_for_role(item: Mapping[str, Any], sees_oracle: bool) -> dict[str, Any]:
    visible = {
        key: item[key]
        for key in (
            "item_id",
            "format",
            "prompt",
            "target_answer",
            "accepted_answers",
        )
    }
    if sees_oracle:
        visible.update(
            {
                "grammar_cell": item["grammar_cell"],
                "active_generator_kcs": item["active_generator_kcs"],
            }
        )
    return visible


def render_prompt(role: str, declaration: Mapping[str, Any], config: Mapping[str, Any], batch: Sequence[Mapping[str, Any]]) -> str:
    dimensions = "\n".join(
        f"- {name}: {question}" for name, question in config["dimensions"].items()
    )
    items = [
        visible_for_role(row, bool(declaration["sees_oracle_annotations"]))
        for row in batch
    ]
    return f"""You are one independent automated critic in a frozen scientific item audit.

ROLE: {role}
LENS: {declaration['lens']}

Evaluate every supplied item independently. Do not browse, call tools, inspect files, or infer other critics' opinions. The target answer and accepted answers are audit keys; they are not visible to an actual learner. GrammarCell/KC annotations, when supplied, are synthetic study annotations rather than claims about human cognition.

Dimensions:
{dimensions}

Use exactly one rating per dimension: {', '.join(config['ratings'])}.
Use `not_applicable` only when the role genuinely cannot assess that dimension. Choose exactly one deployment disposition: {', '.join(config['dispositions'])}.

Return one JSON object with exactly this shape:
{{"role":"{role}","judgments":[{{"item_id":"...","ratings":{{"task_comprehensibility":"pass", "answer_determinacy":"pass", "pedagogical_plausibility":"pass", "format_plausibility":"pass", "lexical_simplicity":"pass", "context_naturalness":"pass", "difficulty_plausibility":"pass", "response_space_plausibility":"pass", "kc_measurement_purity":"pass", "platform_deployability":"pass"}},"disposition":"usable_as_is","primary_concern":"none or one concise item-specific concern (maximum 24 words)","confidence":"low|medium|high"}}]}}

Requirements:
- Include every supplied item exactly once and no other item.
- Use every dimension key exactly once for every item.
- Judge the actual text and scoring mechanism, not whether its Q row is mathematically useful.
- Treat spelling, punctuation, contraction, alternate wording, semantic ambiguity, verbosity, specialist terminology, and visible UI mechanics as relevant where appropriate.
- A concise reason is required in `primary_concern`; use `none` only when no material concern exists.
- Return JSON only, with no markdown.

ITEMS:
{json.dumps(items, ensure_ascii=False)}
"""


def validate_role_result(result: Mapping[str, Any], role: str, item_ids: Sequence[str], config: Mapping[str, Any]) -> list[dict[str, Any]]:
    if set(result) != {"role", "judgments"} or result.get("role") != role:
        raise ValueError(f"{role} output has wrong envelope")
    judgments = result.get("judgments")
    if not isinstance(judgments, list):
        raise ValueError(f"{role} judgments must be a list")
    expected_dimensions = set(config["dimensions"])
    allowed_ratings = set(config["ratings"])
    allowed_dispositions = set(config["dispositions"])
    allowed_confidence = {"low", "medium", "high"}
    output: list[dict[str, Any]] = []
    for row in judgments:
        if set(row) != {"item_id", "ratings", "disposition", "primary_concern", "confidence"}:
            raise ValueError(f"{role} judgment fields changed")
        if set(row["ratings"]) != expected_dimensions:
            raise ValueError(f"{role} rating dimensions changed for {row.get('item_id')}")
        if set(row["ratings"].values()) - allowed_ratings:
            raise ValueError(f"{role} used an unknown rating")
        if row["disposition"] not in allowed_dispositions:
            raise ValueError(f"{role} used an unknown disposition")
        if row["confidence"] not in allowed_confidence:
            raise ValueError(f"{role} used an unknown confidence")
        concern = row["primary_concern"]
        if not isinstance(concern, str) or not concern.strip() or len(concern.split()) > 28:
            raise ValueError(f"{role} concern is empty or too long")
        output.append(dict(row))
    observed = [str(row["item_id"]) for row in output]
    if len(observed) != len(set(observed)) or set(observed) != set(item_ids):
        raise ValueError(f"{role} output item coverage changed")
    return sorted(output, key=lambda row: str(row["item_id"]))


def critic_output_schema(role: str, config: Mapping[str, Any]) -> dict[str, Any]:
    """Return the strict provider-side schema used before local validation."""

    rating_properties = {
        dimension: {"type": "string", "enum": list(config["ratings"])}
        for dimension in config["dimensions"]
    }
    judgment_properties = {
        "item_id": {"type": "string", "minLength": 1},
        "ratings": {
            "type": "object",
            "properties": rating_properties,
            "required": list(config["dimensions"]),
            "additionalProperties": False,
        },
        "disposition": {
            "type": "string",
            "enum": list(config["dispositions"]),
        },
        "primary_concern": {"type": "string", "minLength": 1},
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
    }
    return {
        "type": "object",
        "properties": {
            "role": {"type": "string", "enum": [role]},
            "judgments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": judgment_properties,
                    "required": list(judgment_properties),
                    "additionalProperties": False,
                },
            },
        },
        "required": ["role", "judgments"],
        "additionalProperties": False,
    }


def run_audit(
    dataset: Path,
    config_path: Path,
    output: Path,
    evidence_root: Path,
) -> dict[str, Any]:
    plan, config, items = validate_plan(dataset, config_path, output)
    batch_size = int(plan["batch_size"])
    all_rows: list[dict[str, Any]] = []
    call_manifest: list[dict[str, Any]] = []
    raw_records: list[dict[str, Any]] = []
    for role, declaration in config["roles"].items():
        for start in range(0, len(items), batch_size):
            batch = items[start : start + batch_size]
            batch_number = start // batch_size + 1
            # The audited backend requires call-level evidence to live in an
            # ignored/restricted location because some projects use protected
            # source context.  This audit contains only public frozen items,
            # so a byte-exact raw-output bundle is additionally retained under
            # the experiment directory after each successful call.
            evidence_dir = evidence_root / role / f"batch_{batch_number:02d}"
            prompt = render_prompt(role, declaration, config, batch)
            if (evidence_dir / "parsed_result.json").is_file():
                parsed = json.loads(
                    (evidence_dir / "parsed_result.json").read_text(encoding="utf-8")
                )
            else:
                if evidence_dir.exists():
                    raise FileExistsError(
                        f"incomplete evidence directory must be audited before retry: {evidence_dir}"
                    )
                parsed = audited_model_call(
                    prompt,
                    model=str(config["model"]["name"]),
                    reasoning_effort=str(config["model"]["reasoning_effort"]),
                    input_data={
                        "audit_id": plan["audit_id"],
                        "role": role,
                        "batch_number": batch_number,
                        "items": [
                            visible_for_role(
                                row, bool(declaration["sees_oracle_annotations"])
                            )
                            for row in batch
                        ],
                    },
                    stage="measurement_realism_item_audit",
                    call_key=f"{role}__batch_{batch_number:02d}",
                    evidence_dir=evidence_dir,
                    output_schema=critic_output_schema(role, config),
                )
            rows = validate_role_result(
                parsed,
                role,
                [str(row["item_id"]) for row in batch],
                config,
            )
            all_rows.extend({"role": role, **row} for row in rows)
            raw_text = (evidence_dir / "raw_output.txt").read_text(encoding="utf-8")
            raw_records.append(
                {
                    "role": role,
                    "batch_number": batch_number,
                    "item_ids": [str(row["item_id"]) for row in batch],
                    "raw_output": raw_text,
                }
            )
            call_manifest.append(
                {
                    "role": role,
                    "batch_number": batch_number,
                    "items": len(batch),
                    "first_item_id": batch[0]["item_id"],
                    "last_item_id": batch[-1]["item_id"],
                    "evidence_dir": (
                        str(evidence_dir.relative_to(ROOT))
                        if evidence_dir.is_relative_to(ROOT)
                        else str(evidence_dir)
                    ),
                    "rendered_prompt_sha256": file_sha256(
                        evidence_dir / "rendered_prompt.txt"
                    ),
                    "raw_output_sha256": file_sha256(evidence_dir / "raw_output.txt"),
                    "parsed_result_sha256": file_sha256(
                        evidence_dir / "parsed_result.json"
                    ),
                }
            )
    expected = len(items) * len(config["roles"])
    if len(all_rows) != expected:
        raise ValueError("audit judgment count changed")
    judgment_payload = "".join(
        canonical_json(row) + "\n"
        for row in sorted(all_rows, key=lambda row: (row["item_id"], row["role"]))
    )
    write_frozen_text(output / "judgments.jsonl", judgment_payload, "audit judgments")
    raw_payload = "".join(
        canonical_json(row) + "\n"
        for row in sorted(raw_records, key=lambda row: (row["role"], row["batch_number"]))
    )
    write_frozen_text(
        output / "raw_model_outputs.jsonl",
        raw_payload,
        "raw model-output bundle",
    )
    manifest = {
        "audit_id": plan["audit_id"],
        "status": "AUTOMATED_CRITIQUE_COMPLETE",
        "evidence_type": plan["evidence_type"],
        "human_or_expert_gold": False,
        "calls": len(call_manifest),
        "judgments": len(all_rows),
        "items": len(items),
        "call_manifest": call_manifest,
        "judgments_sha256": sha256_bytes(judgment_payload.encode("utf-8")),
        "raw_model_outputs_sha256": sha256_bytes(raw_payload.encode("utf-8")),
        "restricted_call_evidence_root": (
            str(evidence_root.relative_to(ROOT))
            if evidence_root.is_relative_to(ROOT)
            else str(evidence_root)
        ),
    }
    write_frozen_json(output / "run_manifest.json", manifest, "audit run manifest")
    return manifest


def plurality(values: Sequence[str], tie_order: Sequence[str]) -> str:
    counts = Counter(values)
    maximum = max(counts.values())
    tied = {value for value, count in counts.items() if count == maximum}
    order = {value: index for index, value in enumerate(tie_order)}
    return max(tied, key=lambda value: order[value])


def analyse(dataset: Path, config_path: Path, output: Path) -> dict[str, Any]:
    plan, config, items = validate_plan(dataset, config_path, output)
    manifest = json.loads((output / "run_manifest.json").read_text(encoding="utf-8"))
    judgments_path = output / "judgments.jsonl"
    if file_sha256(judgments_path) != manifest["judgments_sha256"]:
        raise ValueError("audit judgments changed after run")
    judgments = read_jsonl(judgments_path)
    by_item: dict[str, list[dict[str, Any]]] = defaultdict(list)
    role_dimension_counts: dict[str, dict[str, Counter[str]]] = defaultdict(
        lambda: defaultdict(Counter)
    )
    role_dispositions: dict[str, Counter[str]] = defaultdict(Counter)
    for row in judgments:
        by_item[str(row["item_id"])].append(row)
        role_dispositions[str(row["role"])][str(row["disposition"])] += 1
        for dimension, rating in row["ratings"].items():
            role_dimension_counts[str(row["role"])][dimension][rating] += 1
    rating_order = ["pass", "minor_concern", "major_concern"]
    disposition_order = list(config["disposition_tie_break_order"])
    aggregate_rows = []
    for item in items:
        item_id = str(item["item_id"])
        roles = sorted(by_item[item_id], key=lambda row: str(row["role"]))
        if len(roles) != len(config["roles"]):
            raise ValueError(f"incomplete role coverage: {item_id}")
        dimensions: dict[str, Any] = {}
        for dimension in config["dimensions"]:
            values_by_role = {
                str(row["role"]): str(row["ratings"][dimension]) for row in roles
            }
            applicable = [
                value for value in values_by_role.values() if value != "not_applicable"
            ]
            if applicable:
                majority = plurality(applicable, rating_order)
                disagreement_levels = len(set(applicable))
            else:
                majority = "not_applicable"
                disagreement_levels = 0
            dimensions[dimension] = {
                "plurality": majority,
                "distinct_applicable_ratings": disagreement_levels,
                "by_role": values_by_role,
            }
        dispositions_by_role = {
            str(row["role"]): str(row["disposition"]) for row in roles
        }
        final_disposition = plurality(
            list(dispositions_by_role.values()), disposition_order
        )
        aggregate_rows.append(
            {
                "item_id": item_id,
                "cell_id": item["cell_id"],
                "format": item["format"],
                "generation_campaign": item["generation_campaign"],
                "prompt_word_count": item["prompt_word_count"],
                "active_generator_kc_ids": [
                    row["id"] for row in item["active_generator_kcs"]
                ],
                "disposition": final_disposition,
                "disposition_by_role": dispositions_by_role,
                "disposition_disagreement": len(set(dispositions_by_role.values())) > 1,
                "dimensions": dimensions,
                "primary_concern_by_role": {
                    str(row["role"]): str(row["primary_concern"]) for row in roles
                },
                "confidence_by_role": {
                    str(row["role"]): str(row["confidence"]) for row in roles
                },
            }
        )
    aggregate_payload = "".join(canonical_json(row) + "\n" for row in aggregate_rows)
    write_frozen_text(output / "item_aggregates.jsonl", aggregate_payload, "item aggregates")
    disposition_counts = Counter(row["disposition"] for row in aggregate_rows)
    campaign_counts: dict[str, Counter[str]] = defaultdict(Counter)
    kc_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in aggregate_rows:
        campaign_counts[row["generation_campaign"]][row["disposition"]] += 1
        for kc_id in row["active_generator_kc_ids"]:
            kc_counts[kc_id][row["disposition"]] += 1
    summary = {
        "audit_id": plan["audit_id"],
        "status": "AUTOMATED_AUDIT_ANALYSED",
        "evidence_boundary": {
            "critics": "four independent Codex role prompts",
            "human_or_expert_gold": False,
            "interpretation": "automated qualitative stress test; percentages are not validated prevalence estimates",
        },
        "scale": {
            "items": len(items),
            "roles": len(config["roles"]),
            "judgments": len(judgments),
        },
        "aggregate_dispositions": {
            value: {
                "count": disposition_counts[value],
                "fraction": disposition_counts[value] / len(items),
            }
            for value in config["dispositions"]
        },
        "disposition_disagreement": {
            "items": sum(row["disposition_disagreement"] for row in aggregate_rows),
            "fraction": sum(row["disposition_disagreement"] for row in aggregate_rows)
            / len(items),
        },
        "role_dispositions": {
            role: dict(sorted(counts.items()))
            for role, counts in sorted(role_dispositions.items())
        },
        "role_dimension_counts": {
            role: {
                dimension: dict(sorted(counts.items()))
                for dimension, counts in sorted(dimensions.items())
            }
            for role, dimensions in sorted(role_dimension_counts.items())
        },
        "by_generation_campaign": {
            campaign: dict(sorted(counts.items()))
            for campaign, counts in sorted(campaign_counts.items())
        },
        "by_generator_kc": {
            kc_id: dict(sorted(counts.items()))
            for kc_id, counts in sorted(kc_counts.items())
        },
        "item_aggregates_sha256": sha256_bytes(aggregate_payload.encode("utf-8")),
        "judgments_sha256": manifest["judgments_sha256"],
    }
    write_frozen_json(output / "summary.json", summary, "audit summary")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("plan", "run", "analyse"))
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE_ROOT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    dataset = args.dataset.resolve()
    config = args.config.resolve()
    output = args.output.resolve()
    evidence_root = args.evidence_root.resolve()
    if args.stage == "plan":
        result = create_plan(dataset, config, output)
    elif args.stage == "run":
        result = run_audit(dataset, config, output, evidence_root)
    else:
        result = analyse(dataset, config, output)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
