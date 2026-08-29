from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from grammar_kt.io import read_jsonl
from scripts.curate_item_packaging import (
    ARCHIVE_RELATIVE,
    CORRECTION_JUDGMENTS_NAME,
    CORRECTION_MANIFEST_NAME,
    CURATED_CANDIDATES_NAME,
    EXPECTED_PLAN_SHA256,
    PLAN_NAME,
    load_frozen_plan,
    run_curation,
)


ROOT = Path(__file__).resolve().parents[1]
RETAINED = ROOT / "data/grammar_kt_medium_v1"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _copy_curation_fixture(target: Path) -> None:
    for relative in (
        "items/candidates.jsonl",
        "items/validation.jsonl",
        "items/selected_bank.jsonl",
        "items/validator_accepted.jsonl",
        "items/bank_summary.json",
        PLAN_NAME,
        "canonical/cells.jsonl",
        "manifest.json",
        "finalization_manifest.json",
    ):
        archived_source = RETAINED / ARCHIVE_RELATIVE / relative
        source = (
            archived_source
            if archived_source.is_file()
            else RETAINED / relative
        )
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    for relative in ("fold", "simulation", "kc", "kt", "evaluation"):
        path = target / relative
        path.mkdir(parents=True)
        (path / "stale.txt").write_text("old-bank derivative\n", encoding="utf-8")


def _passing_validator(prompt: str, **call):
    assert call["stage"] == "validation"
    return {
        "judgments": {
            name: {"passed": True, "note": "Deterministic curation fixture."}
            for name in call["input_data"]["criteria"]
        }
    }


def test_frozen_packaging_correction_revalidates_six_and_archives_stale_outputs(
    tmp_path: Path,
) -> None:
    _copy_curation_fixture(tmp_path)
    raw_candidates_hash = _sha256(tmp_path / "items/candidates.jsonl")
    raw_validation_hash = _sha256(tmp_path / "items/validation.jsonl")
    calls = []

    def counted_validator(prompt: str, **call):
        calls.append(call["call_key"])
        return _passing_validator(prompt, **call)

    result = run_curation(
        tmp_path,
        workers=2,
        validation_model="gpt-5.6-terra",
        reasoning_effort="medium",
        exact_command="fixture packaging correction",
        model_call=counted_validator,
    )

    assert result["status"] == "complete"
    assert len(calls) == 6
    assert set(calls) == {
        "candidate_cell_003_01",
        "candidate_cell_005_01",
        "candidate_cell_017_06",
        "candidate_cell_018_01",
        "candidate_cell_018_03",
        "candidate_cell_019_03",
    }
    assert len(read_jsonl(tmp_path / CURATED_CANDIDATES_NAME)) == 77
    assert len(read_jsonl(tmp_path / CORRECTION_JUDGMENTS_NAME)) == 6
    assert len(read_jsonl(tmp_path / "items/curated_validation.jsonl")) == 77
    assert len(read_jsonl(tmp_path / "items/selected_bank.jsonl")) == 46
    assert _sha256(tmp_path / "items/candidates.jsonl") == raw_candidates_hash
    assert _sha256(tmp_path / "items/validation.jsonl") == raw_validation_hash

    curated = {
        row["item_id"]: row
        for row in read_jsonl(tmp_path / CURATED_CANDIDATES_NAME)
    }
    assert sum(row["curation_metadata"]["corrected"] for row in curated.values()) == 6
    assert curated["candidate_cell_003_01"]["target_answer"] == (
        "Every morning, she walks the dog before breakfast."
    )
    assert curated["candidate_cell_005_01"]["accepted_answers"] == [
        "Turn on the light"
    ]
    assert curated["candidate_cell_017_06"]["target_answer"] == (
        "Nina was tired because she had not been sleeping well for several nights."
    )
    assert curated["candidate_cell_018_01"]["accepted_answers"] == [
        "She had been painting the fence for four hours",
        "Maya had been painting the fence for four hours",
    ]
    assert curated["candidate_cell_018_03"]["target_answer"] == (
        "At noon, Maya had been painting the fence for four hours."
    )
    assert curated["candidate_cell_018_03"]["accepted_answers"] == [
        "Maya had been painting the fence for four hours"
    ]
    assert curated["candidate_cell_019_03"]["accepted_answers"] == [
        "The fence was painted"
    ]

    archive = tmp_path / ARCHIVE_RELATIVE
    for relative in (
        "manifest.json",
        "finalization_manifest.json",
        "fold/stale.txt",
        "simulation/stale.txt",
        "kc/stale.txt",
        "kt/stale.txt",
        "evaluation/stale.txt",
        "items/selected_bank.jsonl",
    ):
        assert (archive / relative).exists()
    assert not (tmp_path / "finalization_manifest.json").exists()
    assert not (tmp_path / "fold").exists()
    assert json.loads((tmp_path / "manifest.json").read_text())["status"] == (
        "fixed_item_bank_complete"
    )

    def must_not_rejudge(prompt: str, **call):
        raise AssertionError("completed correction must not be recalled")

    replay = run_curation(
        tmp_path,
        workers=1,
        validation_model="gpt-5.6-terra",
        reasoning_effort="medium",
        exact_command="fixture replay",
        model_call=must_not_rejudge,
    )
    assert replay == result
    assert (tmp_path / CORRECTION_MANIFEST_NAME).is_file()


def test_packaging_plan_hash_and_raw_before_state_are_hard_guards(
    tmp_path: Path,
) -> None:
    _copy_curation_fixture(tmp_path)
    plan_path = tmp_path / PLAN_NAME
    plan = json.loads(plan_path.read_text())
    plan["corrections"][0]["changes"]["target_answer"]["after"] += " changed"
    plan_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="plan hash differs"):
        load_frozen_plan(plan_path, expected_sha256=EXPECTED_PLAN_SHA256)

    shutil.copyfile(RETAINED / PLAN_NAME, plan_path)
    candidate_path = tmp_path / "items/candidates.jsonl"
    rows = read_jsonl(candidate_path)
    rows[0]["prompt"] += " changed"
    candidate_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="raw candidate artifact changed"):
        run_curation(
            tmp_path,
            workers=1,
            validation_model="gpt-5.6-terra",
            reasoning_effort="medium",
            exact_command="fixture tamper",
            model_call=_passing_validator,
        )
