#!/usr/bin/env python3
"""Run the preregistered batched generation or preference-judge diagnostic."""

from __future__ import annotations

import argparse
import json
import os
import platform
import random
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from grammar_kt.io import ROOT, read_json, read_jsonl, utc_now, write_json


def output_schema(case_ids: list[str], *, judge: bool) -> dict[str, Any]:
    properties: dict[str, Any] = {
        "case_id": {"type": "string", "enum": case_ids},
    }
    if judge:
        properties.update(
            {
                "preferred": {"type": "string", "enum": ["A", "B"]},
                "error_dimension": {
                    "type": "string",
                    "enum": [
                        "tense",
                        "aspect",
                        "voice",
                        "polarity",
                        "clause",
                        "modal",
                        "unknown",
                    ],
                },
            }
        )
    else:
        properties["response"] = {"type": "string"}
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "additionalProperties": False,
        "required": ["results"],
        "properties": {
            "results": {
                "type": "array",
                "minItems": len(case_ids),
                "maxItems": len(case_ids),
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": list(properties),
                    "properties": properties,
                },
            }
        },
    }


def natural_description(cell: dict[str, str]) -> str:
    parts = []
    if cell["tense"] != "NA":
        parts.append(f"use {cell['tense']} tense")
    parts.extend(
        (
            f"use {cell['aspect'].replace('_', ' ')} aspect",
            f"use {cell['voice']} voice",
            f"make it {cell['polarity']}",
            f"make it a {cell['clause'].replace('_', ' ')}",
        )
    )
    if cell["modal"] != "none":
        parts.append(f"use the modal {cell['modal']}")
    return "; ".join(parts)


def generation_cases(data_dir: Path, maximum: int) -> list[dict[str, Any]]:
    items = read_jsonl(data_dir / "items.jsonl")
    selected: dict[str, dict[str, Any]] = {}
    for item in sorted(items, key=lambda row: row["item_id"]):
        selected.setdefault(item["canonical_cell_id"], item)
    cases = []
    for index, item in enumerate(sorted(selected.values(), key=lambda row: row["canonical_cell_id"])[:maximum], 1):
        cases.append(
            {
                "case_id": f"GEN_{index:03d}",
                "item_id": item["item_id"],
                "canonical_cell_id": item["canonical_cell_id"],
                "canonical_structure": item.get("cell"),
                "realization_spec": item["realization_spec"],
                "exercise_prompt": item["prompt"],
                "target_answer": item["target_answer"],
            }
        )
    # Intrinsic item rows do not contain the cell itself; recover it from the prompt's
    # exact six-field declaration without giving the target sentence to the model.
    for case in cases:
        grammar_fragment = case["exercise_prompt"].split("Grammar: ", 1)[1].split(".\n", 1)[0]
        values = {}
        for part in grammar_fragment.split("; ")[:6]:
            key, value = part.split("=", 1)
            values[key] = value
        case["canonical_structure"] = values
    return cases


def render_generation_prompt(condition: str, cases: list[dict[str, Any]]) -> str:
    rendered = []
    for case in cases:
        spec = case["realization_spec"]
        if condition == "natural_language_description":
            task = {
                "case_id": case["case_id"],
                "request": natural_description(case["canonical_structure"]),
                "fixed_lexical_conditions": {
                    "subject": spec["subject"],
                    "predicate_frame_id": spec["predicate_frame_id"],
                    "wh": spec["wh"],
                    "imperative_subtype": spec["imperative_subtype"],
                    "let_pronoun": spec["let_pronoun"],
                },
            }
        elif condition == "canonical_structure":
            task = {
                "case_id": case["case_id"],
                "canonical_structure": case["canonical_structure"],
                "realization_spec": spec,
            }
        elif condition == "canonical_plus_realization_constraints":
            task = {
                "case_id": case["case_id"],
                "canonical_structure": case["canonical_structure"],
                "realization_constraints": case["exercise_prompt"],
            }
        else:
            raise ValueError(condition)
        rendered.append(task)
    return (
        "Complete each independent controlled English generation case. Return exactly "
        "one sentence per case in the required JSON shape. Do not explain, number, quote, "
        "or add alternatives. Predicate frame IDs have their ordinary repository meanings: "
        "FRAME_WRITE means WRITE with object 'the report'; FRAME_LIKE means LIKE with object "
        "'the new plan'; FRAME_COPULAR_READY means copular BE with complement 'ready'.\n\n"
        + json.dumps(rendered, ensure_ascii=False, indent=2)
    )


def preference_sample(data_dir: Path, per_dimension: int) -> list[dict[str, Any]]:
    rows = read_jsonl(data_dir / "preference.jsonl")
    counts: dict[str, int] = {}
    selected = []
    for row in sorted(rows, key=lambda value: value["record_id"]):
        dimension = row["preference_label"]["differing_dimension"]
        if counts.get(dimension, 0) >= per_dimension:
            continue
        selected.append(row)
        counts[dimension] = counts.get(dimension, 0) + 1
    return selected


def judge_cases(
    preferences: list[dict[str, Any]], *, seed: int, reversed_order: bool
) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    cases = []
    for index, row in enumerate(preferences, 1):
        chosen_first = bool(rng.getrandbits(1))
        if reversed_order:
            chosen_first = not chosen_first
        candidate_a = row["chosen"] if chosen_first else row["rejected"]
        candidate_b = row["rejected"] if chosen_first else row["chosen"]
        cases.append(
            {
                "case_id": f"JUDGE_{index:03d}",
                "preference_record_id": row["record_id"],
                "target": row["context"],
                "candidate_A": candidate_a,
                "candidate_B": candidate_b,
                "expected_preferred": "A" if chosen_first else "B",
                "expected_error_dimension": row["preference_label"][
                    "differing_dimension"
                ],
            }
        )
    return cases


def render_judge_prompt(cases: list[dict[str, Any]]) -> str:
    visible = [
        {
            "case_id": row["case_id"],
            "target": row["target"],
            "candidate_A": row["candidate_A"],
            "candidate_B": row["candidate_B"],
        }
        for row in cases
    ]
    return (
        "For every independent case, choose the candidate that exactly realizes the target "
        "grammar and fixed lexical constraints. Both candidates may be fluent English; one "
        "is deliberately valid for a nearby grammar cell. Also identify the single canonical "
        "dimension on which the rejected candidate differs. Return only the required JSON.\n\n"
        + json.dumps(visible, ensure_ascii=False, indent=2)
    )


def run_codex(
    target: Path,
    *,
    prompt: str,
    schema: dict[str, Any],
    model: str,
    reasoning_effort: str,
    timeout_seconds: int,
    experiment: str,
) -> None:
    target.mkdir(parents=True, exist_ok=False)
    prompt_path = target / "prompt.txt"
    schema_path = target / "output_schema.json"
    raw_path = target / "raw_output.json"
    events_path = target / "events.jsonl"
    stderr_path = target / "stderr.txt"
    prompt_path.write_text(prompt, encoding="utf-8")
    write_json(schema_path, schema)
    with tempfile.TemporaryDirectory(prefix="grammar-kt-post-training-") as temporary:
        workspace = Path(temporary)
        subprocess.run(["git", "init", "-q", "-b", "main", str(workspace)], check=True)
        (workspace / "AGENTS.md").write_text(
            "Do not call tools or inspect files. Answer the user's data task directly and return only JSON matching the supplied schema.\n",
            encoding="utf-8",
        )
        command = [
            "codex",
            "exec",
            "--ignore-user-config",
            "--ephemeral",
            "--sandbox",
            "read-only",
            "--model",
            model,
            "--config",
            f'model_reasoning_effort="{reasoning_effort}"',
            "--json",
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(raw_path),
            "--cd",
            str(workspace),
            "-",
        ]
        started_utc = utc_now()
        start = time.monotonic()
        timed_out = False
        try:
            result = subprocess.run(
                command,
                input=prompt,
                text=True,
                capture_output=True,
                env={**os.environ, "NO_COLOR": "1"},
                timeout=timeout_seconds,
                check=False,
            )
            stdout, stderr, returncode = result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired as error:
            timed_out = True
            stdout = error.stdout or ""
            stderr = (error.stderr or "") + "\nmodel invocation timed out\n"
            if isinstance(stdout, bytes):
                stdout = stdout.decode(errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode(errors="replace")
            returncode = 124
        runtime = time.monotonic() - start
        finished_utc = utc_now()
    events_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    if not raw_path.exists():
        raw_path.write_text("", encoding="utf-8")
    write_json(
        target / "invocation.json",
        {
            "experiment": experiment,
            "command": command,
            "exact_shell_command": " ".join(command[:-1]) + " < prompt.txt",
            "model": model,
            "reasoning_effort": reasoning_effort,
            "model_snapshot_pinned": False,
            "decoding_parameters_pinned": False,
            "started_utc": started_utc,
            "finished_utc": finished_utc,
            "runtime_seconds": runtime,
            "returncode": returncode,
            "timed_out": timed_out,
            "codex_version": subprocess.check_output(
                ["codex", "--version"], text=True
            ).strip(),
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
    )
    if returncode:
        raise RuntimeError(f"{experiment} failed with return code {returncode}: {stderr[-1000:]}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("generation", "preference"))
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "experiments/post_training/configs/model_diagnostics_v0.json",
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=ROOT / "experiments/post_training/data/feasibility_v0",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "experiments/post_training/results/prompt_ablation_v0",
    )
    args = parser.parse_args()
    config = read_json(args.config)
    root = args.output / args.mode
    root.mkdir(parents=True, exist_ok=True)

    if args.mode == "generation":
        cases = generation_cases(args.data, int(config["generation_cases"]))
        write_json(root / "cases.json", cases)
        for condition in config["generation_conditions"]:
            target = root / condition
            run_codex(
                target,
                prompt=render_generation_prompt(condition, cases),
                schema=output_schema([row["case_id"] for row in cases], judge=False),
                model=config["model"],
                reasoning_effort=config["reasoning_effort"],
                timeout_seconds=int(config["timeout_seconds"]),
                experiment=f"generation:{condition}",
            )
    else:
        preferences = preference_sample(
            args.data, int(config["preference_judge_pairs_per_dimension"])
        )
        for order_name, reversed_order in (("seeded_order", False), ("reversed_order", True)):
            cases = judge_cases(
                preferences,
                seed=int(config["seed"]),
                reversed_order=reversed_order,
            )
            target = root / order_name
            target.mkdir(parents=True, exist_ok=False)
            write_json(target / "cases.json", cases)
            # run_codex owns its target, so use a child invocation directory.
            run_codex(
                target / "invocation",
                prompt=render_judge_prompt(cases),
                schema=output_schema([row["case_id"] for row in cases], judge=True),
                model=config["model"],
                reasoning_effort=config["reasoning_effort"],
                timeout_seconds=int(config["timeout_seconds"]),
                experiment=f"preference:{order_name}",
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
