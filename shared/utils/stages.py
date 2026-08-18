"""Declared stage graph and lightweight content-addressed fingerprints."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .config import scientific_paths
from .io import ROOT, display_path, read_json, sha256_file, tree_sha256


STAGES = (
    "source", "normalization", "canonical", "realization", "kc",
    "items", "qmatrix", "simulation", "kt", "provenance",
)

# Package directories are numbered so they follow the research pipeline when
# naturally sorted in a file explorer. Stable stage IDs remain unnumbered in
# manifests and run directories.
MODULE_PACKAGE_DIRS: dict[str, str] = {
    "source": "stage_1_source",
    "normalization": "stage_2_normalization",
    "canonical": "stage_3_canonical",
    "realization": "stage_4_realization",
    "kc": "stage_5_kc",
    "items": "stage_6_items",
    "qmatrix": "stage_7_qmatrix",
    "simulation": "stage_8_simulation",
    "kt": "stage_9_kt",
    "provenance": "stage_10_provenance",
}

# These are the enforced data dependencies, not merely execution order.
DEPENDENCIES: dict[str, tuple[str, ...]] = {
    "source": (),
    "normalization": ("source",),
    "canonical": ("normalization",),
    "realization": ("canonical",),
    "kc": ("canonical", "realization"),
    "items": ("realization", "kc"),
    "qmatrix": ("items", "kc"),
    "simulation": ("items", "qmatrix"),
    "kt": ("simulation",),
    "provenance": (
        "source", "normalization", "canonical", "realization",
        "kc", "items", "qmatrix", "simulation",
    ),
}

# Only files actually consumed across each boundary contribute to cache identity.
DEPENDENCY_ARTIFACTS: dict[str, dict[str, tuple[str, ...]]] = {
    "normalization": {"source": ("source_subset.jsonl", "phase1_records.jsonl", "annotation_units.jsonl")},
    "canonical": {"normalization": ("final_mappings.jsonl",)},
    "realization": {"canonical": ("canonical_cells.jsonl", "source_cell_edges.jsonl")},
    "kc": {
        "canonical": ("canonical_cells.jsonl",),
        "realization": ("realizations.jsonl",),
    },
    "items": {
        "realization": ("realizations.jsonl",),
        "kc": ("cell_kc_projection.jsonl", "kc_inventory.jsonl"),
    },
    "qmatrix": {
        "items": ("validation/accepted_items.jsonl",),
        "kc": ("cell_kc_projection.jsonl", "kc_inventory.jsonl"),
    },
    "simulation": {
        "items": ("validation/accepted_items.jsonl",),
        "qmatrix": ("q_matrix.csv",),
    },
    "kt": {"simulation": ("observable_interactions.jsonl",)},
    "provenance": {
        "source": ("source_subset.jsonl", "manifest.json"),
        "normalization": ("final_mappings.jsonl", "mapping_provenance.jsonl", "manifest.json"),
        "canonical": ("source_cell_edges.jsonl", "manifest.json"),
        "realization": ("realizations.jsonl", "manifest.json"),
        "kc": ("manifest.json",),
        "items": ("validation/accepted_items.jsonl", "manifest.json"),
        "qmatrix": ("item_kc_edges.jsonl", "manifest.json"),
        "simulation": ("observable_interactions.jsonl", "manifest.json"),
    },
}


def stage_config(stage: str, config: dict[str, Any]) -> dict[str, Any]:
    """Expose only the scientific/configuration values used by one runner."""

    value = dict(config[stage])
    if stage == "kc":
        selected = value["policy"]
        value["policies"] = {selected: value["policies"][selected]}
    if stage == "items":
        value["_realization"] = {
            key: config["realization"][key] for key in ("version", "lexicon", "rules")
        }
    return value


def _file_record(path: Path) -> dict[str, Any]:
    if path.is_file():
        return {"path": display_path(path), "sha256": sha256_file(path), "kind": "file"}
    digest, count = tree_sha256(path)
    return {"path": display_path(path), "sha256": digest, "kind": "directory", "files": count}


def _implementation_files(stage: str) -> list[Path]:
    names: dict[str, tuple[str, ...]] = {
        "normalization": ("run.py",),
        "canonical": ("run.py",),
        "realization": ("run.py", "engine.py"),
        "kc": ("run.py", "policy.py"),
        "items": ("run.py", "generate.py", "validate.py", "helpers.py"),
        "qmatrix": ("run.py",),
        "simulation": ("run.py",),
        "kt": ("run.py",),
        "provenance": ("run.py",),
        "source": ("run.py",),
    }
    module_dir = ROOT / "modules" / MODULE_PACKAGE_DIRS[stage]
    files = [module_dir / name for name in names[stage]]
    common = [
        ROOT / "shared/utils/io.py",
        ROOT / "shared/utils/manifests.py",
        ROOT / "shared/utils/contracts.py",
    ]
    if stage in {"normalization", "items"}:
        common.extend(
            (
                ROOT / "shared/utils/model_backend.py",
                ROOT / "shared/utils/model_units.py",
            )
        )
    return [path for path in (*files, *common) if path.is_file()]


def _implicit_resources(stage: str) -> list[Path]:
    relatives: dict[str, tuple[str, ...]] = {
        "source": ("schemas/source_descriptor.schema.json",),
        "normalization": (),
        "canonical": (
            "schemas/grammar_cell.schema.json",
            "schemas/grammar_cell_record.schema.json",
            "schemas/source_cell_edge.schema.json",
        ),
        "realization": (),
        "kc": (
            "schemas/opportunity.schema.json",
            "schemas/kc_spec.schema.json",
            "schemas/kc_activation.schema.json",
        ),
        "items": ("schemas/item_spec_v0_1.schema.json", "schemas/validation_result.schema.json"),
        "qmatrix": ("schemas/item_kc_edge.schema.json",),
        "simulation": ("schemas/interaction.schema.json",),
        "kt": ("schemas/kt_prediction.schema.json",),
        "provenance": ("schemas/provenance_edge.schema.json",),
    }
    module_dir = ROOT / "modules" / MODULE_PACKAGE_DIRS[stage]
    return [module_dir / relative for relative in relatives[stage]]


def stage_fingerprint(stage: str, run_dir: Path, config: dict[str, Any]) -> dict[str, Any]:
    inputs: list[dict[str, Any]] = []
    for dependency, relatives in DEPENDENCY_ARTIFACTS.get(stage, {}).items():
        for relative in relatives:
            path = run_dir / dependency / relative
            if not path.is_file():
                raise FileNotFoundError(f"{stage} requires declared input {path}")
            inputs.append(_file_record(path))
    resolved_config = stage_config(stage, config)
    resource_paths = sorted(set(scientific_paths(resolved_config)) | set(_implicit_resources(stage)))
    resources = [_file_record(path) for path in resource_paths]
    implementation = [_file_record(path) for path in _implementation_files(stage)]
    payload = {
        "stage": stage,
        "version": resolved_config.get("version"),
        "inputs": inputs,
        "configuration": resolved_config,
        "scientific_resources": resources,
        "implementation": implementation,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {**payload, "sha256": hashlib.sha256(encoded.encode("utf-8")).hexdigest()}


def manifest_fingerprint(stage_dir: Path) -> str | None:
    path = stage_dir / "manifest.json"
    if not path.is_file():
        return None
    return read_json(path).get("stage_fingerprint")


def transitive_requirements(selected: list[str]) -> set[str]:
    required: set[str] = set()

    def add(stage: str) -> None:
        for dependency in DEPENDENCIES[stage]:
            add(dependency)
        required.add(stage)

    for stage in selected:
        add(stage)
    return required
