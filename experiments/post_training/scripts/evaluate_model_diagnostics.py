#!/usr/bin/env python3
"""Score retained raw outputs from the batched model diagnostics."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from grammar_kt.io import ROOT, read_json, write_json


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def parsed_results(path: Path) -> tuple[dict[str, dict[str, Any]], list[str]]:
    errors = []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:
        return {}, [f"could not parse {path}: {error}"]
    rows = raw.get("results") if isinstance(raw, dict) else None
    if not isinstance(rows, list):
        return {}, [f"{path}: results is not a list"]
    by_id = {}
    for row in rows:
        case_id = row.get("case_id") if isinstance(row, dict) else None
        if not isinstance(case_id, str) or case_id in by_id:
            errors.append(f"{path}: missing or duplicate case_id {case_id!r}")
            continue
        by_id[case_id] = row
    return by_id, errors


def normalize_sentence(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def score_generation(root: Path, conditions: list[str]) -> dict[str, Any]:
    cases = read_json(root / "cases.json")
    case_by_id = {row["case_id"]: row for row in cases}
    metrics = {}
    for condition in conditions:
        predictions, errors = parsed_results(root / condition / "raw_output.json")
        missing = sorted(set(case_by_id) - set(predictions))
        unknown = sorted(set(predictions) - set(case_by_id))
        rows = []
        for case_id, case in case_by_id.items():
            prediction = predictions.get(case_id, {}).get("response", "")
            exact = normalize_sentence(str(prediction)) == normalize_sentence(
                case["target_answer"]
            )
            format_ok = bool(
                isinstance(prediction, str)
                and "\n" not in prediction.strip()
                and re.fullmatch(r"[^.!?]+[.!?]", prediction.strip())
            )
            rows.append(
                {
                    "case_id": case_id,
                    "canonical_cell_id": case["canonical_cell_id"],
                    "prediction": prediction,
                    "target": case["target_answer"],
                    "exact": exact,
                    "one_sentence_format": format_ok,
                }
            )
        metrics[condition] = {
            "cases": len(cases),
            "exact": sum(row["exact"] for row in rows),
            "exact_accuracy": sum(row["exact"] for row in rows) / len(rows),
            "one_sentence_format_rate": sum(
                row["one_sentence_format"] for row in rows
            )
            / len(rows),
            "missing_case_ids": missing,
            "unknown_case_ids": unknown,
            "parse_errors": errors,
            "rows": rows,
        }
    best = max(metrics, key=lambda name: metrics[name]["exact_accuracy"])
    baseline = metrics["natural_language_description"]["exact_accuracy"]
    return {
        "conditions": metrics,
        "best_condition": best,
        "best_exact_accuracy": metrics[best]["exact_accuracy"],
        "best_improvement_over_natural_language_percentage_points": 100
        * (metrics[best]["exact_accuracy"] - baseline),
        "representation_value_gate": (
            metrics[best]["exact_accuracy"] - baseline >= 0.10
            and metrics[best]["one_sentence_format_rate"]
            >= metrics["natural_language_description"]["one_sentence_format_rate"]
        ),
    }


def score_preference(root: Path) -> dict[str, Any]:
    order_scores = {}
    decisions: dict[str, dict[str, str]] = defaultdict(dict)
    for order_name in ("seeded_order", "reversed_order"):
        cases = read_json(root / order_name / "cases.json")
        predictions, errors = parsed_results(
            root / order_name / "invocation" / "raw_output.json"
        )
        rows = []
        for case in cases:
            prediction = predictions.get(case["case_id"], {})
            preferred = prediction.get("preferred")
            dimension = prediction.get("error_dimension")
            selected_text = (
                case.get(f"candidate_{preferred}") if preferred in {"A", "B"} else None
            )
            decisions[case["preference_record_id"]][order_name] = selected_text
            rows.append(
                {
                    "case_id": case["case_id"],
                    "preference_record_id": case["preference_record_id"],
                    "preferred": preferred,
                    "expected_preferred": case["expected_preferred"],
                    "preference_correct": preferred == case["expected_preferred"],
                    "error_dimension": dimension,
                    "expected_error_dimension": case["expected_error_dimension"],
                    "dimension_correct": dimension
                    == case["expected_error_dimension"],
                    "selected_text": selected_text,
                }
            )
        order_scores[order_name] = {
            "pairs": len(rows),
            "preference_accuracy": sum(row["preference_correct"] for row in rows)
            / len(rows),
            "error_dimension_accuracy": sum(row["dimension_correct"] for row in rows)
            / len(rows),
            "missing_case_ids": sorted(
                {row["case_id"] for row in cases} - set(predictions)
            ),
            "parse_errors": errors,
            "rows": rows,
        }
    comparable = [values for values in decisions.values() if len(values) == 2]
    consistent = sum(
        row["seeded_order"] == row["reversed_order"] for row in comparable
    )
    consistency_rate = consistent / len(comparable) if comparable else 0.0
    minimum_accuracy = min(
        row["preference_accuracy"] for row in order_scores.values()
    )
    return {
        "orders": order_scores,
        "order_comparable_pairs": len(comparable),
        "order_consistency_rate": consistency_rate,
        "order_inconsistency_rate": 1.0 - consistency_rate,
        "preference_validity_gate": minimum_accuracy >= 0.90
        and (1.0 - consistency_rate) <= 0.10,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "experiments/post_training/configs/model_diagnostics_v0.json",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=ROOT / "experiments/post_training/results/prompt_ablation_v0",
    )
    args = parser.parse_args()
    config = read_json(args.config)
    summary: dict[str, Any] = {
        "experiment_id": config["experiment_id"],
        "model": config["model"],
        "claim_boundary": config["claim_boundary"],
        "exact_command": ".venv/bin/python experiments/post_training/scripts/evaluate_model_diagnostics.py",
    }
    if (args.input / "generation" / "cases.json").is_file():
        summary["generation"] = score_generation(
            args.input / "generation", config["generation_conditions"]
        )
    if (args.input / "preference" / "seeded_order" / "cases.json").is_file():
        summary["preference"] = score_preference(args.input / "preference")
    write_json(args.input / "summary.json", summary)
    invocation_paths = sorted(args.input.glob("**/invocation.json"))
    invocations = [read_json(path) for path in invocation_paths]
    retained_paths = sorted(
        path
        for path in args.input.glob("**/*")
        if path.is_file() and path.name not in {"summary.json", "manifest.json"}
    )
    write_json(
        args.input / "manifest.json",
        {
            "experiment_id": config["experiment_id"],
            "git": git_state(),
            "config": {
                "path": display_path(args.config),
                "sha256": sha256(args.config),
            },
            "evaluator": {
                "path": display_path(Path(__file__)),
                "sha256": sha256(Path(__file__).resolve()),
            },
            "model": config["model"],
            "model_revision": None,
            "reasoning_effort": config["reasoning_effort"],
            "model_snapshot_pinned": False,
            "decoding_parameters_pinned": False,
            "seed": config["seed"],
            "calls": len(invocations),
            "total_runtime_seconds": sum(
                float(row["runtime_seconds"]) for row in invocations
            ),
            "monetary_cost": None,
            "monetary_cost_note": "The CLI did not expose monetary cost.",
            "invocation_environments": [
                {
                    key: row.get(key)
                    for key in (
                        "experiment",
                        "model",
                        "reasoning_effort",
                        "codex_version",
                        "python",
                        "platform",
                        "started_utc",
                        "finished_utc",
                        "runtime_seconds",
                        "returncode",
                    )
                }
                for row in invocations
            ],
            "retained_artifact_sha256": {
                str(path.relative_to(args.input)): sha256(path)
                for path in retained_paths
            },
            "claim_boundary": config["claim_boundary"],
            "exact_command": summary["exact_command"],
        },
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
