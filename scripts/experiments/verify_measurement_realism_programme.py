#!/usr/bin/env python3
"""Preflight, freeze, or verify the measurement-realism evidence root.

The tool is deliberately separate from the immutable full-v1 release manifest.
It uses an exact file allowlist, records full-v1 only as a protected Git/hash
anchor, and refuses to freeze while any required report/result/notebook/paper
is missing or while a declared claim boundary is violated.  Raw controlled-
world response streams are reconstruction inputs, not programme-release files.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

import jsonschema


ROOT = Path(__file__).resolve().parents[2]
VERIFICATION_ROOT = ROOT / "experiments/measurement_realism/verification"
DEFAULT_CONFIG = VERIFICATION_ROOT / "programme_evidence_config.json"
DEFAULT_CONFIG_SCHEMA = VERIFICATION_ROOT / "programme_evidence_config.schema.json"


class ReadinessError(ValueError):
    """Raised when the explicit programme evidence contract is not ready."""

    def __init__(self, errors: Sequence[str]):
        self.errors = list(errors)
        super().__init__("programme evidence is not ready: " + "; ".join(self.errors))


@dataclass(frozen=True)
class Assessment:
    config: dict[str, Any]
    records: list[dict[str, Any]]
    protected: dict[str, Any] | None
    release_decision: dict[str, Any] | None
    json_assertions: list[dict[str, Any]]
    text_contracts: list[dict[str, Any]]
    errors: list[str]

    @property
    def ready(self) -> bool:
        return not self.errors


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_identity(root: Path, path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(root).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_json(instance: Any, schema_path: Path) -> None:
    schema = load_json(schema_path)
    jsonschema.Draft202012Validator.check_schema(schema)
    errors = sorted(
        jsonschema.Draft202012Validator(schema).iter_errors(instance),
        key=lambda error: tuple(str(piece) for piece in error.absolute_path),
    )
    if errors:
        rendered = [
            f"{'/'.join(str(piece) for piece in error.absolute_path) or '<root>'}: "
            f"{error.message}"
            for error in errors
        ]
        raise ValueError("JSON schema validation failed: " + "; ".join(rendered))


def safe_relative_path(root: Path, value: str) -> Path:
    pure = PurePosixPath(value)
    if pure.is_absolute() or not pure.parts or any(piece in {"", ".", ".."} for piece in pure.parts):
        raise ValueError(f"path is not a normalized repository-relative path: {value!r}")
    resolved = (root / Path(*pure.parts)).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"path escapes repository root: {value!r}") from exc
    return resolved


def run_git(root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def json_pointer(value: Any, pointer: str) -> Any:
    if not pointer.startswith("/"):
        raise ValueError(f"JSON pointer must begin with '/': {pointer!r}")
    current = value
    for raw_piece in pointer[1:].split("/"):
        piece = raw_piece.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            current = current[int(piece)]
        elif isinstance(current, Mapping):
            current = current[piece]
        else:
            raise KeyError(piece)
    return current


def matches_exclusion(path: str, patterns: Sequence[str]) -> str | None:
    for pattern in patterns:
        if fnmatch.fnmatchcase(path, pattern):
            return pattern
    return None


def load_config(config_path: Path, config_schema_path: Path) -> dict[str, Any]:
    config = load_json(config_path)
    validate_json(config, config_schema_path)
    return config


def collect_allowlisted_records(
    root: Path, config: Mapping[str, Any]
) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    records: list[dict[str, Any]] = []
    group_ids = [str(group["group_id"]) for group in config["evidence_groups"]]
    if len(group_ids) != len(set(group_ids)):
        errors.append("evidence group IDs are not unique")
    missing_groups = sorted(set(config["required_group_ids"]) - set(group_ids))
    unexpected_groups = sorted(set(group_ids) - set(config["required_group_ids"]))
    if missing_groups:
        errors.append(f"required evidence groups missing: {missing_groups}")
    if unexpected_groups:
        errors.append(f"undeclared evidence groups present: {unexpected_groups}")

    protected = str(config["protected_baseline"]["path"]).rstrip("/")
    candidate = str(config["dataset_release_decision"]["candidate_path"]).rstrip("/")
    manifest_output = str(config["manifest_output"])
    seen: dict[str, str] = {}
    for group in config["evidence_groups"]:
        group_id = str(group["group_id"])
        for relative in group["paths"]:
            relative = str(relative)
            try:
                path = safe_relative_path(root, relative)
            except ValueError as exc:
                errors.append(str(exc))
                continue
            excluded_by = matches_exclusion(relative, config["exclusion_patterns"])
            if excluded_by:
                errors.append(
                    f"allowlisted path violates exclusion {excluded_by!r}: {relative}"
                )
            if relative == manifest_output:
                errors.append(f"manifest cannot include itself: {relative}")
            if relative == protected or relative.startswith(protected + "/"):
                errors.append(f"protected full-v1 content cannot be an evidence artifact: {relative}")
            if relative == candidate or relative.startswith(candidate + "/"):
                errors.append(f"non-release dataset path cannot be allowlisted: {relative}")
            if relative in seen:
                errors.append(
                    f"artifact is allowlisted more than once: {relative} "
                    f"({seen[relative]}, {group_id})"
                )
                continue
            seen[relative] = group_id
            if not path.exists():
                errors.append(f"required evidence file missing: {relative}")
                continue
            if not path.is_file() or path.is_symlink():
                errors.append(f"allowlisted artifact is not a regular non-symlink file: {relative}")
                continue
            records.append(
                {
                    "group": group_id,
                    "path": relative,
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    records.sort(key=lambda row: str(row["path"]))
    return records, errors


def protected_baseline_snapshot(
    root: Path, declaration: Mapping[str, Any]
) -> dict[str, Any]:
    relative = str(declaration["path"])
    baseline = safe_relative_path(root, relative)
    if not baseline.is_dir():
        raise ValueError(f"protected baseline directory missing: {relative}")
    source_commit = str(declaration["source_commit"])
    expected_tree = str(declaration["expected_git_tree_object"])
    source_tree = run_git(root, "rev-parse", f"{source_commit}:{relative}")
    head_tree = run_git(root, "rev-parse", f"HEAD:{relative}")
    if source_tree != expected_tree:
        raise ValueError(
            f"source full-v1 tree mismatch: expected {expected_tree}, observed {source_tree}"
        )
    if head_tree != expected_tree:
        raise ValueError(
            f"HEAD full-v1 tree mismatch: expected {expected_tree}, observed {head_tree}"
        )

    tracked_or_untracked = run_git(
        root, "status", "--porcelain=v1", "--untracked-files=all", "--", relative
    ).splitlines()
    ignored = run_git(
        root,
        "ls-files",
        "--others",
        "--ignored",
        "--exclude-standard",
        "--",
        relative,
    ).splitlines()
    source_diff = run_git(root, "diff", "--name-only", source_commit, "--", relative).splitlines()
    contaminated = sorted(set(filter(None, tracked_or_untracked + ignored + source_diff)))
    if contaminated:
        raise ValueError(f"protected full-v1 path is not clean: {contaminated}")

    tree_listing = run_git(
        root, "ls-tree", "-r", "--full-tree", source_commit, "--", relative
    )
    files = sorted(path for path in baseline.rglob("*") if path.is_file())
    symlinks = [path.relative_to(root).as_posix() for path in files if path.is_symlink()]
    if symlinks:
        raise ValueError(f"protected full-v1 contains symlinks: {symlinks}")
    inventory = [
        {
            "path": path.relative_to(baseline).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in files
    ]

    anchor_path = safe_relative_path(root, str(declaration["anchor_path"]))
    if not anchor_path.is_file():
        raise ValueError(f"protected-baseline anchor missing: {declaration['anchor_path']}")
    anchor = load_json(anchor_path)
    if anchor.get("source_commit") != source_commit:
        raise ValueError("baseline anchor source commit disagrees with verification config")
    if anchor.get("git_tree_object") != expected_tree:
        raise ValueError("baseline anchor tree object disagrees with verification config")
    boundary = anchor.get("boundary", {})
    for key in (
        "full_v1_mutated",
        "new_measurement_outputs_written_inside_full_v1",
    ):
        if boundary.get(key) is not False:
            raise ValueError(f"baseline anchor boundary is not false: {key}")

    core_observed: dict[str, str] = {}
    for core_relative, expected_sha in declaration["core_sha256"].items():
        core_path = safe_relative_path(baseline, str(core_relative))
        if not core_path.is_file():
            raise ValueError(f"protected baseline core file missing: {core_relative}")
        observed = sha256_file(core_path)
        if observed != expected_sha:
            raise ValueError(
                f"protected baseline SHA-256 mismatch for {core_relative}: "
                f"expected {expected_sha}, observed {observed}"
            )
        core_observed[str(core_relative)] = observed

    return {
        "path": relative,
        "source_commit": source_commit,
        "source_git_tree_object": source_tree,
        "head_git_tree_object": head_tree,
        "expected_git_tree_object": expected_tree,
        "git_tree_listing_sha256": sha256_bytes((tree_listing + "\n").encode()),
        "filesystem_clean_against_source_commit": True,
        "untracked_or_ignored_inside_protected_path": [],
        "filesystem_file_count": len(inventory),
        "filesystem_bytes": sum(int(row["bytes"]) for row in inventory),
        "filesystem_inventory_semantic_sha256": sha256_bytes(
            canonical_json(inventory).encode()
        ),
        "anchor": file_identity(root, anchor_path),
        "core_sha256": dict(sorted(core_observed.items())),
    }


def verify_release_decision(
    root: Path, config: Mapping[str, Any]
) -> dict[str, Any]:
    declaration = config["dataset_release_decision"]
    candidate = safe_relative_path(root, str(declaration["candidate_path"]))
    if declaration["decision"] != "NO_NEW_DATASET_RELEASE":
        raise ValueError("programme evidence may not declare a new dataset release")
    if declaration["must_not_exist"] is not True:
        raise ValueError("candidate dataset absence is not a hard gate")
    if candidate.exists() or candidate.is_symlink():
        raise ValueError(
            f"no-release candidate path exists and must be removed or separately authorized: "
            f"{declaration['candidate_path']}"
        )
    return {
        "decision": "NO_NEW_DATASET_RELEASE",
        "candidate_path": str(declaration["candidate_path"]),
        "candidate_path_absent": True,
        "basis": str(declaration["basis"]),
    }


def verify_required_absence(root: Path, config: Mapping[str, Any]) -> list[str]:
    errors = []
    for relative in config["required_absent_paths"]:
        path = safe_relative_path(root, str(relative))
        if path.exists() or path.is_symlink():
            errors.append(f"required-absent path exists: {relative}")
    return errors


def verify_claim_assertions(
    root: Path,
    config: Mapping[str, Any],
    allowlisted: set[str],
) -> tuple[list[dict[str, Any]], list[str]]:
    results: list[dict[str, Any]] = []
    errors: list[str] = []
    assertion_ids: set[str] = set()
    for assertion in config["claim_assertions"]:
        assertion_id = str(assertion["assertion_id"])
        relative = str(assertion["path"])
        if assertion_id in assertion_ids:
            errors.append(f"duplicate claim assertion ID: {assertion_id}")
        assertion_ids.add(assertion_id)
        if relative not in allowlisted:
            errors.append(f"claim assertion reads a non-allowlisted file: {relative}")
        path = safe_relative_path(root, relative)
        if not path.is_file():
            errors.append(f"claim assertion file missing: {relative}")
            continue
        try:
            observed = json_pointer(load_json(path), str(assertion["json_pointer"]))
        except (KeyError, IndexError, ValueError, TypeError, json.JSONDecodeError) as exc:
            errors.append(
                f"claim assertion {assertion_id} cannot read "
                f"{relative}{assertion['json_pointer']}: {exc}"
            )
            continue
        passed = observed == assertion["equals"]
        if not passed:
            errors.append(
                f"claim assertion {assertion_id} failed: expected "
                f"{assertion['equals']!r}, observed {observed!r}"
            )
        results.append(
            {
                "assertion_id": assertion_id,
                "path": relative,
                "json_pointer": str(assertion["json_pointer"]),
                "observed": observed,
                "passed": passed,
            }
        )
    return results, errors


def verify_text_contracts(
    root: Path,
    config: Mapping[str, Any],
    allowlisted: set[str],
) -> tuple[list[dict[str, Any]], list[str]]:
    results: list[dict[str, Any]] = []
    errors: list[str] = []
    contract_ids: set[str] = set()
    for contract in config["text_contracts"]:
        contract_id = str(contract["contract_id"])
        relative = str(contract["path"])
        if contract_id in contract_ids:
            errors.append(f"duplicate text-contract ID: {contract_id}")
        contract_ids.add(contract_id)
        if relative not in allowlisted:
            errors.append(f"text contract reads a non-allowlisted file: {relative}")
        path = safe_relative_path(root, relative)
        if not path.is_file():
            errors.append(f"text-contract file missing: {relative}")
            continue
        text = path.read_text(encoding="utf-8").casefold()
        missing = [
            phrase
            for phrase in contract["required_casefold_phrases"]
            if str(phrase).casefold() not in text
        ]
        forbidden = [
            phrase
            for phrase in contract.get("forbidden_casefold_phrases", [])
            if str(phrase).casefold() in text
        ]
        if missing:
            errors.append(f"text contract {contract_id} missing phrases: {missing}")
        if forbidden:
            errors.append(
                f"text contract {contract_id} contains forbidden phrases: {forbidden}"
            )
        results.append(
            {
                "contract_id": contract_id,
                "path": relative,
                "required_casefold_phrases": list(contract["required_casefold_phrases"]),
                "forbidden_casefold_phrases": list(
                    contract.get("forbidden_casefold_phrases", [])
                ),
                "passed": not missing and not forbidden,
            }
        )
    return results, errors


def assess(
    *,
    root: Path = ROOT,
    config_path: Path = DEFAULT_CONFIG,
    config_schema_path: Path = DEFAULT_CONFIG_SCHEMA,
) -> Assessment:
    root = root.resolve()
    config_path = config_path.resolve()
    config_schema_path = config_schema_path.resolve()
    config = load_config(config_path, config_schema_path)
    records, errors = collect_allowlisted_records(root, config)
    allowlisted = {
        str(relative)
        for group in config["evidence_groups"]
        for relative in group["paths"]
    }

    protected: dict[str, Any] | None = None
    try:
        protected = protected_baseline_snapshot(root, config["protected_baseline"])
    except (ValueError, FileNotFoundError, subprocess.CalledProcessError) as exc:
        errors.append(f"protected full-v1 verification failed: {exc}")

    release_decision: dict[str, Any] | None = None
    try:
        release_decision = verify_release_decision(root, config)
    except ValueError as exc:
        errors.append(f"dataset-release boundary failed: {exc}")
    errors.extend(verify_required_absence(root, config))

    assertions, assertion_errors = verify_claim_assertions(
        root, config, allowlisted
    )
    errors.extend(assertion_errors)
    text_contracts, text_errors = verify_text_contracts(root, config, allowlisted)
    errors.extend(text_errors)
    return Assessment(
        config=config,
        records=records,
        protected=protected,
        release_decision=release_decision,
        json_assertions=assertions,
        text_contracts=text_contracts,
        errors=sorted(set(errors)),
    )


def readiness_summary(assessment: Assessment) -> dict[str, Any]:
    return {
        "status": "READY_TO_FREEZE" if assessment.ready else "NOT_READY_TO_FREEZE",
        "ready": assessment.ready,
        "artifact_count_present": len(assessment.records),
        "artifact_bytes_present": sum(int(row["bytes"]) for row in assessment.records),
        "protected_full_v1_verified": assessment.protected is not None,
        "no_dataset_release_verified": assessment.release_decision is not None,
        "errors": assessment.errors,
    }


def build_manifest(
    *,
    root: Path = ROOT,
    config_path: Path = DEFAULT_CONFIG,
    config_schema_path: Path = DEFAULT_CONFIG_SCHEMA,
) -> dict[str, Any]:
    assessment = assess(
        root=root,
        config_path=config_path,
        config_schema_path=config_schema_path,
    )
    if not assessment.ready:
        raise ReadinessError(assessment.errors)
    assert assessment.protected is not None
    assert assessment.release_decision is not None
    config = assessment.config
    records = assessment.records
    inventory_digest = sha256_bytes(canonical_json(records).encode())
    manifest = {
        "schema_version": 1,
        "manifest_id": "measurement_realism_programme_evidence_v1",
        "status": "PROGRAMME_EVIDENCE_VERIFIED",
        "config": file_identity(root.resolve(), config_path.resolve()),
        "protected_full_v1": assessment.protected,
        "dataset_release_decision": assessment.release_decision,
        "claim_boundary_verification": {
            "json_assertions": assessment.json_assertions,
            "text_contracts": assessment.text_contracts,
        },
        "scope": {
            "explicit_allowlist": {
                str(group["group_id"]): list(group["paths"])
                for group in config["evidence_groups"]
            },
            "exclusion_patterns": list(config["exclusion_patterns"]),
            "required_absent_paths": list(config["required_absent_paths"]),
        },
        "reconstruction_commands": list(config["reconstruction_commands"]),
        "artifact_count": len(records),
        "artifact_bytes": sum(int(row["bytes"]) for row in records),
        "inventory_semantic_sha256": inventory_digest,
        "artifacts": records,
    }
    manifest_schema = safe_relative_path(root.resolve(), str(config["manifest_schema"]))
    validate_json(manifest, manifest_schema)
    return manifest


def freeze_manifest(
    *,
    authorized: bool,
    root: Path = ROOT,
    config_path: Path = DEFAULT_CONFIG,
    config_schema_path: Path = DEFAULT_CONFIG_SCHEMA,
) -> dict[str, Any]:
    if not authorized:
        raise PermissionError(
            "final manifest freeze requires --authorize-final-freeze after shared deliverables are ready"
        )
    config = load_config(config_path.resolve(), config_schema_path.resolve())
    output = safe_relative_path(root.resolve(), str(config["manifest_output"]))
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"refusing to overwrite frozen programme manifest: {output}")
    manifest = build_manifest(
        root=root,
        config_path=config_path,
        config_schema_path=config_schema_path,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".programme_evidence_manifest.incomplete.",
        dir=output.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        if output.exists() or output.is_symlink():
            raise FileExistsError(f"refusing to overwrite frozen programme manifest: {output}")
        temporary.replace(output)
    finally:
        if temporary.exists():
            temporary.unlink()
    return manifest


def verify_frozen_manifest(
    *,
    root: Path = ROOT,
    config_path: Path = DEFAULT_CONFIG,
    config_schema_path: Path = DEFAULT_CONFIG_SCHEMA,
) -> dict[str, Any]:
    config = load_config(config_path.resolve(), config_schema_path.resolve())
    output = safe_relative_path(root.resolve(), str(config["manifest_output"]))
    if not output.is_file():
        raise FileNotFoundError(f"frozen programme manifest missing: {output}")
    stored = load_json(output)
    manifest_schema = safe_relative_path(root.resolve(), str(config["manifest_schema"]))
    validate_json(stored, manifest_schema)
    current = build_manifest(
        root=root,
        config_path=config_path,
        config_schema_path=config_schema_path,
    )
    if stored != current:
        stored_by_path = {row["path"]: row for row in stored.get("artifacts", [])}
        current_by_path = {row["path"]: row for row in current.get("artifacts", [])}
        missing = sorted(set(stored_by_path) - set(current_by_path))
        unexpected = sorted(set(current_by_path) - set(stored_by_path))
        changed = sorted(
            path
            for path in set(stored_by_path) & set(current_by_path)
            if stored_by_path[path] != current_by_path[path]
        )
        raise ValueError(
            "programme evidence manifest drift: "
            f"missing={missing}, unexpected={unexpected}, changed={changed}"
        )
    return {
        "status": "PROGRAMME_EVIDENCE_MANIFEST_VERIFIED",
        "manifest": output.relative_to(root.resolve()).as_posix(),
        "manifest_sha256": sha256_file(output),
        "artifacts": stored["artifact_count"],
        "protected_full_v1_tree": stored["protected_full_v1"][
            "expected_git_tree_object"
        ],
        "dataset_release_decision": stored["dataset_release_decision"]["decision"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("preflight", "freeze", "verify"))
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--config-schema", type=Path, default=DEFAULT_CONFIG_SCHEMA)
    parser.add_argument(
        "--authorize-final-freeze",
        action="store_true",
        help="required only for the final non-overwriting freeze after root approval",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.stage == "preflight":
            result = readiness_summary(
                assess(
                    root=ROOT,
                    config_path=args.config,
                    config_schema_path=args.config_schema,
                )
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["ready"] else 1
        if args.stage == "freeze":
            manifest = freeze_manifest(
                authorized=args.authorize_final_freeze,
                root=ROOT,
                config_path=args.config,
                config_schema_path=args.config_schema,
            )
            config = load_config(args.config.resolve(), args.config_schema.resolve())
            output = safe_relative_path(ROOT, str(config["manifest_output"]))
            print(
                json.dumps(
                    {
                        "status": manifest["status"],
                        "manifest": output.relative_to(ROOT).as_posix(),
                        "manifest_sha256": sha256_file(output),
                        "artifacts": manifest["artifact_count"],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
        print(
            json.dumps(
                verify_frozen_manifest(
                    root=ROOT,
                    config_path=args.config,
                    config_schema_path=args.config_schema,
                ),
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except (ReadinessError, PermissionError, FileNotFoundError, ValueError, subprocess.CalledProcessError) as exc:
        payload: dict[str, Any] = {"status": "FAIL", "error": str(exc)}
        if isinstance(exc, ReadinessError):
            payload["errors"] = exc.errors
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
