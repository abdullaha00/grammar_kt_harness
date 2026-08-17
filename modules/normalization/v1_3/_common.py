#!/usr/bin/env python3
"""Shared frozen helpers for independent v1.3 EGP annotations."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "specification"
INPUT = ROOT / "input"
OUTPUTS = ROOT / "outputs"
LOGS = ROOT / "logs"
EXECUTION_PATH = SPEC / "execution.json"
MAPPING_SCHEMA_PATH = SPEC / "mapping_output_schema.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number}: expected object")
            rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=False)
        handle.write("\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    text = "\n".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in rows)
    write_text(path, text + ("\n" if rows else ""))


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write(value)


def execution_config() -> dict[str, Any]:
    return load_json(EXECUTION_PATH)


def verify_frozen_manifest() -> list[str]:
    manifest = ROOT / "FROZEN_MANIFEST.sha256"
    if not manifest.exists():
        return ["FROZEN_MANIFEST.sha256 is missing"]
    errors: list[str] = []
    for line_number, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            expected, relative = line.split("  ", 1)
        except ValueError:
            errors.append(f"manifest line {line_number} is malformed")
            continue
        path = ROOT / relative
        if not path.is_file():
            errors.append(f"frozen file missing: {relative}")
        elif sha256_path(path) != expected:
            errors.append(f"frozen file hash mismatch: {relative}")
    return errors


def verify_source() -> Path:
    config = execution_config()
    source = Path(config["source_jsonl_original_path"])
    if not source.is_file():
        raise RuntimeError(f"source JSONL is missing: {source}")
    actual = sha256_path(source)
    expected = config["source_jsonl_sha256"]
    if actual != expected:
        raise RuntimeError(f"source hash mismatch: expected {expected}, got {actual}")
    return source


def verify_prior_pilots() -> list[str]:
    config = execution_config()
    v1 = Path(config["v1_pilot_path"])
    v1_1 = Path(config["v1_1_pilot_path"])
    previous = Path(config["previous_pilot_path"])
    checks = [
        (v1 / "REPORT.md", config["v1_pilot_report_sha256"], "v1 report"),
        (v1 / "specification" / "schema.txt", config["previous_schema_sha256"], "v1 schema"),
        (v1_1 / "REPORT.md", config["v1_1_pilot_report_sha256"], "v1.1 report"),
        (v1_1 / "specification" / "schema.txt", config["previous_schema_sha256"], "v1.1 schema"),
        (previous / "REPORT.md", config["previous_pilot_report_sha256"], "v1.2 report"),
        (previous / "specification" / "schema.txt", config["previous_schema_sha256"], "v1.2 schema"),
    ]
    errors: list[str] = []
    for path, expected, label in checks:
        if not path.is_file():
            errors.append(f"{label} missing: {path}")
        elif sha256_path(path) != expected:
            errors.append(f"{label} hash mismatch: {path}")
    schema = SPEC / "schema.txt"
    if schema.is_file() and sha256_path(schema) != config["previous_schema_sha256"]:
        errors.append("v1.3 schema is not byte-identical to the frozen v1-v1.2 schema")
    for repo, expected, label in (
        (v1, config["v1_pilot_final_commit"], "v1 pilot"),
        (v1_1, config["v1_1_pilot_final_commit"], "v1.1 pilot"),
        (previous, config["previous_pilot_final_commit"], "v1.2 pilot"),
    ):
        try:
            actual = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=repo, text=True
            ).strip()
        except (OSError, subprocess.CalledProcessError):
            errors.append(f"cannot resolve {label} Git HEAD: {repo}")
        else:
            if actual != expected:
                errors.append(f"{label} Git HEAD mismatch: expected {expected}, got {actual}")
    return errors


def frozen_context(phase: int, replacements: dict[str, str]) -> str:
    schema = (SPEC / "schema.txt").read_text(encoding="utf-8")
    rulebook = (SPEC / "rulebook.md").read_text(encoding="utf-8")
    template = (SPEC / f"phase{phase}_prompt.txt").read_text(encoding="utf-8")
    rendered = template
    for key, value in replacements.items():
        rendered = rendered.replace("{" + key + "}", value)
    unresolved = [token for token in ("{record}", "{phase1_mapping}", "{examples}") if token in rendered]
    if unresolved:
        raise ValueError(f"unresolved prompt placeholders: {unresolved}")
    return (
        "FROZEN GRAMMAR SCHEMA\n"
        "=====================\n"
        f"{schema}\n"
        "FROZEN NORMALIZATION RULEBOOK\n"
        "=============================\n"
        f"{rulebook}\n"
        f"FROZEN PHASE {phase} PROMPT\n"
        "=====================\n"
        f"{rendered}"
    )


def codex_command(workspace: Path, raw_output: Path) -> list[str]:
    config = execution_config()
    return [
        "codex",
        "--ask-for-approval",
        config["approval_policy"],
        "exec",
        "--ignore-user-config",
        "--ephemeral",
        "--sandbox",
        config["sandbox"],
        "--model",
        config["model"],
        "--config",
        f'model_reasoning_effort="{config["model_reasoning_effort"]}"',
        "--json",
        "--output-schema",
        str(MAPPING_SCHEMA_PATH),
        "--output-last-message",
        str(raw_output),
        "--cd",
        str(workspace),
        "-",
    ]


def run_codex_attempt(
    *,
    phase: int,
    unit_id: str,
    egp_id: str,
    attempt: int,
    prompt: str,
    raw_output: Path,
    log_dir: Path,
) -> dict[str, Any]:
    log_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{unit_id}.attempt-{attempt:02d}"
    prompt_path = log_dir / f"{stem}.prompt.txt"
    events_path = log_dir / f"{stem}.events.jsonl"
    stderr_path = log_dir / f"{stem}.stderr.txt"
    metadata_path = log_dir / f"{stem}.json"
    for path in (prompt_path, events_path, stderr_path, metadata_path, raw_output):
        if path.exists():
            raise RuntimeError(f"refusing to overwrite existing run file: {path}")
    write_text(prompt_path, prompt)

    with tempfile.TemporaryDirectory(prefix=f"egp-v13-p{phase}-{unit_id}-") as tmp:
        workspace = Path(tmp)
        subprocess.run(
            ["git", "init", "-q", "-b", "main", str(workspace)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        shutil.copy2(ROOT / "AGENTS.md", workspace / "AGENTS.md")
        command = codex_command(workspace, raw_output)
        started = utc_now()
        process = subprocess.run(
            command,
            input=prompt,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=ROOT,
            env={**os.environ, "NO_COLOR": "1"},
            check=False,
        )
        finished = utc_now()

    write_text(events_path, process.stdout)
    write_text(stderr_path, process.stderr)
    metadata = {
        "phase": phase,
        "unit_id": unit_id,
        "egp_id": egp_id,
        "attempt": attempt,
        "started_utc": started,
        "finished_utc": finished,
        "returncode": process.returncode,
        "command": command,
        "prompt_path": str(prompt_path.relative_to(ROOT)),
        "prompt_sha256": sha256_path(prompt_path),
        "raw_output_path": str(raw_output.relative_to(ROOT)),
        "raw_output_sha256": sha256_path(raw_output) if raw_output.exists() else None,
        "events_path": str(events_path.relative_to(ROOT)),
        "stderr_path": str(stderr_path.relative_to(ROOT)),
        "isolated_workspace_contents": [".git/", "AGENTS.md"],
        "session_resumed": False,
        "duplicate_status_exposed_to_model": False,
    }
    return metadata
