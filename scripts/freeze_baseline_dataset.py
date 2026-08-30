#!/usr/bin/env python3
"""Freeze or verify the full-v1 observable and private learner streams.

This runner is the terminal step of Layer-A dataset construction.  It accepts
only the fixed item bank, explicit generator K*, deterministic Q*, structural
grammar regimes, the declared simulation config, and the outcome-free
simulator pilot.  It does not run KC discovery, choose K-hat, fit KT models, or
read downstream predictions.
"""

from __future__ import annotations

import argparse
import json
import platform
import shlex
import subprocess
import sys
import zlib
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from grammar_kt.baseline_simulation import (
    OBSERVABLE_FIELDS,
    ORACLE_FIELDS,
    iter_baseline_rows,
    validate_baseline_config,
)
from grammar_kt.dataset_freeze import (
    artifact_inventory,
    file_sha256,
    freeze_copy,
    freeze_json,
    freeze_text,
    semantic_sha256,
    verify_artifact_inventory,
    verify_baseline_streams,
    write_baseline_streams,
)
from grammar_kt.grammar_regimes import design_grammar_regimes
from grammar_kt.io import read_jsonl, read_yaml
from grammar_kt.measurement_gate import (
    build_measurement_bundle,
    verify_measurement_artifacts,
)


DATASET_ID = "grammar_kt_full_v1"
FREEZE_PLAN_ID = "grammar_kt_full_v1_baseline_freeze_plan_v1"
MANIFEST_ID = "grammar_kt_full_v1_frozen_baseline_manifest_v1"
EXPECTED_PILOT_ID = "baseline_simulator_assumptions_v1"

DEFAULT_DATASET_DIR = ROOT / "data/grammar_kt_full_v1"
DEFAULT_PILOT_PATH = (
    ROOT
    / "reports/baseline/artifacts/full_simulator_v1/pilot_seed_20260829.json"
)
DEFAULT_SIMULATION_CONFIG = ROOT / "modules/simulation/baseline.yaml"
DEFAULT_GRAMMAR_SCHEMA = ROOT / "modules/grammar/canonical/schema.yaml"
DEFAULT_REGIME_DESIGN = ROOT / "modules/simulation/grammar_regimes_full_v1.yaml"
DEFAULT_MEASUREMENT_DESIGN = ROOT / "modules/kcs/generator/design.yaml"

CELLS_RELATIVE = Path("grammar/cells.jsonl")
RELATIONS_RELATIVE = Path("grammar/source_cell_relations.jsonl")
KCS_RELATIVE = Path("kcs.jsonl")
ITEMS_RELATIVE = Path("items/items.jsonl")
REGIMES_RELATIVE = Path("grammar/regime_assignments.jsonl")
REGIME_AUDIT_RELATIVE = Path("provenance/grammar_regimes/audit.json")
CURATION_RELATIVE = Path("provenance/items/curation.json")
Q_DENSE_RELATIVE = Path("q_matrix.csv")
Q_SPARSE_RELATIVE = Path("oracle/q_matrix_sparse.jsonl")
Q_AUDIT_RELATIVE = Path("provenance/measurement/audit.json")
Q_MANIFEST_RELATIVE = Path("provenance/measurement/manifest.json")
INTERACTIONS_RELATIVE = Path("interactions.jsonl.gz")
ORACLE_RELATIVE = Path("oracle/learner_truth.jsonl.gz")
FREEZE_PLAN_RELATIVE = Path("provenance/simulation/freeze_plan.json")
FROZEN_CONFIG_RELATIVE = Path("provenance/simulation/baseline.yaml")
FROZEN_PILOT_RELATIVE = Path("provenance/simulation/pilot.json")
README_RELATIVE = Path("README.md")
MANIFEST_RELATIVE = Path("manifest.json")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _git_revision() -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _git_worktree_state() -> dict[str, Any]:
    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return {
            "available": False,
            "clean": None,
            "porcelain_entry_count": None,
            "porcelain_semantic_sha256": None,
        }
    rows = result.stdout.splitlines()
    return {
        "available": True,
        "clean": not rows,
        "porcelain_entry_count": len(rows),
        # Retain drift evidence without copying unrelated filenames into the
        # scientific dataset.
        "porcelain_semantic_sha256": semantic_sha256(result.stdout),
    }


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


def _require_file(path: Path, label: str) -> None:
    if not path.is_file() or path.is_symlink() or path.stat().st_size == 0:
        raise FileNotFoundError(f"{label} is absent or invalid: {path}")


def _regime_mapping(rows: list[dict[str, Any]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for index, row in enumerate(rows):
        cell_id = row.get("cell_id")
        regime = row.get("grammar_regime")
        if not isinstance(cell_id, str) or not isinstance(regime, str):
            raise ValueError(f"grammar regime row {index} lacks cell_id/regime")
        if cell_id in result:
            raise ValueError(f"duplicate grammar regime assignment: {cell_id}")
        result[cell_id] = regime
    return result


def _condition_from_config(config: dict[str, Any]) -> dict[str, Any]:
    acquisition = config["schedule"]["acquisition"]
    return {
        "aggregation": config["response"]["aggregation"],
        "learning_rule": config["learning"]["rule"],
        "schedule_mode": "q_balanced",
        "target_opportunities_per_seen_kc": acquisition[
            "target_opportunities_per_seen_kc"
        ],
        "exhaustive_passes": None,
        "learning_rate": float(config["learning"]["rate"]),
        "beta_alpha": float(config["initial_mastery"]["alpha"]),
        "beta_beta": float(config["initial_mastery"]["beta"]),
        "guess": float(config["response"]["guess"]),
        "slip": float(config["response"]["slip"]),
    }


def _verify_pilot(
    pilot: dict[str, Any],
    *,
    pilot_path: Path,
    paths: dict[str, Path],
    items: list[dict[str, Any]],
    kcs: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    if pilot.get("pilot_id") != EXPECTED_PILOT_ID:
        raise ValueError("unexpected baseline simulator pilot ID")
    boundary = pilot.get("scientific_boundary", {})
    if (
        boundary.get("prediction_or_kc_recovery_used") is not False
        or boundary.get("inputs_not_accepted") is None
    ):
        raise ValueError("simulator pilot scientific boundary is missing or changed")
    pilot_inputs = pilot.get("inputs", {})
    expected_hashes = {
        "items_file_sha256": paths["items"],
        "generator_kcs_file_sha256": paths["kcs"],
        "q_matrix_file_sha256": paths["q_dense"],
        "grammar_regimes_file_sha256": paths["regimes"],
    }
    for field, path in expected_hashes.items():
        if pilot_inputs.get(field) != file_sha256(path):
            raise ValueError(f"simulator pilot input hash differs: {field}")
    if pilot_inputs.get("item_count") != len(items):
        raise ValueError("simulator pilot item count differs from fixed bank")
    if pilot_inputs.get("generator_kc_count") != len(kcs):
        raise ValueError("simulator pilot K* count differs")
    if pilot.get("protocol", {}).get("seed") != config["seed"]:
        raise ValueError("simulator pilot seed differs from the baseline seed")

    desired = _condition_from_config(config)
    matching = [
        row
        for row in pilot.get("conditions", [])
        if all(row.get(name) == value for name, value in desired.items())
    ]
    if len(matching) != 1:
        raise ValueError("active baseline condition is absent or duplicated in the pilot")
    selected = matching[0]
    if (
        selected.get("admissible") is not True
        or selected.get("simulation_gates", {}).get("passed") is not True
        or selected.get("analytical_aggregation_gates_passed") is not True
        or selected.get("condition_id") not in pilot.get("admissible_condition_ids", [])
    ):
        raise ValueError("active baseline condition did not pass the frozen pilot gates")
    return {
        "path": _display_path(pilot_path),
        "sha256": file_sha256(pilot_path),
        "pilot_id": pilot["pilot_id"],
        "condition_id": selected["condition_id"],
        "condition": desired,
        "pilot_learners": pilot["protocol"]["learners"],
        "pilot_seed": pilot["protocol"]["seed"],
        "all_declared_gates_passed": True,
    }


def preflight_full_v1(
    dataset_dir: Path,
    *,
    pilot_path: Path,
    simulation_config_path: Path,
    grammar_schema_path: Path,
    regime_design_path: Path,
    measurement_design_path: Path,
) -> dict[str, Any]:
    """Verify every frozen Layer-A input before any learner row is written."""

    paths = {
        "cells": dataset_dir / CELLS_RELATIVE,
        "relations": dataset_dir / RELATIONS_RELATIVE,
        "kcs": dataset_dir / KCS_RELATIVE,
        "items": dataset_dir / ITEMS_RELATIVE,
        "regimes": dataset_dir / REGIMES_RELATIVE,
        "regime_audit": dataset_dir / REGIME_AUDIT_RELATIVE,
        "curation": dataset_dir / CURATION_RELATIVE,
        "q_dense": dataset_dir / Q_DENSE_RELATIVE,
        "q_sparse": dataset_dir / Q_SPARSE_RELATIVE,
        "q_audit": dataset_dir / Q_AUDIT_RELATIVE,
        "q_manifest": dataset_dir / Q_MANIFEST_RELATIVE,
        "simulation_config": simulation_config_path,
        "grammar_schema": grammar_schema_path,
        "regime_design": regime_design_path,
        "measurement_design": measurement_design_path,
        "pilot": pilot_path,
    }
    for name, path in paths.items():
        _require_file(path, name.replace("_", " "))
    input_hashes = {name: file_sha256(path) for name, path in paths.items()}

    cells = read_jsonl(paths["cells"])
    items = read_jsonl(paths["items"])
    kcs = read_jsonl(paths["kcs"])
    q_rows = read_jsonl(paths["q_sparse"])
    regime_rows = read_jsonl(paths["regimes"])
    regimes = _regime_mapping(regime_rows)
    config = read_yaml(paths["simulation_config"])
    validate_baseline_config(config)

    curation = _read_json(paths["curation"])
    if curation.get("status") != "PASS":
        raise ValueError("full-v1 item curation has not passed")
    if curation.get("selected_items") != len(items):
        raise ValueError("curation selected-item count differs from the fixed bank")
    if curation.get("covered_cells") != len(cells):
        raise ValueError("curation does not cover every canonical GrammarCell")
    if curation.get("final_bank_sha256") != semantic_sha256(items):
        raise ValueError("fixed item bank differs from curation provenance")

    expected_regimes = design_grammar_regimes(
        read_yaml(paths["grammar_schema"]),
        cells,
        generator_kcs=kcs,
        items=items,
        design=read_yaml(paths["regime_design"]),
    )
    if regime_rows != expected_regimes["assignments"]:
        raise ValueError("grammar regime assignments differ from the active design")
    retained_regime_audit = _read_json(paths["regime_audit"])
    if (
        retained_regime_audit != expected_regimes["audit"]
        or retained_regime_audit.get("status") != "PASS"
        or "item_support_not_audited" in retained_regime_audit.get("limitations", [])
    ):
        raise ValueError("grammar regime audit is incomplete or changed")

    measurement_bundle = build_measurement_bundle(
        cells,
        items,
        kcs,
        read_yaml(paths["measurement_design"]),
        grammar_regime_by_cell=regime_rows,
    )
    if measurement_bundle["audit"]["status"] != "PASS":
        raise ValueError("mandatory K*/Q* measurement gate did not pass")
    if q_rows != measurement_bundle["q_rows"]:
        raise ValueError("sparse Q* differs from deterministic K* projection")
    verify_measurement_artifacts(
        measurement_bundle,
        dense_q_matrix_path=paths["q_dense"],
        sparse_q_matrix_path=paths["q_sparse"],
        audit_path=paths["q_audit"],
        manifest_path=paths["q_manifest"],
    )

    pilot = _read_json(paths["pilot"])
    pilot_summary = _verify_pilot(
        pilot,
        pilot_path=paths["pilot"],
        paths=paths,
        items=items,
        kcs=kcs,
        config=config,
    )
    changed_during_preflight = sorted(
        name
        for name, path in paths.items()
        if file_sha256(path) != input_hashes[name]
    )
    if changed_during_preflight:
        raise ValueError(
            "scientific inputs changed during preflight: "
            f"{changed_during_preflight}"
        )
    return {
        "paths": paths,
        "input_hashes": input_hashes,
        "cells": cells,
        "items": items,
        "kcs": kcs,
        "q_rows": q_rows,
        "regime_rows": regime_rows,
        "regimes": regimes,
        "config": config,
        "curation": curation,
        "regime_audit": retained_regime_audit,
        "measurement_audit": measurement_bundle["audit"],
        "pilot": pilot_summary,
    }


def _implementation_hashes() -> dict[str, str]:
    files = [
        ROOT / "src/grammar_kt/baseline_simulation.py",
        ROOT / "src/grammar_kt/dataset_freeze.py",
        Path(__file__).resolve(),
    ]
    return {_display_path(path): file_sha256(path) for path in files}


def _scientific_inputs(preflight: dict[str, Any]) -> dict[str, dict[str, str]]:
    return {
        name: {
            "path": _display_path(path),
            "sha256": preflight["input_hashes"][name],
        }
        for name, path in sorted(preflight["paths"].items())
    }


def _plan_core(preflight: dict[str, Any]) -> dict[str, Any]:
    scientific_inputs = _scientific_inputs(preflight)
    return {
        "plan_id": FREEZE_PLAN_ID,
        "dataset_id": DATASET_ID,
        "status": "FROZEN_BEFORE_LEARNER_SIMULATION",
        "scientific_inputs": scientific_inputs,
        "scientific_inputs_semantic_sha256": semantic_sha256(scientific_inputs),
        "simulation_id": preflight["config"]["simulation_id"],
        "simulation_seed": preflight["config"]["seed"],
        "simulation_config_semantic_sha256": semantic_sha256(preflight["config"]),
        "pilot_decision": preflight["pilot"],
        "outputs": {
            "observable_interactions": INTERACTIONS_RELATIVE.as_posix(),
            "private_learner_truth": ORACLE_RELATIVE.as_posix(),
        },
        "scientific_boundary": {
            "inputs_consumed": [
                "fixed_items",
                "generator_k_star",
                "true_q_star",
                "grammar_regimes",
                "simulation_config",
                "outcome_free_simulator_pilot",
            ],
            "learner_outcomes_read_before_simulation": False,
            "discovered_kcs_read": False,
            "kt_results_read": False,
            "holdout_outcomes_read": False,
        },
    }


def _assert_input_hashes_unchanged(preflight: dict[str, Any]) -> None:
    changed = sorted(
        name
        for name, path in preflight["paths"].items()
        if file_sha256(path) != preflight["input_hashes"][name]
    )
    if changed:
        raise ValueError(f"scientific inputs changed after preflight: {changed}")


def _verify_retained_plan(
    dataset_dir: Path,
    preflight: dict[str, Any],
    *,
    require_current_implementation: bool,
) -> dict[str, Any]:
    plan_path = dataset_dir / FREEZE_PLAN_RELATIVE
    _require_file(plan_path, "baseline simulation freeze plan")
    plan = _read_json(plan_path)
    core = _plan_core(preflight)
    expected_keys = set(core) | {
        "implementation_sha256",
        "git_revision_at_freeze",
        "git_worktree_at_freeze",
        "original_exact_command",
    }
    if set(plan) != expected_keys:
        raise ValueError("frozen baseline simulation plan schema changed")
    retained_core = {key: plan.get(key) for key in core}
    if retained_core != core:
        raise ValueError("frozen baseline simulation plan changed")
    if semantic_sha256(plan["scientific_inputs"]) != plan.get(
        "scientific_inputs_semantic_sha256"
    ):
        raise ValueError("freeze-plan scientific-input digest differs")
    _assert_input_hashes_unchanged(preflight)
    implementation = plan.get("implementation_sha256")
    if (
        not isinstance(implementation, dict)
        or not implementation
        or (
            require_current_implementation
            and implementation != _implementation_hashes()
        )
    ):
        raise ValueError("freeze-plan implementation hashes differ")
    if not isinstance(plan.get("original_exact_command"), str) or not plan[
        "original_exact_command"
    ]:
        raise ValueError("freeze plan lacks the exact original command")
    worktree = plan.get("git_worktree_at_freeze")
    if not isinstance(worktree, dict) or set(worktree) != {
        "available",
        "clean",
        "porcelain_entry_count",
        "porcelain_semantic_sha256",
    }:
        raise ValueError("freeze plan lacks worktree-state provenance")
    revision = plan.get("git_revision_at_freeze")
    if revision is not None and (not isinstance(revision, str) or not revision):
        raise ValueError("freeze plan has invalid code-revision provenance")
    return plan


def _freeze_plan(
    dataset_dir: Path,
    preflight: dict[str, Any],
    *,
    exact_command: str,
) -> dict[str, Any]:
    _assert_input_hashes_unchanged(preflight)
    plan = {
        **_plan_core(preflight),
        "implementation_sha256": _implementation_hashes(),
        "git_revision_at_freeze": _git_revision(),
        "git_worktree_at_freeze": _git_worktree_state(),
        "original_exact_command": exact_command,
    }
    plan_path = dataset_dir / FREEZE_PLAN_RELATIVE
    if plan_path.exists():
        return _verify_retained_plan(
            dataset_dir,
            preflight,
            require_current_implementation=True,
        )
    freeze_json(plan_path, plan, "baseline simulation freeze plan")
    return plan


def _readme(
    preflight: dict[str, Any],
    stream_summary: dict[str, Any],
    plan: dict[str, Any],
) -> str:
    config = preflight["config"]
    counts = preflight["measurement_audit"]["counts"]
    regime_counts = preflight["regime_audit"]["counts"]
    exact_command = plan["original_exact_command"]
    return f"""# Grammar-KT full dataset v1

This is the frozen Layer-A Grammar-KT baseline. It contains {counts['canonical_cells']}
canonical English GrammarCells, {counts['generator_kcs']} declared synthetic
generator KCs, {counts['items']} fixed learner-facing items, a deterministic
true Q-matrix, and {stream_summary['rows']:,} observable response events from
{stream_summary['learners']:,} simulated learners.

The scientific objects remain distinct:

```text
GrammarCell != generator K* != downstream discovered K-hat
```

K* and Q* are controlled truth only inside the declared synthetic world. They
are not claims about human cognitive decomposition. Automatic item validation
is not human pedagogical gold, simulator parameters are not human estimates,
and the English study does not establish cross-lingual empirical validity.

## Core artifacts

```text
grammar/cells.jsonl                     canonical linguistic structures
grammar/source_cell_relations.jsonl     auditable source-to-cell relations
kcs.jsonl                               frozen generator KC inventory K*
items/items.jsonl                       fixed learner-facing item bank
q_matrix.csv                            dense true item-to-KC mapping Q*
grammar/regime_assignments.jsonl        seen/generalisation regimes
interactions.jsonl.gz                   observable learner event stream
oracle/q_matrix_sparse.jsonl            sparse auditable Q* projection
oracle/learner_truth.jsonl.gz            private simulator trajectories
manifest.json                           hashes, counts, and reconstruction record
```

The structural grammar split contains {regime_counts['seen_cells']} seen,
{regime_counts['unseen_combination_cells']} unseen-combination, and
{regime_counts['unseen_value_cells']} unseen-value cells. Acquisition presents
seen items only. A terminal all-bank probe does not update mastery.

## Observable interactions

Every JSONL row has exactly:

```text
{' '.join(OBSERVABLE_FIELDS)}
```

`correct` is integer 0/1. During acquisition, `pass_index` is the item-local
exposure index. During probes, it is the probe-repeat index. The composite
`learner_id + sequence_index` is the stable event key. Ordinary KT does not
need `oracle/learner_truth.jsonl.gz`.

The private oracle has exactly:

```text
{' '.join(ORACLE_FIELDS)}
```

It records active K*, mastery before/after, the weakest-link aggregate, true
response probability, and response draw. Keep it hidden from ordinary KT and
KC-discovery inputs; use it only for controlled evaluation.

## Frozen simulator

- simulation ID: `{config['simulation_id']}`
- seed: `{config['seed']}`
- initial mastery: `Beta({config['initial_mastery']['alpha']}, {config['initial_mastery']['beta']})`
- response aggregation: minimum/weakest-link
- guess/slip: `{config['response']['guess']}` / `{config['response']['slip']}`
- learning: all active KCs, opportunity-based rate `{config['learning']['rate']}`
- forgetting and item difficulty: none
- acquisition target: at least `{config['schedule']['acquisition']['target_opportunities_per_seen_kc']}` opportunities per seen KC
- pilot condition: `{preflight['pilot']['condition_id']}`

## Reconstruction and verification

The LLM-backed source, normalisation, item-generation, validation, rescue, and
packaging-correction evidence is retained under `provenance/`. Deterministic
construction from the frozen item/KC inputs is verified with:

```bash
.venv/bin/python scripts/build_true_q_matrix.py \\
  --cells data/grammar_kt_full_v1/grammar/cells.jsonl \\
  --items data/grammar_kt_full_v1/items/items.jsonl \\
  --kcs data/grammar_kt_full_v1/kcs.jsonl \\
  --design modules/kcs/generator/design.yaml \\
  --regimes data/grammar_kt_full_v1/grammar/regime_assignments.jsonl \\
  --dense-q-matrix data/grammar_kt_full_v1/q_matrix.csv \\
  --sparse-q-matrix data/grammar_kt_full_v1/oracle/q_matrix_sparse.jsonl \\
  --audit data/grammar_kt_full_v1/provenance/measurement/audit.json \\
  --manifest data/grammar_kt_full_v1/provenance/measurement/manifest.json \\
  --verify-only

.venv/bin/python scripts/freeze_baseline_dataset.py \\
  --dataset-dir data/grammar_kt_full_v1 \\
  --pilot reports/baseline/artifacts/full_simulator_v1/pilot_seed_20260829.json \\
  --verify-only
```

Original stream-freeze invocation:

```text
{exact_command}
```

Gzip uses an empty embedded filename, compression level 9, and `mtime=0`.
`manifest.json` records both compressed-byte hashes and uncompressed canonical
JSONL content hashes. Downstream experiments must treat this directory as
immutable and write their hypotheses and results elsewhere.
"""


def _manifest(
    dataset_dir: Path,
    preflight: dict[str, Any],
    stream_summary: dict[str, Any],
    plan: dict[str, Any],
) -> dict[str, Any]:
    inventory = artifact_inventory(dataset_dir)
    config = preflight["config"]
    return {
        "manifest_id": MANIFEST_ID,
        "dataset_id": DATASET_ID,
        "version": "1",
        "status": "FROZEN_BASELINE_COMPLETE",
        "scientific_layers": {
            "linguistic_truth": "grammar/cells.jsonl",
            "synthetic_generator_truth": [
                "kcs.jsonl",
                "q_matrix.csv",
            ],
            "observable_data": [
                "items/items.jsonl",
                "interactions.jsonl.gz",
            ],
            "private_oracle": "oracle/learner_truth.jsonl.gz",
            "downstream_hypotheses_included": False,
        },
        "scale": {
            "source_relations": len(read_jsonl(preflight["paths"]["relations"])),
            "canonical_grammar_cells": len(preflight["cells"]),
            "generator_kcs": len(preflight["kcs"]),
            "items": len(preflight["items"]),
            "q_edges": preflight["measurement_audit"]["counts"]["q_edges"],
            "learners": stream_summary["learners"],
            "interactions": stream_summary["rows"],
        },
        "grammar_regimes": preflight["regime_audit"]["counts"],
        "simulation": {
            "simulation_id": config["simulation_id"],
            "seed": config["seed"],
            "config_semantic_sha256": semantic_sha256(config),
            "pilot": preflight["pilot"],
            "stream_summary": stream_summary,
        },
        "scientific_boundary": {
            "generator_kcs_frozen_before_responses": True,
            "q_star_frozen_before_responses": True,
            "item_bank_frozen_before_responses": True,
            "learner_outcomes_used_to_construct_k_star_or_q_star": False,
            "discovered_kcs_or_kt_results_read": False,
            "private_oracle_required_for_ordinary_kt": False,
        },
        "reproducibility": {
            "freeze_plan": FREEZE_PLAN_RELATIVE.as_posix(),
            "freeze_plan_sha256": file_sha256(
                dataset_dir / FREEZE_PLAN_RELATIVE
            ),
            "git_revision_at_freeze": plan["git_revision_at_freeze"],
            "implementation_sha256": plan["implementation_sha256"],
            "python": platform.python_version(),
            "numpy": np.__version__,
            "zlib_compile": zlib.ZLIB_VERSION,
            "zlib_runtime": zlib.ZLIB_RUNTIME_VERSION,
            "original_exact_command": plan["original_exact_command"],
            "verification_command": (
                ".venv/bin/python scripts/freeze_baseline_dataset.py "
                "--dataset-dir data/grammar_kt_full_v1 "
                "--pilot reports/baseline/artifacts/full_simulator_v1/"
                "pilot_seed_20260829.json --verify-only"
            ),
        },
        "artifact_inventory": inventory,
        "artifact_inventory_semantic_sha256": semantic_sha256(inventory),
    }


def _verify_frozen_declaration_copies(
    dataset_dir: Path, preflight: dict[str, Any]
) -> None:
    pairs = (
        (
            preflight["paths"]["simulation_config"],
            dataset_dir / FROZEN_CONFIG_RELATIVE,
            "frozen simulation config",
        ),
        (
            preflight["paths"]["pilot"],
            dataset_dir / FROZEN_PILOT_RELATIVE,
            "frozen simulator pilot",
        ),
    )
    for source, frozen, label in pairs:
        _require_file(frozen, label)
        if file_sha256(source) != file_sha256(frozen):
            raise ValueError(f"{label} differs from its scientific input")


def _verify_manifest_claims(
    dataset_dir: Path,
    manifest: dict[str, Any],
    preflight: dict[str, Any],
    stream_summary: dict[str, Any],
    plan: dict[str, Any],
) -> None:
    expected = _manifest(dataset_dir, preflight, stream_summary, plan)
    ignored_runtime = {"python", "numpy", "zlib_compile", "zlib_runtime"}
    actual_reproducibility = manifest.get("reproducibility")
    if not isinstance(actual_reproducibility, dict):
        raise ValueError("frozen dataset manifest lacks reproducibility metadata")
    for field in ignored_runtime:
        if not isinstance(actual_reproducibility.get(field), str) or not (
            actual_reproducibility[field]
        ):
            raise ValueError(f"manifest reproducibility field is invalid: {field}")
    actual_core = {
        key: value for key, value in manifest.items() if key != "reproducibility"
    }
    expected_core = {
        key: value for key, value in expected.items() if key != "reproducibility"
    }
    actual_reproducibility_core = {
        key: value
        for key, value in actual_reproducibility.items()
        if key not in ignored_runtime
    }
    expected_reproducibility_core = {
        key: value
        for key, value in expected["reproducibility"].items()
        if key not in ignored_runtime
    }
    if (
        actual_core != expected_core
        or actual_reproducibility_core != expected_reproducibility_core
    ):
        raise ValueError("frozen dataset manifest claims differ from reconstruction")


def _verify_complete_dataset(
    dataset_dir: Path, preflight: dict[str, Any]
) -> dict[str, Any]:
    manifest_path = dataset_dir / MANIFEST_RELATIVE
    _require_file(manifest_path, "frozen dataset manifest")
    manifest = _read_json(manifest_path)
    if (
        manifest.get("manifest_id") != MANIFEST_ID
        or manifest.get("status") != "FROZEN_BASELINE_COMPLETE"
    ):
        raise ValueError("unexpected or incomplete frozen dataset manifest")
    plan = _verify_retained_plan(
        dataset_dir,
        preflight,
        require_current_implementation=True,
    )
    _verify_frozen_declaration_copies(dataset_dir, preflight)
    retained_summary = manifest.get("simulation", {}).get("stream_summary")
    if not isinstance(retained_summary, dict):
        raise ValueError("frozen dataset manifest lacks a stream summary")
    summary = verify_baseline_streams(
        dataset_dir / INTERACTIONS_RELATIVE,
        dataset_dir / ORACLE_RELATIVE,
        items=preflight["items"],
        q_rows=preflight["q_rows"],
        grammar_regime_by_cell=preflight["regimes"],
        config=preflight["config"],
        expected_summary=retained_summary,
        expected_row_pairs=iter_baseline_rows(
            preflight["items"],
            preflight["kcs"],
            preflight["q_rows"],
            preflight["regimes"],
            preflight["config"],
            seed=int(preflight["config"]["seed"]),
        ),
    )
    verify_artifact_inventory(dataset_dir, manifest["artifact_inventory"])
    _verify_manifest_claims(dataset_dir, manifest, preflight, summary, plan)
    if semantic_sha256(manifest["artifact_inventory"]) != manifest.get(
        "artifact_inventory_semantic_sha256"
    ):
        raise ValueError("manifest artifact-inventory digest differs")
    return manifest


def freeze_full_v1_dataset(
    dataset_dir: Path,
    *,
    pilot_path: Path,
    simulation_config_path: Path = DEFAULT_SIMULATION_CONFIG,
    grammar_schema_path: Path = DEFAULT_GRAMMAR_SCHEMA,
    regime_design_path: Path = DEFAULT_REGIME_DESIGN,
    measurement_design_path: Path = DEFAULT_MEASUREMENT_DESIGN,
    verify_only: bool = False,
    exact_command: str = "direct Python call",
) -> dict[str, Any]:
    """Freeze the baseline once, or stream-verify an already frozen dataset."""

    dataset_dir = dataset_dir.resolve()
    preflight = preflight_full_v1(
        dataset_dir,
        pilot_path=pilot_path.resolve(),
        simulation_config_path=simulation_config_path.resolve(),
        grammar_schema_path=grammar_schema_path.resolve(),
        regime_design_path=regime_design_path.resolve(),
        measurement_design_path=measurement_design_path.resolve(),
    )
    manifest_path = dataset_dir / MANIFEST_RELATIVE
    if manifest_path.exists():
        return _verify_complete_dataset(dataset_dir, preflight)
    if verify_only:
        raise FileNotFoundError("--verify-only requires a frozen dataset manifest")

    plan_path = dataset_dir / FREEZE_PLAN_RELATIVE
    if not plan_path.exists():
        preexisting_outputs = [
            relative.as_posix()
            for relative in (
                INTERACTIONS_RELATIVE,
                ORACLE_RELATIVE,
                FROZEN_CONFIG_RELATIVE,
                FROZEN_PILOT_RELATIVE,
                README_RELATIVE,
            )
            if (dataset_dir / relative).exists()
        ]
        if preexisting_outputs:
            raise ValueError(
                "simulation outputs exist before the freeze plan: "
                f"{preexisting_outputs}"
            )
    plan = _freeze_plan(dataset_dir, preflight, exact_command=exact_command)
    freeze_copy(
        preflight["paths"]["simulation_config"],
        dataset_dir / FROZEN_CONFIG_RELATIVE,
        "simulation config copy",
    )
    freeze_copy(
        preflight["paths"]["pilot"],
        dataset_dir / FROZEN_PILOT_RELATIVE,
        "simulator pilot copy",
    )
    config = preflight["config"]
    stream_summary = write_baseline_streams(
        dataset_dir / INTERACTIONS_RELATIVE,
        dataset_dir / ORACLE_RELATIVE,
        iter_baseline_rows(
            preflight["items"],
            preflight["kcs"],
            preflight["q_rows"],
            preflight["regimes"],
            config,
            seed=int(config["seed"]),
        ),
        items=preflight["items"],
        q_rows=preflight["q_rows"],
        grammar_regime_by_cell=preflight["regimes"],
        config=config,
    )
    freeze_text(
        dataset_dir / README_RELATIVE,
        _readme(preflight, stream_summary, plan),
        "dataset README",
    )
    # The stream can take long enough for a concurrent edit to matter.  Do not
    # let the final inventory describe different scientific bytes from those
    # loaded before simulation.
    plan = _verify_retained_plan(
        dataset_dir,
        preflight,
        require_current_implementation=True,
    )
    _verify_frozen_declaration_copies(dataset_dir, preflight)
    manifest = _manifest(dataset_dir, preflight, stream_summary, plan)
    freeze_json(manifest_path, manifest, "frozen dataset manifest")
    return _verify_complete_dataset(dataset_dir, preflight)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET_DIR)
    parser.add_argument("--pilot", type=Path, default=DEFAULT_PILOT_PATH)
    parser.add_argument(
        "--simulation-config", type=Path, default=DEFAULT_SIMULATION_CONFIG
    )
    parser.add_argument("--grammar-schema", type=Path, default=DEFAULT_GRAMMAR_SCHEMA)
    parser.add_argument("--regime-design", type=Path, default=DEFAULT_REGIME_DESIGN)
    parser.add_argument(
        "--measurement-design", type=Path, default=DEFAULT_MEASUREMENT_DESIGN
    )
    parser.add_argument("--verify-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    manifest = freeze_full_v1_dataset(
        arguments.dataset_dir,
        pilot_path=arguments.pilot,
        simulation_config_path=arguments.simulation_config,
        grammar_schema_path=arguments.grammar_schema,
        regime_design_path=arguments.regime_design,
        measurement_design_path=arguments.measurement_design,
        verify_only=arguments.verify_only,
        exact_command=shlex.join([sys.executable, *sys.argv]),
    )
    print(
        json.dumps(
            {
                "dataset": manifest["dataset_id"],
                "status": manifest["status"],
                "items": manifest["scale"]["items"],
                "learners": manifest["scale"]["learners"],
                "interactions": manifest["scale"]["interactions"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
