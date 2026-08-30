from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/experiments/analyze_measurement_realism_bank_failure.py"
PROGRAMME_CONFIG = (
    ROOT
    / "experiments/measurement_realism/verification/programme_evidence_config.json"
)
RUN = (
    ROOT
    / "experiments/measurement_realism/design/bank_protocol/runs/"
    "matched_bank_v0_2_20260830"
)
SPEC = importlib.util.spec_from_file_location("bank_failure_analysis", SCRIPT)
assert SPEC and SPEC.loader
analysis = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(analysis)


def test_exact_rank_handles_duplicates_and_independent_rows() -> None:
    assert analysis.exact_rank([]) == 0
    assert analysis.exact_rank([[1, 0], [1, 0]]) == 1
    assert analysis.exact_rank([[1, 0], [0, 1], [1, 1]]) == 2


def test_negative_result_replays_exact_headlines_without_composite_score() -> None:
    result = analysis.analyze()
    assert result["status"] == "FAILED_PREREGISTERED_BANK_FREEZE_GATE"
    assert result["execution_integrity"] == {
        "call_records": 178,
        "calls_by_stage_and_status": [
            {"calls": 106, "stage": "generation", "status": "complete"},
            {"calls": 48, "stage": "solver", "status": "complete"},
            {"calls": 24, "stage": "validation", "status": "complete"},
        ],
        "critic_family_role_records": 90,
        "curation_decisions": 106,
        "deterministic_check_records": 106,
        "generation_outputs": 106,
        "rejection_rows": 101,
        "scientific_run_technical_failures": 0,
        "solver_attempt_records": 712,
    }
    assert result["pass_funnel"]["overall"] == {
        "candidate_requests_preregistered": 114,
        "candidates_evaluated": 106,
        "critic_family_gate_pass": 5,
        "deterministic_gate_pass": 89,
        "families_accepted": 5,
        "families_accepted_at_candidate": 5,
        "families_exhausted_after_round_3": 33,
        "families_preregistered": 38,
        "solver_family_gate_pass": 30,
    }
    geometry = result["accepted_family_geometry"]
    assert geometry["accepted_family_count"] == 5
    assert geometry["accepted_item_slots"] == 20
    assert geometry["accepted_seen_q_rank"] == 3
    assert geometry["accepted_all_regimes_q_rank"] == 4
    assert geometry["active_kcs_covered"] == 6
    assert len(geometry["accepted_family_examples"]) == 5
    assert result["release_gate_failure"]["freeze_permitted"] is False
    assert result["scientific_boundaries"][
        "numeric_average_or_composite_realism_score"
    ] is False
    assert "realism_score" not in result


def test_preflights_are_excluded_as_infrastructure_failures() -> None:
    result = analysis.analyze()
    provider = result["preflight_failures"]["provider_schema_preflight"]
    assert provider["attempts"] == 3
    assert provider["technical_failures"] == 3
    assert provider["parsed_outputs"] == 0
    assert provider["scientific_judgments"] == 0
    assert provider["offending_protocol_id_schema"] == {
        "const": "measurement_realism_matched_bank_v0"
    }
    reconstruction = result["preflight_failures"][
        "dialogue_reconstruction_preflight"
    ]
    assert reconstruction["calls"] == 1
    assert reconstruction["failed_checks"] == [
        "dialogue_completion:canonical_reconstruction"
    ]
    assert reconstruction["old_config_declared_speaker_label_exclusion"] is False
    assert (
        reconstruction["scientific_run_declared_speaker_label_exclusion"] is True
    )
    assert reconstruction["scientific_judgments"] == 0


def test_packaged_analysis_and_manifest_verify_exactly() -> None:
    expected = analysis.analyze()
    stored = json.loads(
        (RUN / "analysis/failure_analysis.json").read_text(encoding="utf-8")
    )
    assert stored == expected
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "verify"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    verified = json.loads(completed.stdout)
    assert verified["status"] == "PASS"
    assert all(verified["checks"].values())


def test_every_negative_result_source_file_is_allowlisted_and_not_ignored() -> None:
    records = analysis.source_records(
        analysis.DEFAULT_RUN,
        analysis.DEFAULT_PROVIDER_PREFLIGHT,
        analysis.DEFAULT_RECONSTRUCTION_PREFLIGHT,
    )
    source_paths = {row["path"] for row in records["files"]}
    for tree in records["trees"]:
        tree_root = ROOT / tree["path"]
        source_paths.update(
            path.relative_to(ROOT).as_posix()
            for path in tree_root.rglob("*")
            if path.is_file()
        )

    config = json.loads(PROGRAMME_CONFIG.read_text(encoding="utf-8"))
    allowlisted = {
        path
        for group in config["evidence_groups"]
        for path in group["paths"]
    }
    assert len(source_paths) == 1095
    assert source_paths <= allowlisted

    ignored = subprocess.run(
        ["git", "check-ignore", "--no-index", "--stdin"],
        cwd=ROOT,
        input="\n".join(sorted(source_paths)) + "\n",
        capture_output=True,
        text=True,
        check=False,
    )
    assert ignored.returncode == 1
    assert ignored.stdout == ""

    excluded_v0_2 = [
        RUN / "raw/generation/example/attempt_01/raw_output.txt",
        RUN / "provenance/calls/example.json",
    ]
    for path in excluded_v0_2:
        result = subprocess.run(
            ["git", "check-ignore", "--no-index", "--quiet", "--", str(path)],
            cwd=ROOT,
            check=False,
        )
        assert result.returncode == 0
