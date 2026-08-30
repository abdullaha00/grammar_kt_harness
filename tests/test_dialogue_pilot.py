from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / "experiments/measurement_realism/dialogue_pilot"
BUILDER = PILOT / "build_plan.py"
ANALYZER = PILOT / "analyze_dialogue_pilot.py"

FORMATS = [
    "constrained_cloze",
    "sentence_transformation",
    "contextual_production",
    "dialogue_completion",
    "open_dialogue",
]


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        check=check,
        capture_output=True,
        text=True,
    )


def test_dialogue_plan_replays_and_uses_frozen_outcome_free_strata(tmp_path: Path) -> None:
    output_dir = tmp_path / "replay"
    result = run(str(BUILDER), "--output-dir", str(output_dir))
    status = json.loads(result.stdout)
    assert status == {
        "cells": 4,
        "live_model_calls_made": 0,
        "planned_opportunities": 20,
        "status": "FROZEN_NO_CALL_CONTINUUM_PLAN",
    }

    for name in ("selected_cells.json", "generation_requests.jsonl", "manifest.json"):
        assert (output_dir / name).read_bytes() == (PILOT / name).read_bytes()

    plan = json.loads((output_dir / "selected_cells.json").read_text())
    assert [row["cell_id"] for row in plan["selected_cells"]] == [
        "gc_d15de8b5658bd6a5",
        "gc_2d6eb4f93cba4c6b",
        "gc_08d90a35b669ed28",
        "gc_4634bf1b005f7724",
    ]
    assert [row["q_cardinality"] for row in plan["selected_cells"]] == [1, 2, 3, 3]
    assert [row["pilot_stratum"] for row in plan["selected_cells"]] == [
        "simple",
        "multi_kc",
        "question",
        "rare_complex",
    ]
    assert plan["format_order"] == FORMATS
    assert plan["counts"] == {
        "cells": 4,
        "formats_per_cell": 5,
        "planned_critic_judgments": 100,
        "planned_opportunities": 20,
    }
    assert plan["selection_method"]["outcomes_read"] is False
    assert plan["selection_method"]["private_oracle_trajectories_read"] is False

    requests = [
        json.loads(line)
        for line in (output_dir / "generation_requests.jsonl").read_text().splitlines()
    ]
    assert len(requests) == 4
    assert all(request["live_call_authorized"] is False for request in requests)
    assert all(
        [slot["format"] for slot in request["formats"]] == FORMATS
        for request in requests
    )

    manifest = json.loads((output_dir / "manifest.json").read_text())
    assert manifest["live_model_calls_made"] == 0
    assert manifest["human_judgments_collected"] == 0
    assert manifest["full_v1_mutated"] is False
    assert "private mastery trajectories" in manifest["forbidden_inputs"]


def synthetic_judgments(plan: dict) -> list[dict]:
    profiles = {
        "constrained_cloze": {
            "task": "pass",
            "context": "minor_concern",
            "interaction": "major_concern",
            "platform": "minor_concern",
            "determinacy": "determinate",
            "coverage": "complete",
            "lexical": "low",
            "attribution": "clear",
            "lower_bound": 1,
            "incidental": [],
            "shortcut": False,
        },
        "sentence_transformation": {
            "task": "pass",
            "context": "minor_concern",
            "interaction": "minor_concern",
            "platform": "minor_concern",
            "determinacy": "determinate",
            "coverage": "complete",
            "lexical": "low",
            "attribution": "clear",
            "lower_bound": 1,
            "incidental": [],
            "shortcut": False,
        },
        "contextual_production": {
            "task": "pass",
            "context": "pass",
            "interaction": "minor_concern",
            "platform": "pass",
            "determinacy": "bounded_multiple",
            "coverage": "minor_gap",
            "lexical": "moderate",
            "attribution": "partial",
            "lower_bound": 2,
            "incidental": ["discourse_pragmatics"],
            "shortcut": False,
        },
        "dialogue_completion": {
            "task": "pass",
            "context": "pass",
            "interaction": "pass",
            "platform": "pass",
            "determinacy": "bounded_multiple",
            "coverage": "minor_gap",
            "lexical": "moderate",
            "attribution": "partial",
            "lower_bound": 2,
            "incidental": ["discourse_pragmatics"],
            "shortcut": False,
        },
        "open_dialogue": {
            "task": "minor_concern",
            "context": "pass",
            "interaction": "pass",
            "platform": "pass",
            "determinacy": "materially_ambiguous",
            "coverage": "major_gap",
            "lexical": "high",
            "attribution": "weak",
            "lower_bound": 4,
            "incidental": ["discourse_pragmatics", "lexical_choice"],
            "shortcut": True,
        },
    }
    rows: list[dict] = []
    for cell in plan["selected_cells"]:
        for slot in cell["opportunity_slots"]:
            profile = profiles[slot["format"]]
            for role in plan["critic_roles"]:
                rows.append(
                    {
                        "judgment_schema": "dialogue_continuum_critic_v1",
                        "critic_id": f"fixture_{role}",
                        "critic_role": role,
                        "family_id": cell["family_id"],
                        "opportunity_id": slot["opportunity_id"],
                        "format": slot["format"],
                        "ratings": {
                            "task_comprehensibility": profile["task"],
                            "context_naturalness": profile["context"],
                            "interaction_naturalness": profile["interaction"],
                            "platform_plausibility": profile["platform"],
                            "answer_determinacy": profile["determinacy"],
                            "accepted_response_coverage": profile["coverage"],
                            "lexical_nuisance": profile["lexical"],
                            "kc_attribution": profile["attribution"],
                        },
                        "plausible_response_lower_bound": profile["lower_bound"],
                        "incidental_grammar_operations": profile["incidental"],
                        "target_avoiding_shortcut": profile["shortcut"],
                        "primary_concern": "Synthetic test fixture, not evidence.",
                    }
                )
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def test_analyzer_keeps_ecology_and_precision_separate(tmp_path: Path) -> None:
    plan = json.loads((PILOT / "selected_cells.json").read_text())
    judgments_path = tmp_path / "judgments.jsonl"
    output_path = tmp_path / "analysis.json"
    write_jsonl(judgments_path, synthetic_judgments(plan))

    result = run(
        str(ANALYZER),
        "--judgments",
        str(judgments_path),
        "--output",
        str(output_path),
    )
    status = json.loads(result.stdout)
    assert status["opportunities"] == 20
    assert status["judgments"] == 100
    assert status["scalar_realism_score_computed"] is False

    analysis = json.loads(output_path.read_text())
    assert analysis["scale"]["planned_opportunities"] == 20
    assert analysis["scale"]["observed_opportunities"] == 20
    assert analysis["scale"]["judgments"] == 100
    assert analysis["evidence_boundary"]["scalar_realism_score_computed"] is False
    assert analysis["evidence_boundary"]["weighted_composite_computed"] is False

    open_summary = analysis["by_format"]["open_dialogue"]
    assert open_summary["opportunities"] == 4
    assert open_summary["judgments"] == 20
    assert open_summary["rating_distributions"]["answer_determinacy"] == {
        "materially_ambiguous": 20
    }
    assert open_summary["plausible_response_lower_bound"]["mean"] == 4.0
    assert open_summary["incidental_grammar"]["operation_counts"] == {
        "discourse_pragmatics": 20,
        "lexical_choice": 20,
    }

    open_deltas = analysis["matched_deltas_vs_constrained_cloze"]["open_dialogue"]
    assert open_deltas["matched_family_role_pairs"] == 20
    assert open_deltas["separate_metric_deltas_target_minus_reference"][
        "determinacy_risk"
    ]["mean"] == 2.0
    assert open_deltas["separate_metric_deltas_target_minus_reference"][
        "interaction_naturalness_risk"
    ]["mean"] == -2.0

    checks = analysis["continuum_direction_checks"]
    assert checks["determinacy_risk"]["fraction_monotone"] == 1.0
    assert checks["interaction_naturalness_risk"]["fraction_monotone"] == 1.0
    assert checks["incidental_grammar_count"]["fraction_monotone"] == 1.0
    assert all(value["count"] == 0 for value in analysis["role_disagreement"].values())


def test_analyzer_rejects_incomplete_or_non_boolean_evidence(tmp_path: Path) -> None:
    plan = json.loads((PILOT / "selected_cells.json").read_text())
    rows = synthetic_judgments(plan)

    incomplete_path = tmp_path / "incomplete.jsonl"
    write_jsonl(incomplete_path, rows[:-1])
    incomplete = run(
        str(ANALYZER),
        "--judgments",
        str(incomplete_path),
        "--output",
        str(tmp_path / "incomplete.json"),
        check=False,
    )
    assert incomplete.returncode != 0
    assert "missing 1 opportunity/role judgments" in incomplete.stderr

    rows[0]["target_avoiding_shortcut"] = 1
    invalid_path = tmp_path / "invalid.jsonl"
    write_jsonl(invalid_path, rows)
    invalid = run(
        str(ANALYZER),
        "--judgments",
        str(invalid_path),
        "--output",
        str(tmp_path / "invalid.json"),
        check=False,
    )
    assert invalid.returncode != 0
    assert "invalid shortcut flag" in invalid.stderr
