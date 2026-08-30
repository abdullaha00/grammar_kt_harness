from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/experiments/verify_measurement_realism_programme.py"
CONFIG = (
    ROOT
    / "experiments/measurement_realism/verification/programme_evidence_config.json"
)
CONFIG_SCHEMA = CONFIG.with_name("programme_evidence_config.schema.json")
MANIFEST_SCHEMA = CONFIG.with_name("programme_evidence_manifest.schema.json")
SPEC = importlib.util.spec_from_file_location("programme_verification", SCRIPT)
assert SPEC and SPEC.loader
verification = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = verification
SPEC.loader.exec_module(verification)


def run_git(root: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def fixture_repository(tmp_path: Path) -> tuple[Path, Path, Path]:
    root = tmp_path / "repository"
    root.mkdir()
    run_git(root, "init", "-q")
    run_git(root, "config", "user.email", "fixture@example.invalid")
    run_git(root, "config", "user.name", "Fixture")

    baseline = root / "data/grammar_kt_full_v1"
    write(baseline / "manifest.json", '{"status":"FROZEN"}\n')
    run_git(root, "add", "data/grammar_kt_full_v1/manifest.json")
    run_git(root, "commit", "-q", "-m", "baseline")
    source_commit = run_git(root, "rev-parse", "HEAD")
    tree = run_git(root, "rev-parse", "HEAD:data/grammar_kt_full_v1")

    anchor = {
        "source_commit": source_commit,
        "git_tree_object": tree,
        "boundary": {
            "full_v1_mutated": False,
            "new_measurement_outputs_written_inside_full_v1": False,
        },
    }
    write(
        root / "experiments/measurement_realism/baseline_anchor.json",
        json.dumps(anchor) + "\n",
    )

    files = {
        "audit_evidence": "evidence/claim.json",
        "design_and_protocol": "evidence/design.md",
        "live_call_evidence": "evidence/live.jsonl",
        "retained_results": "evidence/result.json",
        "programme_reports": "evidence/report.md",
        "notebook_and_paper": "evidence/notebook.ipynb",
        "implementation_sources": "evidence/implementation.py",
    }
    write(root / files["audit_evidence"], '{"release_eligible":false}\n')
    write(root / files["design_and_protocol"], "frozen design\n")
    write(root / files["live_call_evidence"], '{"call":"frozen"}\n')
    write(root / files["retained_results"], '{"status":"complete"}\n')
    write(
        root / files["programme_reports"],
        "Measurement realism. No new dataset release. Controlled scenario.\n",
    )
    write(root / files["notebook_and_paper"], '{"cells":[],"metadata":{}}\n')
    write(root / files["implementation_sources"], "VALUE = 1\n")

    verification_dir = root / "experiments/measurement_realism/verification"
    verification_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(CONFIG_SCHEMA, verification_dir / CONFIG_SCHEMA.name)
    shutil.copy2(MANIFEST_SCHEMA, verification_dir / MANIFEST_SCHEMA.name)
    config_path = verification_dir / "programme_evidence_config.json"
    manifest_path = verification_dir / "programme_evidence_manifest.json"
    group_ids = [
        "audit_evidence",
        "design_and_protocol",
        "live_call_evidence",
        "retained_results",
        "programme_reports",
        "notebook_and_paper",
        "implementation_sources",
        "verification_sources",
    ]
    groups = [
        {
            "group_id": group_id,
            "purpose": f"fixture {group_id}",
            "paths": [files[group_id]],
        }
        for group_id in group_ids[:-1]
    ]
    groups.append(
        {
            "group_id": "verification_sources",
            "purpose": "fixture verification declarations",
            "paths": [
                "experiments/measurement_realism/verification/programme_evidence_config.json",
                "experiments/measurement_realism/verification/programme_evidence_config.schema.json",
                "experiments/measurement_realism/verification/programme_evidence_manifest.schema.json",
            ],
        }
    )
    config = {
        "schema_version": 1,
        "config_id": "fixture_allowlist",
        "status": "PRE_FREEZE_EXPLICIT_ALLOWLIST",
        "manifest_output": str(manifest_path.relative_to(root)),
        "manifest_schema": str(
            (verification_dir / MANIFEST_SCHEMA.name).relative_to(root)
        ),
        "protected_baseline": {
            "path": "data/grammar_kt_full_v1",
            "anchor_path": "experiments/measurement_realism/baseline_anchor.json",
            "source_commit": source_commit,
            "expected_git_tree_object": tree,
            "core_sha256": {
                "manifest.json": verification.sha256_file(baseline / "manifest.json")
            },
        },
        "dataset_release_decision": {
            "decision": "NO_NEW_DATASET_RELEASE",
            "candidate_path": "data/grammar_kt_measurement_v1",
            "must_not_exist": True,
            "basis": "fixture bank failed its release gate",
        },
        "required_group_ids": group_ids,
        "evidence_groups": groups,
        "exclusion_patterns": [
            "data/grammar_kt_full_v1/**",
            "data/grammar_kt_measurement_v1/**",
            "experiments/measurement_realism/worlds/controlled_instrument_v1/runs/**",
            "**/__pycache__/**",
            "**/*.pyc",
            "**/.analysis.incomplete*/**",
            "pipeline.txt",
            "tmp/**",
        ],
        "required_absent_paths": ["data/grammar_kt_measurement_v1"],
        "claim_assertions": [
            {
                "assertion_id": "not_release_eligible",
                "path": files["audit_evidence"],
                "json_pointer": "/release_eligible",
                "equals": False,
            }
        ],
        "text_contracts": [
            {
                "contract_id": "report_boundary",
                "path": files["programme_reports"],
                "required_casefold_phrases": [
                    "measurement realism",
                    "no new dataset release",
                    "controlled scenario",
                ],
            }
        ],
        "reconstruction_commands": [
            {
                "command_id": "fixture_verify",
                "kind": "verification",
                "purpose": "verify fixture evidence",
                "command": "python verifier.py verify",
            }
        ],
    }
    write(config_path, json.dumps(config, indent=2) + "\n")
    return root, config_path, manifest_path


def test_repository_config_is_schema_valid_and_explicitly_excludes_raw_data() -> None:
    config = verification.load_config(CONFIG, CONFIG_SCHEMA)
    groups = {group["group_id"]: group for group in config["evidence_groups"]}
    assert set(groups) == set(config["required_group_ids"])
    assert all(group["paths"] for group in groups.values())
    all_paths = {
        path for group in config["evidence_groups"] for path in group["paths"]
    }
    assert config["manifest_output"] not in all_paths
    assert not any(path.startswith("data/grammar_kt_full_v1/") for path in all_paths)
    assert not any(
        "/worlds/controlled_instrument_v1/runs/" in path for path in all_paths
    )
    assert "experiments/measurement_realism/worlds/controlled_instrument_v1/runs/**" in config[
        "exclusion_patterns"
    ]
    assert (
        "experiments/measurement_realism/design/bank_protocol/runs/"
        "matched_bank_v0_2_20260830/raw/**"
    ) in config["exclusion_patterns"]
    assert (
        "experiments/measurement_realism/design/bank_protocol/runs/"
        "matched_bank_v0_2_20260830/provenance/calls/**"
    ) in config["exclusion_patterns"]
    assert config["dataset_release_decision"]["decision"] == "NO_NEW_DATASET_RELEASE"
    all_paths = {
        path for group in config["evidence_groups"] for path in group["paths"]
    }
    assert "ACL/paper.bbl" in all_paths
    assert all(
        path in all_paths
        for path in (
            "experiments/measurement_realism/"
            "kc_induction_infrastructure_attempt_v1_provider_schema/"
            f"call_evidence/independent_{index:02d}/raw_output.txt"
            for index in range(1, 4)
        )
    )
    final_contract = next(
        contract
        for contract in config["text_contracts"]
        if contract["contract_id"] == "final_verification_programme_boundary"
    )
    assert "[final_full_suite_count_pending]" in final_contract[
        "forbidden_casefold_phrases"
    ]


def test_build_freeze_verify_and_detect_artifact_drift(tmp_path: Path) -> None:
    root, config_path, manifest_path = fixture_repository(tmp_path)
    assessment = verification.assess(
        root=root,
        config_path=config_path,
        config_schema_path=root
        / "experiments/measurement_realism/verification/programme_evidence_config.schema.json",
    )
    assert assessment.errors == []
    manifest = verification.build_manifest(
        root=root,
        config_path=config_path,
        config_schema_path=root
        / "experiments/measurement_realism/verification/programme_evidence_config.schema.json",
    )
    assert manifest["status"] == "PROGRAMME_EVIDENCE_VERIFIED"
    assert manifest["protected_full_v1"]["filesystem_clean_against_source_commit"]
    assert manifest["dataset_release_decision"] == {
        "decision": "NO_NEW_DATASET_RELEASE",
        "candidate_path": "data/grammar_kt_measurement_v1",
        "candidate_path_absent": True,
        "basis": "fixture bank failed its release gate",
    }
    assert not any(
        row["path"].startswith("data/grammar_kt_full_v1/")
        for row in manifest["artifacts"]
    )
    with pytest.raises(PermissionError, match="authorize-final-freeze"):
        verification.freeze_manifest(
            authorized=False,
            root=root,
            config_path=config_path,
            config_schema_path=root
            / "experiments/measurement_realism/verification/programme_evidence_config.schema.json",
        )
    verification.freeze_manifest(
        authorized=True,
        root=root,
        config_path=config_path,
        config_schema_path=root
        / "experiments/measurement_realism/verification/programme_evidence_config.schema.json",
    )
    assert manifest_path.is_file()
    verified = verification.verify_frozen_manifest(
        root=root,
        config_path=config_path,
        config_schema_path=root
        / "experiments/measurement_realism/verification/programme_evidence_config.schema.json",
    )
    assert verified["status"] == "PROGRAMME_EVIDENCE_MANIFEST_VERIFIED"

    write(root / "evidence/design.md", "changed design\n")
    with pytest.raises(ValueError, match="manifest drift"):
        verification.verify_frozen_manifest(
            root=root,
            config_path=config_path,
            config_schema_path=root
            / "experiments/measurement_realism/verification/programme_evidence_config.schema.json",
        )


def test_missing_deliverable_and_false_release_boundary_fail_readiness(
    tmp_path: Path,
) -> None:
    root, config_path, _ = fixture_repository(tmp_path)
    (root / "evidence/result.json").unlink()
    write(root / "evidence/claim.json", '{"release_eligible":true}\n')
    assessment = verification.assess(
        root=root,
        config_path=config_path,
        config_schema_path=root
        / "experiments/measurement_realism/verification/programme_evidence_config.schema.json",
    )
    assert not assessment.ready
    assert any("required evidence file missing: evidence/result.json" in error for error in assessment.errors)
    assert any("claim assertion not_release_eligible failed" in error for error in assessment.errors)
    with pytest.raises(verification.ReadinessError):
        verification.build_manifest(
            root=root,
            config_path=config_path,
            config_schema_path=root
            / "experiments/measurement_realism/verification/programme_evidence_config.schema.json",
        )


def test_forbidden_text_contract_marker_blocks_assessment(tmp_path: Path) -> None:
    root, config_path, _ = fixture_repository(tmp_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["text_contracts"][0]["forbidden_casefold_phrases"] = [
        "[final_pending]"
    ]
    write(config_path, json.dumps(config, indent=2) + "\n")
    report_path = root / config["text_contracts"][0]["path"]
    report_path.write_text(
        report_path.read_text(encoding="utf-8") + "[FINAL_PENDING]\n",
        encoding="utf-8",
    )

    assessment = verification.assess(
        root=root,
        config_path=config_path,
        config_schema_path=root
        / "experiments/measurement_realism/verification/programme_evidence_config.schema.json",
    )
    assert any("contains forbidden phrases" in error for error in assessment.errors)


def test_candidate_dataset_or_protected_baseline_mutation_fails(
    tmp_path: Path,
) -> None:
    root, config_path, _ = fixture_repository(tmp_path)
    write(root / "data/grammar_kt_measurement_v1/README.md", "not authorized\n")
    write(root / "data/grammar_kt_full_v1/manifest.json", "changed\n")
    assessment = verification.assess(
        root=root,
        config_path=config_path,
        config_schema_path=root
        / "experiments/measurement_realism/verification/programme_evidence_config.schema.json",
    )
    assert not assessment.ready
    assert any("dataset-release boundary failed" in error for error in assessment.errors)
    assert any("required-absent path exists" in error for error in assessment.errors)
    assert any("protected full-v1 verification failed" in error for error in assessment.errors)


def test_excluded_raw_run_cannot_enter_explicit_allowlist(tmp_path: Path) -> None:
    root, config_path, _ = fixture_repository(tmp_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    raw = (
        "experiments/measurement_realism/worlds/controlled_instrument_v1/"
        "runs/world__seed_1/observable.jsonl.gz"
    )
    write(root / raw, "raw\n")
    config["evidence_groups"][0]["paths"].append(raw)
    write(config_path, json.dumps(config, indent=2) + "\n")
    assessment = verification.assess(
        root=root,
        config_path=config_path,
        config_schema_path=root
        / "experiments/measurement_realism/verification/programme_evidence_config.schema.json",
    )
    assert any("allowlisted path violates exclusion" in error for error in assessment.errors)


def test_duplicate_artifact_paths_are_rejected(tmp_path: Path) -> None:
    root, config_path, _ = fixture_repository(tmp_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    duplicate = config["evidence_groups"][0]["paths"][0]
    config["evidence_groups"][1]["paths"].append(duplicate)
    write(config_path, json.dumps(config, indent=2) + "\n")
    assessment = verification.assess(
        root=root,
        config_path=config_path,
        config_schema_path=root
        / "experiments/measurement_realism/verification/programme_evidence_config.schema.json",
    )
    assert any("allowlisted more than once" in error for error in assessment.errors)
