#!/usr/bin/env python3
"""Write or verify the machine-readable full-v1 release root manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "reports/final_release_manifest.json"

EXACT_GROUPS: dict[str, tuple[str, ...]] = {
    "release_documentation": (
        "README.md",
        "reports/research_state.md",
        "reports/experiment_log.md",
        "reports/experiment_bank.md",
        "reports/final_methodology.md",
        "reports/final_rq_ledger.md",
        "reports/final_verification.md",
        "reports/full_dataset_investigation.md",
    ),
    "dataset_root": (
        "data/grammar_kt_full_v1/README.md",
        "data/grammar_kt_full_v1/manifest.json",
        "data/grammar_kt_full_v1/grammar/cells.jsonl",
        "data/grammar_kt_full_v1/grammar/regime_assignments.jsonl",
        "data/grammar_kt_full_v1/grammar/source_cell_relations.jsonl",
        "data/grammar_kt_full_v1/kcs.jsonl",
        "data/grammar_kt_full_v1/items/items.jsonl",
        "data/grammar_kt_full_v1/q_matrix.csv",
        "data/grammar_kt_full_v1/interactions.jsonl.gz",
        "data/grammar_kt_full_v1/oracle/q_matrix_sparse.jsonl",
        "data/grammar_kt_full_v1/oracle/learner_truth.jsonl.gz",
    ),
    "generator_and_simulator_decisions": (
        "reports/full_v1_artifacts/kc/generator_alternatives_full_cells_preitem.json",
        "reports/baseline/artifacts/full_simulator_v1/pilot_seed_20260829.json",
    ),
    "active_runners_and_notebooks": (
        "scripts/build_dataset.py",
        "scripts/build_true_q_matrix.py",
        "scripts/freeze_baseline_dataset.py",
        "scripts/investigate_baseline_simulator.py",
        "scripts/build_full_v1_results_notebook.py",
        "scripts/experiments/rq2_kc_misspecification.py",
        "scripts/experiments/rq3_kc_discovery.py",
        "scripts/experiments/rq4_grammar_generalisation.py",
        "scripts/experiments/full_v1_mastery_recovery.py",
        "scripts/experiments/full_v1_mastery_recovery_bootstrap.py",
        "scripts/experiments/full_v1_bkt_state_recovery.py",
        "scripts/experiments/simulator_robustness.py",
        "scripts/experiments/collection_design.py",
        "scripts/final_release_manifest.py",
        "notebooks/pipeline_walkthrough.ipynb",
        "notebooks/final_dataset.ipynb",
        "notebooks/final_dataset_results.ipynb",
    ),
    "release_contracts": (
        "tests/test_collection_design.py",
        "tests/test_research_layout.py",
        "tests/test_final_release_manifest.py",
    ),
}

DIRECTORY_GROUPS: dict[str, tuple[str, tuple[str, ...]]] = {
    "rq2_final": (
        "reports/full_v1_artifacts/rq2_misspecification_v1",
        ("development_results_n20.json",),
    ),
    "rq3_final": (
        "experiments/full_v1/rq3_kc_discovery_v1",
        ("pilot_evaluation.json", "pilot_selection.json"),
    ),
    "rq4_final": ("experiments/full_v1/rq4_generalisation_v1", ()),
    "mastery_recovery": ("reports/full_v1_artifacts/mastery_recovery_v1", ()),
    "simulator_robustness": ("experiments/full_v1/simulator_robustness_v1", ()),
    "collection_design": ("experiments/full_v1/collection_design_v1", ()),
}

ACL_SUFFIXES = frozenset({".tex", ".bib", ".bst", ".sty", ".md", ".pdf", ".bbl", ".py"})
SOURCE_SUFFIXES = frozenset({".py", ".yaml", ".yml", ".json", ".md", ".txt"})


def sha256_bytes(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _directory_files(relative_dir: str, excluded_names: Iterable[str]) -> list[Path]:
    base = ROOT / relative_dir
    excluded = set(excluded_names)
    if not base.is_dir():
        raise FileNotFoundError(f"release scope directory missing: {relative_dir}")
    return sorted(
        path
        for path in base.rglob("*")
        if path.is_file() and path.name not in excluded
    )


def scoped_files() -> dict[str, list[Path]]:
    groups: dict[str, list[Path]] = {}
    for group, relative_paths in EXACT_GROUPS.items():
        paths = [ROOT / path for path in relative_paths]
        missing = [str(path.relative_to(ROOT)) for path in paths if not path.is_file()]
        if missing:
            raise FileNotFoundError(f"release files missing: {missing}")
        groups[group] = sorted(paths)
    for group, (relative_dir, excluded) in DIRECTORY_GROUPS.items():
        groups[group] = _directory_files(relative_dir, excluded)

    groups["active_source"] = sorted(
        path
        for relative_dir in ("src/grammar_kt", "modules/grammar", "modules/kcs/generator", "modules/items", "modules/simulation")
        for path in (ROOT / relative_dir).rglob("*")
        if path.is_file() and path.suffix in SOURCE_SUFFIXES
    )
    groups["acl_manuscript"] = sorted(
        path
        for path in (ROOT / "ACL").rglob("*")
        if path.is_file()
        and path.suffix in ACL_SUFFIXES
        and "tests/__pycache__" not in path.relative_to(ROOT).as_posix()
    )
    return groups


def scope_declaration() -> dict[str, object]:
    return {
        "exact_groups": {key: list(value) for key, value in EXACT_GROUPS.items()},
        "directory_groups": {
            key: {"directory": value[0], "excluded_names": list(value[1])}
            for key, value in DIRECTORY_GROUPS.items()
        },
        "active_source_directories": [
            "src/grammar_kt",
            "modules/grammar",
            "modules/kcs/generator",
            "modules/items",
            "modules/simulation",
        ],
        "active_source_suffixes": sorted(SOURCE_SUFFIXES),
        "acl_directory": "ACL",
        "acl_suffixes": sorted(ACL_SUFFIXES),
    }


def build_manifest() -> dict[str, object]:
    records: list[dict[str, object]] = []
    seen: set[str] = set()
    for group, paths in sorted(scoped_files().items()):
        for path in paths:
            relative = path.relative_to(ROOT).as_posix()
            if relative in seen:
                raise ValueError(f"release file occurs in multiple groups: {relative}")
            seen.add(relative)
            records.append(
                {
                    "group": group,
                    "path": relative,
                    "bytes": path.stat().st_size,
                    "sha256": sha256_bytes(path),
                }
            )
    records.sort(key=lambda row: row["path"])
    canonical = json.dumps(records, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {
        "manifest_id": "grammar_kt_full_v1_final_release_root",
        "status": "FINAL_RELEASE_VERIFIED",
        "purpose": "Root byte-hash anchor for the frozen baseline, paper-facing experiments, final synthesis, executable notebooks, and ACL manuscript.",
        "scope": scope_declaration(),
        "explicit_exclusions": [
            "reports/final_release_manifest.json (this manifest; anchored by Git)",
            "reports/historical/** and medium-v1 evidence",
            "RQ2 development_results_n20.json and RQ3 pilot outputs",
            "TeX auxiliary/log files and local render intermediates",
            "licensed source content, provider snapshots/seeds, and unrelated user files",
        ],
        "artifact_count": len(records),
        "artifact_bytes": sum(int(row["bytes"]) for row in records),
        "inventory_semantic_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
        "artifacts": records,
    }


def write_manifest(path: Path) -> None:
    manifest = build_manifest()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "artifact": path.relative_to(ROOT).as_posix(),
                "artifacts": manifest["artifact_count"],
                "sha256": sha256_bytes(path),
            },
            indent=2,
        )
    )


def verify_manifest(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"release manifest missing: {path}")
    stored = json.loads(path.read_text(encoding="utf-8"))
    current = build_manifest()
    if stored != current:
        stored_by_path = {row["path"]: row for row in stored.get("artifacts", [])}
        current_by_path = {row["path"]: row for row in current["artifacts"]}
        missing = sorted(set(stored_by_path) - set(current_by_path))
        unexpected = sorted(set(current_by_path) - set(stored_by_path))
        changed = sorted(
            path_key
            for path_key in set(stored_by_path) & set(current_by_path)
            if stored_by_path[path_key] != current_by_path[path_key]
        )
        raise ValueError(
            "final release manifest drift: "
            f"missing={missing}, unexpected={unexpected}, changed={changed}"
        )
    print(
        json.dumps(
            {
                "status": "FINAL_RELEASE_MANIFEST_VERIFIED",
                "artifacts": stored["artifact_count"],
                "sha256": sha256_bytes(path),
            },
            indent=2,
        )
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--verify", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = args.output.resolve()
    if output != DEFAULT_OUTPUT.resolve():
        raise ValueError("the final release root has one fixed repository path")
    if args.write:
        write_manifest(output)
    else:
        verify_manifest(output)


if __name__ == "__main__":
    main()
