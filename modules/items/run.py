"""Expose generation and validation as explicit substeps under one item stage."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from modules.items.generate import run_generation
from modules.items.validate import run_validation
from shared.utils.io import ROOT, require_new_directory, utc_now
from shared.utils.manifests import write_stage_manifest


def run_stage(run_dir: Path, config: dict[str, Any], experiment_manifest: Path, command: list[str]) -> None:
    started = utc_now()
    output = run_dir / "items"
    require_new_directory(output)
    run_generation(output, run_dir, config, experiment_manifest, command)
    run_validation(output, run_dir, config, experiment_manifest, command)
    write_stage_manifest(
        output,
        module="items",
        version=config["version"],
        started_utc=started,
        command=command,
        inputs=[run_dir / "kc" / "manifest.json", run_dir / "realization" / "manifest.json"],
        configs=[experiment_manifest],
        code=[Path(__file__)],
        outputs=[output / "generation", output / "validation"],
        details={"substeps": ["generation", "validation"], "substeps_separate": True},
    )

