#!/usr/bin/env python3
"""Apply and revalidate the frozen Phase-6 answer-key packaging corrections.

This is deliberately a data-specific curation procedure, not an item generator.
It verifies six exact before/after edits, preserves the 77 raw candidates and
their original judgments, obtains six independent replacement judgments, then
rebuilds the fixed bank.  Any downstream artifacts based on the old bank are
archived before replacement bank artifacts are written.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from grammar_kt.io import (
    ModelCall,
    call_model,
    read_jsonl,
    read_text,
    read_yaml,
    write_json,
    write_jsonl,
)
from grammar_kt.validate_items import (
    answer_span_consistency,
    bank_summary,
    select_item_bank,
    validate_items,
)


PROTOCOL = "frozen_item_packaging_correction_v1"
CORRECTION_STATUS = "phase6_frozen_item_packaging_correction"
EXPECTED_PLAN_SHA256 = (
    "bbed7be77c2d326bd7133308ea22d637bed5de8d44cd4bb470a2421c4ebe0dc5"
)
EXPECTED_CORRECTION_COUNT = 6
EXPECTED_CANDIDATE_COUNT = 77

DEFAULT_DATASET = ROOT / "data/grammar_kt_medium_v1"
DEFAULT_MODEL = "gpt-5.6-terra"
DEFAULT_REASONING_EFFORT = "medium"
PLAN_NAME = "items/packaging_correction_plan.json"
CURATED_CANDIDATES_NAME = "items/curated_candidates.jsonl"
CORRECTION_JUDGMENTS_NAME = "items/packaging_correction_validation.jsonl"
CURATED_JUDGMENTS_NAME = "items/curated_validation.jsonl"
CORRECTION_MANIFEST_NAME = "items/packaging_correction_manifest.json"
ARCHIVE_MARKER_NAME = "items/packaging_correction_archive.json"
ARCHIVE_RELATIVE = Path(
    "superseded_pre_curation/2026-08-27_f36_packaging_correction"
)

VALIDATION_PROMPT_PATH = ROOT / "modules/items/validation/prompt.txt"
VALIDATION_CRITERIA_PATH = ROOT / "modules/items/validation/criteria.yaml"
GENERATION_DESIGN_PATH = ROOT / "modules/items/generation/design.yaml"

# Raw model evidence is intentionally absent. These are only artifacts derived
# from the old item package and therefore invalid once the curated bank changes.
STALE_DERIVED_PATHS = (
    "manifest.json",
    "finalization_manifest.json",
    "fold",
    "simulation",
    "kc",
    "kt",
    "evaluation",
    "selection_stability",
    "items/validator_accepted.jsonl",
    "items/selected_bank.jsonl",
    "items/bank_summary.json",
    "items/missing_cells.jsonl",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_frozen_plan(
    path: Path, *, expected_sha256: str = EXPECTED_PLAN_SHA256
) -> dict[str, Any]:
    """Verify the immutable plan before reading any proposed after value."""

    actual_sha256 = _sha256(path)
    if actual_sha256 != expected_sha256:
        raise ValueError(
            "packaging correction plan hash differs from the preregistered "
            f"hash: expected={expected_sha256}, actual={actual_sha256}"
        )
    plan = _read_json(path)
    if plan.get("protocol") != PROTOCOL:
        raise ValueError(f"unexpected packaging correction protocol: {plan}")
    corrections = plan.get("corrections", [])
    item_ids = [row.get("item_id") for row in corrections]
    if len(corrections) != EXPECTED_CORRECTION_COUNT:
        raise ValueError("the frozen plan must contain exactly six corrections")
    if len(item_ids) != len(set(item_ids)):
        raise ValueError("the frozen correction IDs must be unique")
    if set(row.get("audit_disposition") for row in corrections) - {
        "selected",
        "rejected",
    }:
        raise ValueError("each correction requires its audited bank disposition")
    for correction in corrections:
        changes = correction.get("changes", {})
        if not changes or set(changes) - {"target_answer", "accepted_answers"}:
            raise ValueError(f"invalid frozen correction fields: {correction}")
        for field, change in changes.items():
            if set(change) != {"before", "after"} or change["before"] == change["after"]:
                raise ValueError(
                    f"correction {correction['item_id']}/{field} lacks an exact change"
                )
    return plan


def make_curated_candidates(
    dataset_dir: Path, plan: dict[str, Any], *, plan_sha256: str
) -> list[dict[str, Any]]:
    """Apply only frozen edits and mark all rows as corrected or unchanged."""

    raw_path = dataset_dir / "items/candidates.jsonl"
    raw_validation_path = dataset_dir / "items/validation.jsonl"
    if _sha256(raw_path) != plan["raw_candidates_sha256"]:
        raise ValueError("raw candidate artifact changed after the correction freeze")
    if _sha256(raw_validation_path) != plan["raw_validation_sha256"]:
        raise ValueError("raw judgment artifact changed after the correction freeze")
    raw = read_jsonl(raw_path)
    if len(raw) != EXPECTED_CANDIDATE_COUNT:
        raise ValueError(
            f"expected {EXPECTED_CANDIDATE_COUNT} retained candidates, found {len(raw)}"
        )
    raw_ids = [row["item_id"] for row in raw]
    if len(raw_ids) != len(set(raw_ids)):
        raise ValueError("raw candidate IDs must be unique")
    correction_by_id = {row["item_id"]: row for row in plan["corrections"]}
    missing = set(correction_by_id) - set(raw_ids)
    if missing:
        raise ValueError(f"frozen correction IDs absent from raw candidates: {sorted(missing)}")
    selected_ids = {
        row["item_id"]
        for row in read_jsonl(dataset_dir / "items/selected_bank.jsonl")
    }
    raw_judgments = {
        row["item_id"]: row for row in read_jsonl(raw_validation_path)
    }
    for item_id, correction in correction_by_id.items():
        disposition = correction["audit_disposition"]
        if disposition == "selected" and item_id not in selected_ids:
            raise ValueError(f"frozen selected disposition differs for {item_id}")
        if disposition == "rejected" and (
            item_id in selected_ids or raw_judgments[item_id]["accepted"]
        ):
            raise ValueError(f"frozen rejected disposition differs for {item_id}")

    curated = []
    for raw_row in raw:
        row = copy.deepcopy(raw_row)
        correction = correction_by_id.get(row["item_id"])
        corrected_fields = []
        if correction:
            for field, change in correction["changes"].items():
                if raw_row.get(field) != change["before"]:
                    raise ValueError(
                        f"{row['item_id']}/{field} does not equal its frozen before value"
                    )
                row[field] = copy.deepcopy(change["after"])
                corrected_fields.append(field)
        row["curation_metadata"] = {
            "status": CORRECTION_STATUS if correction else "unchanged_raw_candidate",
            "protocol": PROTOCOL,
            "plan_sha256": plan_sha256,
            "source_artifact": "items/candidates.jsonl",
            "corrected": bool(correction),
            "corrected_fields": sorted(corrected_fields),
        }
        curated.append(row)

    # Exact field-level invariant: removing the one metadata field and restoring
    # planned values must reproduce every raw row and its original ordering.
    for raw_row, curated_row in zip(raw, curated, strict=True):
        restored = copy.deepcopy(curated_row)
        restored.pop("curation_metadata")
        correction = correction_by_id.get(raw_row["item_id"])
        if correction:
            for field, change in correction["changes"].items():
                if restored[field] != change["after"]:
                    raise AssertionError("curated after value was not retained")
                restored[field] = copy.deepcopy(change["before"])
        if restored != raw_row:
            raise AssertionError(
                f"unplanned candidate mutation detected: {raw_row['item_id']}"
            )
    write_jsonl(dataset_dir / CURATED_CANDIDATES_NAME, curated)
    if _sha256(raw_path) != plan["raw_candidates_sha256"]:
        raise AssertionError("writing curated candidates changed the raw artifact")
    return curated


def _parallel_completed(
    rows: list[dict[str, Any]],
    function: Callable[[dict[str, Any]], dict[str, Any]],
    workers: int,
):
    if workers < 1:
        raise ValueError("workers must be positive")
    if workers == 1:
        for row in rows:
            yield row, function(row)
        return
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(function, row): row for row in rows}
        for future in as_completed(futures):
            yield futures[future], future.result()


def validate_corrections(
    dataset_dir: Path,
    plan: dict[str, Any],
    curated: list[dict[str, Any]],
    *,
    plan_sha256: str,
    workers: int,
    validation_model: str,
    reasoning_effort: str,
    model_call: ModelCall = call_model,
) -> list[dict[str, Any]]:
    """Independently judge each corrected package exactly once, with resume."""

    if validation_model != plan["validation_model"]:
        raise ValueError("correction validation must use the frozen validator model")
    if reasoning_effort != plan["reasoning_effort"]:
        raise ValueError("correction validation must use the frozen reasoning effort")
    if _sha256(VALIDATION_PROMPT_PATH) != plan["validation_prompt_sha256"]:
        raise ValueError("active validation prompt changed after the correction freeze")
    if _sha256(VALIDATION_CRITERIA_PATH) != plan["validation_criteria_sha256"]:
        raise ValueError("active validation criteria changed after the correction freeze")

    cells = read_jsonl(dataset_dir / "canonical/cells.jsonl")
    by_id = {row["item_id"]: row for row in curated}
    planned_ids = [row["item_id"] for row in plan["corrections"]]
    corrected = [by_id[item_id] for item_id in planned_ids]
    inconsistent = {
        row["item_id"]: answer_span_consistency(row)[1]
        for row in corrected
        if not answer_span_consistency(row)[0]
    }
    if inconsistent:
        raise ValueError(
            "a frozen after-value still fails answer-span consistency; no model "
            f"calls made: {inconsistent}"
        )

    judgment_path = dataset_dir / CORRECTION_JUDGMENTS_NAME
    retained = read_jsonl(judgment_path) if judgment_path.exists() else []
    retained_by_id: dict[str, dict[str, Any]] = {}
    for row in retained:
        item_id = row.get("item_id")
        metadata = row.get("validation_metadata", {})
        if item_id not in planned_ids or item_id in retained_by_id:
            raise ValueError(f"invalid retained correction judgment: {item_id}")
        expected = {
            "status": CORRECTION_STATUS,
            "protocol": PROTOCOL,
            "plan_sha256": plan_sha256,
            "model": validation_model,
            "reasoning_effort": reasoning_effort,
        }
        if any(metadata.get(name) != value for name, value in expected.items()):
            raise ValueError(
                f"retained correction judgment settings differ for {item_id}"
            )
        retained_by_id[item_id] = row
    unjudged = [row for row in corrected if row["item_id"] not in retained_by_id]
    prompt = read_text(VALIDATION_PROMPT_PATH)
    criteria = read_yaml(VALIDATION_CRITERIA_PATH)

    def judge(candidate: dict[str, Any]) -> dict[str, Any]:
        started = time.monotonic()
        try:
            _, rows = validate_items(
                [candidate],
                cells,
                prompt,
                criteria,
                model=validation_model,
                reasoning_effort=reasoning_effort,
                model_call=model_call,
                evidence_dir=dataset_dir / "items/packaging_correction_evidence",
            )
            judgment = rows[0]
            error_type = None
            error = None
        except Exception as caught:  # terminal evidence prevents silent recall
            judgment = {
                "item_id": candidate["item_id"],
                "deterministic_checks": {},
                "judgments": {},
                "accepted": False,
                "rejection_stage": "validator_call_or_output_failure",
            }
            error_type = type(caught).__name__
            error = str(caught)
        judgment["validation_metadata"] = {
            "status": CORRECTION_STATUS,
            "protocol": PROTOCOL,
            "plan_sha256": plan_sha256,
            "source_artifact": CURATED_CANDIDATES_NAME,
            "model": validation_model,
            "reasoning_effort": reasoning_effort,
            "runtime_seconds": time.monotonic() - started,
            "error_type": error_type,
            "error": error,
        }
        return judgment

    order = {item_id: index for index, item_id in enumerate(planned_ids)}
    for completed, (candidate, judgment) in enumerate(
        _parallel_completed(unjudged, judge, workers), 1
    ):
        retained_by_id[candidate["item_id"]] = judgment
        rows = sorted(retained_by_id.values(), key=lambda row: order[row["item_id"]])
        write_jsonl(judgment_path, rows)
        print(
            f"packaging-correction judgments completed: {completed}/{len(unjudged)}",
            flush=True,
        )
    judgments = sorted(retained_by_id.values(), key=lambda row: order[row["item_id"]])
    if len(judgments) != EXPECTED_CORRECTION_COUNT:
        raise ValueError(
            "all six corrected packages require a terminal independent judgment"
        )
    return judgments


def archive_stale_downstream(
    dataset_dir: Path, *, plan_sha256: str
) -> dict[str, Any]:
    """Move every old-bank derivative to a fixed, recoverable archive."""

    marker_path = dataset_dir / ARCHIVE_MARKER_NAME
    archive_dir = dataset_dir / ARCHIVE_RELATIVE
    if marker_path.exists():
        marker = _read_json(marker_path)
        if (
            marker.get("protocol") != PROTOCOL
            or marker.get("plan_sha256") != plan_sha256
            or marker.get("archive_path") != str(ARCHIVE_RELATIVE)
        ):
            raise ValueError("retained pre-curation archive marker is incompatible")
        return marker

    archived = []
    for relative_text in STALE_DERIVED_PATHS:
        relative = Path(relative_text)
        source = dataset_dir / relative
        destination = archive_dir / relative
        if source.exists() and destination.exists():
            raise ValueError(
                f"both stale source and archive destination exist: {relative}"
            )
        if source.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(destination))
            archived.append(relative_text)
        elif destination.exists():  # resume after an interrupted archive pass
            archived.append(relative_text)
    marker = {
        "status": "stale_pre_curation_artifacts_archived",
        "protocol": PROTOCOL,
        "plan_sha256": plan_sha256,
        "archive_path": str(ARCHIVE_RELATIVE),
        "archived_paths": archived,
        "raw_artifacts_preserved_in_place": [
            "items/candidates.jsonl",
            "items/validation.jsonl",
            "items/generation_attempts.jsonl",
            "items/generation_evidence",
            "items/validation_evidence",
        ],
    }
    write_json(marker_path, marker)
    return marker


def _load_pre_curation_manifest(dataset_dir: Path) -> dict[str, Any]:
    current = dataset_dir / "manifest.json"
    archived = dataset_dir / ARCHIVE_RELATIVE / "manifest.json"
    # Once the archive exists it is the immutable pre-curation source. This
    # also makes a no-call replay rebuild derived summaries without nesting a
    # curation manifest inside itself.
    if archived.exists():
        return _read_json(archived)
    if current.exists():
        return _read_json(current)
    raise FileNotFoundError("neither current nor archived item-bank manifest exists")


def rebuild_curated_bank(
    dataset_dir: Path,
    plan: dict[str, Any],
    curated: list[dict[str, Any]],
    correction_judgments: list[dict[str, Any]],
    *,
    plan_sha256: str,
    exact_command: str,
) -> dict[str, Any]:
    """Override six judgments, archive stale derivatives, and rebuild the bank."""

    raw_judgments = read_jsonl(dataset_dir / "items/validation.jsonl")
    raw_by_id = {row["item_id"]: row for row in raw_judgments}
    if len(raw_by_id) != len(raw_judgments) or set(raw_by_id) != {
        row["item_id"] for row in curated
    }:
        raise ValueError("raw candidate and judgment inventories must match exactly")
    correction_by_id = {row["item_id"]: row for row in correction_judgments}
    planned_ids = {row["item_id"] for row in plan["corrections"]}
    if set(correction_by_id) != planned_ids:
        raise ValueError("corrected judgment inventory does not match the frozen plan")

    active_judgments = [
        copy.deepcopy(correction_by_id.get(row["item_id"], row))
        for row in raw_judgments
    ]
    active_by_id = {row["item_id"]: row for row in active_judgments}
    validator_accepted = [
        row for row in curated if active_by_id[row["item_id"]]["accepted"]
    ]
    selected = select_item_bank(
        validator_accepted, read_yaml(GENERATION_DESIGN_PATH)
    )
    cells = read_jsonl(dataset_dir / "canonical/cells.jsonl")
    cell_ids = {row["cell_id"] for row in cells}
    covered_ids = {row["cell_id"] for row in selected}
    unknown = covered_ids - cell_ids
    missing_ids = cell_ids - covered_ids
    if unknown:
        raise ValueError(f"curated selected bank has unknown cells: {sorted(unknown)}")

    base_manifest = _load_pre_curation_manifest(dataset_dir)
    archived_selected = dataset_dir / ARCHIVE_RELATIVE / "items/selected_bank.jsonl"
    pre_selected_path = (
        archived_selected
        if archived_selected.exists()
        else dataset_dir / "items/selected_bank.jsonl"
    )
    pre_selected_ids = (
        {row["item_id"] for row in read_jsonl(pre_selected_path)}
        if pre_selected_path.exists()
        else set()
    )
    archive = archive_stale_downstream(dataset_dir, plan_sha256=plan_sha256)

    write_jsonl(dataset_dir / CURATED_JUDGMENTS_NAME, active_judgments)
    write_jsonl(dataset_dir / "items/validator_accepted.jsonl", validator_accepted)
    write_jsonl(dataset_dir / "items/selected_bank.jsonl", selected)
    write_jsonl(
        dataset_dir / "items/missing_cells.jsonl",
        [row for row in cells if row["cell_id"] in missing_ids],
    )
    summary = bank_summary(
        curated,
        validator_accepted,
        active_judgments,
        cells,
        selected_items=selected,
    )
    summary.update(
        {
            "raw_candidates": len(curated),
            "packaging_corrections": EXPECTED_CORRECTION_COUNT,
            "correction_judgments": len(correction_judgments),
            "corrected_candidates_accepted": sum(
                bool(row["accepted"]) for row in correction_judgments
            ),
            "raw_candidate_artifact_preserved": True,
            "raw_validation_artifact_preserved": True,
        }
    )
    write_json(dataset_dir / "items/bank_summary.json", summary)

    original_acceptance = {
        item_id: bool(raw_by_id[item_id]["accepted"]) for item_id in sorted(planned_ids)
    }
    corrected_acceptance = {
        item_id: bool(correction_by_id[item_id]["accepted"])
        for item_id in sorted(planned_ids)
    }
    selected_ids = {row["item_id"] for row in selected}
    outcomes = [
        {
            "item_id": item_id,
            "original_accepted": original_acceptance[item_id],
            "corrected_accepted": corrected_acceptance[item_id],
            "selected_before_curation": item_id in pre_selected_ids,
            "selected_after_curation": item_id in selected_ids,
        }
        for item_id in sorted(planned_ids)
    ]

    manifest = copy.deepcopy(base_manifest)
    prior_command = manifest.get("exact_command")
    manifest.update(
        {
            "status": (
                "fixed_item_bank_complete"
                if not missing_ids
                else "packaging_correction_complete_item_bank_incomplete"
            ),
            "artifact_scope": "source_through_curated_fixed_item_bank",
            "item_summary": summary,
            "uncovered_cell_ids": sorted(missing_ids),
            "item_packaging_correction": {
                "protocol": PROTOCOL,
                "status": "complete",
                "plan": PLAN_NAME,
                "plan_sha256": plan_sha256,
                "corrected_item_count": EXPECTED_CORRECTION_COUNT,
                "independent_revalidation_count": len(correction_judgments),
                "original_item_construction_exact_command": prior_command,
                "raw_candidates_sha256": plan["raw_candidates_sha256"],
                "raw_validation_sha256": plan["raw_validation_sha256"],
                "curated_candidates_sha256": _sha256(
                    dataset_dir / CURATED_CANDIDATES_NAME
                ),
                "curated_validation_sha256": _sha256(
                    dataset_dir / CURATED_JUDGMENTS_NAME
                ),
                "selected_bank_sha256": _sha256(
                    dataset_dir / "items/selected_bank.jsonl"
                ),
                "archive": archive,
            },
            "exact_command": exact_command,
        }
    )
    manifest.setdefault("inputs", {})["packaging_correction_plan"] = PLAN_NAME
    manifest.setdefault("item_method", {})["packaging_correction"] = {
        "scope": "answer-key packaging only",
        "prompts_cells_and_item_ids_unchanged": True,
        "six_corrected_records_independently_revalidated": True,
        "correction_judgments_override_originals_only_in_curated_artifacts": True,
    }
    write_json(dataset_dir / "manifest.json", manifest)

    correction_manifest = {
        "status": "complete",
        "protocol": PROTOCOL,
        "plan": PLAN_NAME,
        "plan_sha256": plan_sha256,
        "model": plan["validation_model"],
        "reasoning_effort": plan["reasoning_effort"],
        "raw_candidates_sha256": _sha256(
            dataset_dir / "items/candidates.jsonl"
        ),
        "raw_validation_sha256": _sha256(
            dataset_dir / "items/validation.jsonl"
        ),
        "curated_candidates_sha256": _sha256(
            dataset_dir / CURATED_CANDIDATES_NAME
        ),
        "correction_judgments_sha256": _sha256(
            dataset_dir / CORRECTION_JUDGMENTS_NAME
        ),
        "curated_validation_sha256": _sha256(
            dataset_dir / CURATED_JUDGMENTS_NAME
        ),
        "selected_bank_sha256": _sha256(
            dataset_dir / "items/selected_bank.jsonl"
        ),
        "raw_candidate_count": len(curated),
        "corrected_item_count": EXPECTED_CORRECTION_COUNT,
        "correction_outcomes": outcomes,
        "selected_bank_items_before": len(pre_selected_ids),
        "selected_bank_items_after": len(selected),
        "covered_cells_after": len(covered_ids),
        "uncovered_cell_ids_after": sorted(missing_ids),
        "archive": archive,
        "exact_command": exact_command,
    }
    write_json(dataset_dir / CORRECTION_MANIFEST_NAME, correction_manifest)
    if (
        _sha256(dataset_dir / "items/candidates.jsonl")
        != plan["raw_candidates_sha256"]
        or _sha256(dataset_dir / "items/validation.jsonl")
        != plan["raw_validation_sha256"]
    ):
        raise AssertionError("curation changed a raw generation/judgment artifact")
    return correction_manifest


def run_curation(
    dataset_dir: Path,
    *,
    workers: int,
    validation_model: str,
    reasoning_effort: str,
    exact_command: str,
    model_call: ModelCall = call_model,
    expected_plan_sha256: str = EXPECTED_PLAN_SHA256,
) -> dict[str, Any]:
    plan_path = dataset_dir / PLAN_NAME
    plan = load_frozen_plan(plan_path, expected_sha256=expected_plan_sha256)
    completed_path = dataset_dir / CORRECTION_MANIFEST_NAME
    if completed_path.exists():
        completed = _read_json(completed_path)
        if (
            completed.get("status") != "complete"
            or completed.get("protocol") != PROTOCOL
            or completed.get("plan_sha256") != expected_plan_sha256
        ):
            raise ValueError("existing correction manifest is incompatible")
        if (
            _sha256(dataset_dir / "items/candidates.jsonl")
            != plan["raw_candidates_sha256"]
            or _sha256(dataset_dir / "items/validation.jsonl")
            != plan["raw_validation_sha256"]
            or _sha256(dataset_dir / CURATED_CANDIDATES_NAME)
            != completed["curated_candidates_sha256"]
            or _sha256(dataset_dir / "items/selected_bank.jsonl")
            != completed["selected_bank_sha256"]
        ):
            raise ValueError("completed packaging-correction artifacts changed")
        return rebuild_curated_bank(
            dataset_dir,
            plan,
            read_jsonl(dataset_dir / CURATED_CANDIDATES_NAME),
            read_jsonl(dataset_dir / CORRECTION_JUDGMENTS_NAME),
            plan_sha256=expected_plan_sha256,
            exact_command=completed["exact_command"],
        )

    curated = make_curated_candidates(
        dataset_dir, plan, plan_sha256=expected_plan_sha256
    )
    judgments = validate_corrections(
        dataset_dir,
        plan,
        curated,
        plan_sha256=expected_plan_sha256,
        workers=workers,
        validation_model=validation_model,
        reasoning_effort=reasoning_effort,
        model_call=model_call,
    )
    return rebuild_curated_bank(
        dataset_dir,
        plan,
        curated,
        judgments,
        plan_sha256=expected_plan_sha256,
        exact_command=exact_command,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply and independently revalidate six frozen item corrections."
    )
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--validation-model", default=DEFAULT_MODEL)
    parser.add_argument("--reasoning-effort", default=DEFAULT_REASONING_EFFORT)
    arguments = parser.parse_args()
    judgment_path = arguments.dataset_dir / CORRECTION_JUDGMENTS_NAME
    retained_count = len(read_jsonl(judgment_path)) if judgment_path.exists() else 0
    if retained_count < EXPECTED_CORRECTION_COUNT and shutil.which("codex") is None:
        parser.error("codex CLI is unavailable for correction revalidation")
    return arguments


def main() -> int:
    arguments = parse_args()
    dataset_dir = arguments.dataset_dir.resolve()
    manifest = run_curation(
        dataset_dir,
        workers=arguments.workers,
        validation_model=arguments.validation_model,
        reasoning_effort=arguments.reasoning_effort,
        exact_command=" ".join([sys.executable, *sys.argv]),
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
