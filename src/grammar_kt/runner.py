"""Explicit pipeline execution with reuse-safety signatures, never hidden caching."""

from __future__ import annotations

import shutil
import subprocess
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from . import canonical, items, kc, kc_selection, kt, normalisation, qmatrix, realisation, simulation, source
from .config import load_experiment
from .io import ROOT, repo_path, sha256_file, utc_now, write_json


PIPELINE = [
    ("source", source.run),
    ("normalisation", normalisation.run),
    ("canonical", canonical.run),
    ("realisation", realisation.run),
    ("items", items.run),
    ("simulation", simulation.run),
    ("kc_selection", kc_selection.run),
    ("kc", kc.run),
    ("qmatrix", qmatrix.run),
    ("kt", kt.run),
]
STAGE_NAMES = [name for name, _run_stage in PIPELINE]

# Scientific module files consumed through stable code-level entry points rather
# than experiment keys. Keeping this short list here makes reuse checks auditable.
STAGE_MODULE_INPUTS = {
    "normalisation": [
        "modules/canonical/grammar_schema.yaml",
        "modules/normalisation/prompts/wrapper.txt",
        "modules/normalisation/rules/rulebook.md",
        "modules/normalisation/rules/model_instructions.md",
        "modules/normalisation/configs/mapping_schema.json",
    ],
    "canonical": ["modules/canonical/grammar_schema.yaml"],
    "items": [
        "modules/items/validation/diagnostic_prompt.txt",
        "modules/items/validation/diagnostic_instructions.md",
        "modules/items/validation/diagnostic_schema.json",
    ],
}


def _resolve_signature_value(value: Any, seen: frozenset[Path] = frozenset()) -> Any:
    if isinstance(value, dict):
        return {
            key: _resolve_signature_value(item, seen)
            for key, item in sorted(value.items())
        }
    if isinstance(value, list):
        return [_resolve_signature_value(item, seen) for item in value]
    if isinstance(value, str):
        try:
            candidate = repo_path(value)
            if candidate.is_file():
                resolved: dict[str, Any] = {
                    "path": value,
                    "sha256": sha256_file(candidate),
                }
                if candidate not in seen and candidate.suffix.lower() in {".json", ".yaml", ".yml"}:
                    try:
                        parsed = (
                            json.loads(candidate.read_text(encoding="utf-8"))
                            if candidate.suffix.lower() == ".json"
                            else yaml.safe_load(candidate.read_text(encoding="utf-8"))
                        )
                        resolved["referenced_inputs"] = _resolve_signature_value(
                            parsed, seen | {candidate}
                        )
                    except (ValueError, TypeError):
                        # The byte hash remains authoritative for malformed
                        # config; stage execution will report its parse error.
                        pass
                return resolved
        except OSError:
            # Plain descriptive strings are settings too, but are not paths.
            pass
    return value


def stage_input_signature(stage: str, settings: dict[str, Any]) -> dict[str, Any]:
    """Hash the resolved researcher-controlled inputs consumed by one stage."""

    resolved = {
        "settings": _resolve_signature_value(settings.get(stage, {})),
        "fixed_module_inputs": _resolve_signature_value(
            STAGE_MODULE_INPUTS.get(stage, [])
        ),
    }
    payload = json.dumps(resolved, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {
        "sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "resolved_inputs": resolved,
    }


def stage_input_signatures(settings: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {stage: stage_input_signature(stage, settings) for stage in STAGE_NAMES}


def validate_reuse(
    parent: Path,
    child_settings: dict[str, Any],
    reused_stages: list[str],
) -> None:
    metadata_path = parent / "metadata.json"
    if not metadata_path.is_file():
        raise RuntimeError(f"parent run lacks reuse-safety metadata: {metadata_path}")
    from .io import read_json

    parent_metadata = read_json(metadata_path)
    recorded = parent_metadata.get("stage_input_signatures")
    if not isinstance(recorded, dict):
        raise RuntimeError(
            "parent run predates stage-input signatures; rerun the parent before --from reuse"
        )
    current = stage_input_signatures(child_settings)
    mismatches = []
    for stage in reused_stages:
        previous = recorded.get(stage)
        if not isinstance(previous, dict) or previous.get("sha256") != current[stage]["sha256"]:
            mismatches.append(
                {
                    "stage": stage,
                    "parent_sha256": previous.get("sha256") if isinstance(previous, dict) else None,
                    "child_sha256": current[stage]["sha256"],
                    "parent_inputs": previous.get("resolved_inputs") if isinstance(previous, dict) else None,
                    "child_inputs": current[stage]["resolved_inputs"],
                }
            )
    if mismatches:
        details = "; ".join(
            f"{row['stage']}: parent={row['parent_sha256']} child={row['child_sha256']}"
            for row in mismatches
        )
        raise RuntimeError(f"refusing unsafe --from reuse; upstream settings differ: {details}")


def git_state() -> tuple[str | None, bool | None]:
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True))
        return commit, dirty
    except (OSError, subprocess.CalledProcessError):
        return None, None


def run_experiment(name: str, *, from_stage: str | None = None, force: bool = False,
                   runs_root: Path | None = None) -> Path:
    settings, parent_name = load_experiment(name)
    run_name = settings.get("experiment", name)
    root = runs_root or ROOT / "runs"
    run_dir = root / run_name
    reused_stages: list[str] = []
    parent: Path | None = None
    if from_stage:
        if from_stage not in STAGE_NAMES:
            raise ValueError(f"unknown stage {from_stage!r}; choose from {STAGE_NAMES}")
        if not parent_name:
            raise ValueError("--from requires an experiment with extends: PARENT")
        parent = root / parent_name
        if not parent.is_dir():
            raise FileNotFoundError(f"parent run does not exist: {parent}")
        reused_stages = STAGE_NAMES[:STAGE_NAMES.index(from_stage)]
        validate_reuse(parent, settings, reused_stages)
    if run_dir.exists():
        if not force:
            raise FileExistsError(f"run already exists: {run_dir}; choose another experiment name or use --force")
        if run_dir.parent.resolve() != root.resolve():
            raise RuntimeError("refusing to remove a run outside the configured runs directory")
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True)
    (run_dir / "experiment.yaml").write_text(yaml.safe_dump(settings, sort_keys=False), encoding="utf-8")
    commit, dirty = git_state()
    metadata = {
        "experiment": run_name,
        "parent": parent_name,
        "git_commit": commit,
        "git_dirty": dirty,
        "timestamp": utc_now(),
        "seed": settings.get("simulation", {}).get("seed"),
        "source_sha256": settings.get("source", {}).get("sha256"),
        "from_stage": from_stage,
        "reused_from": None,
        "stage_input_signatures": stage_input_signatures(settings),
        "stages": {},
    }
    start_index = 0
    if from_stage:
        copied = []
        assert parent is not None
        for stage in reused_stages:
            source_dir = parent / stage
            if not source_dir.is_dir():
                raise FileNotFoundError(f"parent run lacks {stage}: {source_dir}")
            shutil.copytree(source_dir, run_dir / stage)
            copied.append(stage)
        metadata["reused_from"] = {"run": parent_name, "stages": copied}
        for stage in copied:
            metadata["stages"][stage] = {"status": "reused", "from": parent_name}
        start_index = STAGE_NAMES.index(from_stage)
    write_json(run_dir / "metadata.json", metadata)
    for stage, run_stage in PIPELINE[start_index:]:
        summary = run_stage(run_dir, settings.get(stage, {}))
        metadata["stages"][stage] = {"status": "executed", "summary": summary}
        write_json(run_dir / "metadata.json", metadata)
    return run_dir
