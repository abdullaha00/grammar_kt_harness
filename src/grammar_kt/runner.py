"""Explicit pipeline execution; no hidden fingerprints or automatic cache."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

import yaml

from . import canonical, items, kc, kc_selection, kt, normalisation, qmatrix, realisation, simulation, source
from .config import load_experiment
from .io import ROOT, utc_now, write_json


PIPELINE = [
    ("source", source.run),
    ("normalisation", normalisation.run),
    ("canonical", canonical.run),
    ("realisation", realisation.run),
    ("items", items.run),
    ("kc_selection", kc_selection.run),
    ("kc", kc.run),
    ("qmatrix", qmatrix.run),
    ("simulation", simulation.run),
    ("kt", kt.run),
]
STAGE_NAMES = [name for name, _run_stage in PIPELINE]


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
        "stages": {},
    }
    start_index = 0
    if from_stage:
        if from_stage not in STAGE_NAMES:
            raise ValueError(f"unknown stage {from_stage!r}; choose from {STAGE_NAMES}")
        if not parent_name:
            raise ValueError("--from requires an experiment with extends: PARENT")
        parent = root / parent_name
        if not parent.is_dir():
            raise FileNotFoundError(f"parent run does not exist: {parent}")
        copied = []
        for stage in STAGE_NAMES[:STAGE_NAMES.index(from_stage)]:
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
