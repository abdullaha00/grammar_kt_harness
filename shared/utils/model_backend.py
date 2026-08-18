"""Minimal prompt-in/raw-artifacts-out backend interface.

Scientific modules render prompts. Backends only transport the exact rendered
text and retain the command/events/stderr/raw response needed to audit that
transport.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

from .io import display_path, sha256_file, utc_now, write_json
from .manifests import describe


@dataclass(frozen=True)
class BackendResult:
    raw_path: Path
    metadata_path: Path
    returncode: int


class ModelBackend(Protocol):
    name: str

    def invoke(
        self,
        *,
        prompt: str,
        output_schema: Path,
        instructions: Path,
        raw_path: Path,
        log_dir: Path,
        stem: str,
        config: dict[str, Any],
        context: dict[str, Any],
        invocation_dir: Path | None = None,
    ) -> BackendResult: ...


@lru_cache(maxsize=1)
def codex_cli_version() -> str:
    return subprocess.check_output(["codex", "--version"], text=True).strip()


def _artifact_paths(
    *, log_dir: Path, stem: str, invocation_dir: Path | None
) -> tuple[Path, Path, Path, Path]:
    if invocation_dir is not None:
        invocation_dir.mkdir(parents=True, exist_ok=True)
        return (
            invocation_dir / "rendered_prompt.txt",
            invocation_dir / "events.jsonl",
            invocation_dir / "stderr.txt",
            invocation_dir / "invocation.json",
        )
    log_dir.mkdir(parents=True, exist_ok=True)
    return (
        log_dir / f"{stem}.prompt.txt",
        log_dir / f"{stem}.events.jsonl",
        log_dir / f"{stem}.stderr.txt",
        log_dir / f"{stem}.json",
    )


def _metadata(
    *,
    context: dict[str, Any],
    backend: str,
    transport: str,
    config: dict[str, Any],
    command: list[str],
    prompt_path: Path,
    raw_path: Path,
    events_path: Path,
    stderr_path: Path,
    output_schema: Path,
    instructions: Path,
    started: str,
    finished: str,
    returncode: int,
    timed_out: bool,
) -> dict[str, Any]:
    return {
        **context,
        "backend": backend,
        "transport": transport,
        "model": config.get("model"),
        "model_snapshot_pinned": bool(config.get("model_snapshot_pinned", False)),
        "reasoning_effort": config.get("reasoning_effort"),
        "reasoning_options": config.get("reasoning_options", {}),
        "decoding_parameters_pinned": bool(config.get("decoding_parameters_pinned", False)),
        "timeout_seconds": config.get("timeout_seconds"),
        "started_utc": started,
        "finished_utc": finished,
        "returncode": returncode,
        "timed_out": timed_out,
        "command": command,
        "prompt_path": display_path(prompt_path),
        "prompt_sha256": sha256_file(prompt_path),
        "schema": describe(output_schema),
        "instructions": describe(instructions),
        "raw_output_path": display_path(raw_path),
        "raw_output_sha256": sha256_file(raw_path) if raw_path.exists() else None,
        "events_path": display_path(events_path),
        "stderr_path": display_path(stderr_path),
        "execution_isolation": {
            "sandbox": config.get("sandbox"),
            "approval_policy": config.get("approval_policy"),
            "ignore_user_config": bool(config.get("ignore_user_config", True)),
            "ephemeral": bool(config.get("ephemeral", True)),
        },
        "session_resumed": False,
    }


class CodexExecBackend:
    name = "codex_exec"

    def invoke(
        self,
        *,
        prompt: str,
        output_schema: Path,
        instructions: Path,
        raw_path: Path,
        log_dir: Path,
        stem: str,
        config: dict[str, Any],
        context: dict[str, Any],
        invocation_dir: Path | None = None,
    ) -> BackendResult:
        actual_cli_version = codex_cli_version()
        expected_cli_version = config.get("codex_cli_version")
        if expected_cli_version and actual_cli_version not in {
            expected_cli_version,
            f"codex-cli {expected_cli_version}",
        }:
            raise RuntimeError(
                f"Codex CLI version mismatch: expected {expected_cli_version}, got {actual_cli_version}"
            )
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path, events_path, stderr_path, metadata_path = _artifact_paths(
            log_dir=log_dir, stem=stem, invocation_dir=invocation_dir
        )
        for path in (prompt_path, events_path, stderr_path, metadata_path, raw_path):
            if path.exists():
                raise RuntimeError(f"refusing to overwrite model artifact: {path}")
        prompt_path.write_text(prompt, encoding="utf-8")
        command: list[str]
        timed_out = False
        with tempfile.TemporaryDirectory(prefix=f"grammar-kt-{stem}-") as temporary:
            workspace = Path(temporary)
            subprocess.run(
                ["git", "init", "-q", "-b", "main", str(workspace)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            shutil.copy2(instructions, workspace / "AGENTS.md")
            command = ["codex", "--ask-for-approval", config["approval_policy"], "exec"]
            if config.get("ignore_user_config", True):
                command.append("--ignore-user-config")
            if config.get("ephemeral", True):
                command.append("--ephemeral")
            reasoning_options = config.get("reasoning_options", {})
            if not isinstance(reasoning_options, dict):
                raise ValueError("reasoning_options must be a mapping")
            command.extend(
                [
                    "--sandbox", config["sandbox"],
                    "--model", config["model"],
                    "--config", f'model_reasoning_effort="{config["reasoning_effort"]}"',
                ]
            )
            for key, value in sorted(reasoning_options.items()):
                command.extend(["--config", f"{key}={json.dumps(value, sort_keys=True)}"])
            command.extend(
                [
                    "--json",
                    "--output-schema", str(output_schema.resolve()),
                    "--output-last-message", str(raw_path.resolve()),
                    "--cd", str(workspace),
                    "-",
                ]
            )
            started = utc_now()
            try:
                process = subprocess.run(
                    command,
                    input=prompt,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env={**os.environ, "NO_COLOR": "1"},
                    timeout=config.get("timeout_seconds"),
                    check=False,
                )
                stdout, stderr, returncode = process.stdout, process.stderr, process.returncode
            except subprocess.TimeoutExpired as error:
                timed_out = True
                stdout = error.stdout or ""
                stderr = error.stderr or ""
                if isinstance(stdout, bytes):
                    stdout = stdout.decode("utf-8", errors="replace")
                if isinstance(stderr, bytes):
                    stderr = stderr.decode("utf-8", errors="replace")
                stderr += f"\nTimed out after {config.get('timeout_seconds')} seconds.\n"
                returncode = 124
            finished = utc_now()
        events_path.write_text(stdout, encoding="utf-8")
        stderr_path.write_text(stderr, encoding="utf-8")
        raw_output_was_missing = not raw_path.is_file()
        if raw_output_was_missing:
            raw_path.write_text("", encoding="utf-8")
        metadata = _metadata(
            context=context,
            backend=self.name,
            transport="codex-cli exec",
            config=config,
            command=command,
            prompt_path=prompt_path,
            raw_path=raw_path,
            events_path=events_path,
            stderr_path=stderr_path,
            output_schema=output_schema,
            instructions=instructions,
            started=started,
            finished=finished,
            returncode=returncode,
            timed_out=timed_out,
        )
        metadata["codex_cli_version"] = actual_cli_version
        metadata["isolated_workspace_contents"] = [".git/", "AGENTS.md"]
        metadata["raw_output_was_missing"] = raw_output_was_missing
        write_json(metadata_path, metadata)
        return BackendResult(raw_path=raw_path, metadata_path=metadata_path, returncode=returncode)


class FixtureFileBackend:
    """Deterministic transport fixture for harness tests; it is not a model."""

    name = "fixture_file"

    def invoke(
        self,
        *,
        prompt: str,
        output_schema: Path,
        instructions: Path,
        raw_path: Path,
        log_dir: Path,
        stem: str,
        config: dict[str, Any],
        context: dict[str, Any],
        invocation_dir: Path | None = None,
    ) -> BackendResult:
        prompt_path, events_path, stderr_path, metadata_path = _artifact_paths(
            log_dir=log_dir, stem=stem, invocation_dir=invocation_dir
        )
        response_path = Path(config["response_file"]).expanduser().resolve()
        for path in (prompt_path, events_path, stderr_path, metadata_path, raw_path):
            if path.exists():
                raise RuntimeError(f"refusing to overwrite model artifact: {path}")
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path.write_text(prompt, encoding="utf-8")
        shutil.copy2(response_path, raw_path)
        events_path.write_text("", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        now = utc_now()
        metadata = _metadata(
            context={**context, "fixture_response": describe(response_path), "not_a_model": True},
            backend=self.name,
            transport="local fixture copy",
            config=config,
            command=["fixture_file", str(response_path)],
            prompt_path=prompt_path,
            raw_path=raw_path,
            events_path=events_path,
            stderr_path=stderr_path,
            output_schema=output_schema,
            instructions=instructions,
            started=now,
            finished=now,
            returncode=0,
            timed_out=False,
        )
        write_json(metadata_path, metadata)
        return BackendResult(raw_path=raw_path, metadata_path=metadata_path, returncode=0)


BACKENDS: dict[str, type[ModelBackend]] = {
    CodexExecBackend.name: CodexExecBackend,
    FixtureFileBackend.name: FixtureFileBackend,
}


def get_backend(name: str) -> ModelBackend:
    try:
        return BACKENDS[name]()
    except KeyError as error:
        raise ValueError(f"unknown model backend: {name}; available: {sorted(BACKENDS)}") from error
