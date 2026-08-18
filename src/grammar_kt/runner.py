"""Explicit pipeline execution; no hidden fingerprints or automatic cache."""

from __future__ import annotations

import shutil
import subprocess
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from . import STAGES
from . import canonical, items, kc, kt, normalisation, qmatrix, realisation, simulation, source
from .config import Experiment, resolve_experiment
from .io import ROOT, path, utc_now, write_json


RUNNERS = {
    "source": source.run,
    "normalisation": normalisation.run,
    "canonical": canonical.run,
    "realisation": realisation.run,
    "kc": kc.run,
    "items": items.run,
    "simulation": simulation.run,
    "kt": kt.run,
}


def prepared_config(experiment: Experiment) -> dict[str, Any]:
    config = deepcopy(experiment.resolved)
    source_config = config["source"]
    for key in ("path", "sample_ids", "sample_metadata", "annotation_units"):
        source_config[key] = str(path(source_config[key]))
    return config


def git_state() -> tuple[str | None, bool | None]:
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True))
        return commit, dirty
    except (OSError, subprocess.CalledProcessError):
        return None, None


def _copy_upstream(parent: Path, target: Path, start: str) -> list[str]:
    copied = []
    for stage in STAGES[:STAGES.index(start)]:
        source_dir = parent / stage
        if not source_dir.is_dir():
            raise FileNotFoundError(f"parent run lacks {stage}: {source_dir}")
        shutil.copytree(source_dir, target / stage)
        copied.append(stage)
    if STAGES.index(start) > STAGES.index("items"):
        if not (parent / "qmatrix").is_dir():
            raise FileNotFoundError(f"parent run lacks qmatrix: {parent / 'qmatrix'}")
        shutil.copytree(parent / "qmatrix", target / "qmatrix")
        copied.append("qmatrix")
    return copied


def run_experiment(name: str, *, from_stage: str | None = None, force: bool = False,
                   runs_root: Path | None = None) -> Path:
    experiment = resolve_experiment(name)
    config = prepared_config(experiment)
    run_name = config.get("experiment", experiment.name)
    root = runs_root or ROOT / "runs"
    run_dir = root / run_name
    if run_dir.exists():
        if not force:
            raise FileExistsError(f"run already exists: {run_dir}; choose another experiment name or use --force")
        if run_dir.parent.resolve() != root.resolve():
            raise RuntimeError("refusing to remove a run outside the configured runs directory")
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True)
    (run_dir / "experiment.yaml").write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    commit, dirty = git_state()
    metadata = {
        "experiment": run_name,
        "parent": experiment.parent,
        "git_commit": commit,
        "git_dirty": dirty,
        "timestamp": utc_now(),
        "seed": config.get("simulation", {}).get("seed"),
        "source_sha256": config.get("source", {}).get("sha256"),
        "from_stage": from_stage,
        "reused_from": None,
        "stages": {},
    }
    start_index = 0
    if from_stage:
        if from_stage not in STAGES:
            raise ValueError(f"unknown stage {from_stage!r}; choose from {STAGES}")
        if not experiment.parent:
            raise ValueError("--from requires an experiment with extends: PARENT")
        parent = root / experiment.parent
        if not parent.is_dir():
            raise FileNotFoundError(f"parent run does not exist: {parent}")
        copied = _copy_upstream(parent, run_dir, from_stage)
        metadata["reused_from"] = {"run": experiment.parent, "stages": copied}
        for stage in copied:
            metadata["stages"][stage] = {"status": "reused", "from": experiment.parent}
        start_index = STAGES.index(from_stage)
    write_json(run_dir / "metadata.json", metadata)
    for stage in STAGES[start_index:]:
        summary = RUNNERS[stage](run_dir, config.get(stage, {}))
        metadata["stages"][stage] = {"status": "executed", "summary": summary}
        if stage == "items":
            q_summary = qmatrix.run(run_dir)
            metadata["stages"]["qmatrix"] = {"status": "executed", "summary": q_summary}
        write_json(run_dir / "metadata.json", metadata)
    return run_dir
