"""Minimal prompt-in/raw-response-out model backends.

Every call retains the effective prompt, command, raw response, transport logs,
and parsed/validation files in one unit directory.  Reproducibility comes from
Git plus the resolved experiment, rather than a parallel hash graph.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .io import utc_now, write_json


@dataclass(frozen=True)
class BackendResult:
    raw_path: Path
    metadata_path: Path
    returncode: int


class ModelBackend(Protocol):
    def invoke(self, *, prompt: str, output_schema: Path, instructions: Path,
               unit_dir: Path, config: dict[str, Any]) -> BackendResult: ...


def _paths(unit_dir: Path) -> tuple[Path, Path, Path, Path, Path]:
    unit_dir.mkdir(parents=True, exist_ok=True)
    paths = tuple(unit_dir / name for name in (
        "rendered_prompt.txt", "raw_output.txt", "events.jsonl", "stderr.txt", "invocation.json"
    ))
    if any(item.exists() for item in paths):
        raise RuntimeError(f"refusing to overwrite model evidence: {unit_dir}")
    return paths


def _metadata(config: dict[str, Any], command: list[str], schema: Path,
              instructions: Path, started: str, finished: str, returncode: int,
              timed_out: bool) -> dict[str, Any]:
    return {
        "backend": config["backend"],
        "model": config.get("model"),
        "reasoning_effort": config.get("reasoning_effort"),
        "reasoning_options": config.get("reasoning_options", {}),
        "timeout_seconds": config.get("timeout_seconds"),
        "command": command,
        "output_schema": str(schema),
        "instructions": str(instructions),
        "started_utc": started,
        "finished_utc": finished,
        "returncode": returncode,
        "timed_out": timed_out,
        "execution_isolation": {
            "sandbox": config.get("sandbox"),
            "approval_policy": config.get("approval_policy"),
            "ignore_user_config": config.get("ignore_user_config", True),
            "ephemeral": config.get("ephemeral", True),
        },
        "model_snapshot_pinned": bool(config.get("model_snapshot_pinned", False)),
        "decoding_parameters_pinned": bool(config.get("decoding_parameters_pinned", False)),
    }


class CodexExecBackend:
    def invoke(self, *, prompt: str, output_schema: Path, instructions: Path,
               unit_dir: Path, config: dict[str, Any]) -> BackendResult:
        prompt_path, raw_path, events_path, stderr_path, metadata_path = _paths(unit_dir)
        prompt_path.write_text(prompt, encoding="utf-8")
        timed_out = False
        with tempfile.TemporaryDirectory(prefix="grammar-kt-model-") as temporary:
            workspace = Path(temporary)
            subprocess.run(["git", "init", "-q", "-b", "main", str(workspace)], check=True)
            shutil.copy2(instructions, workspace / "AGENTS.md")
            command = ["codex", "--ask-for-approval", config.get("approval_policy", "never"), "exec"]
            if config.get("ignore_user_config", True):
                command.append("--ignore-user-config")
            if config.get("ephemeral", True):
                command.append("--ephemeral")
            command += [
                "--sandbox", config.get("sandbox", "read-only"),
                "--model", config["model"],
                "--config", f'model_reasoning_effort="{config["reasoning_effort"]}"',
            ]
            for key, value in sorted(config.get("reasoning_options", {}).items()):
                command += ["--config", f"{key}={json.dumps(value, sort_keys=True)}"]
            command += [
                "--json", "--output-schema", str(output_schema),
                "--output-last-message", str(raw_path), "--cd", str(workspace), "-",
            ]
            started = utc_now()
            try:
                result = subprocess.run(
                    command, input=prompt, text=True, capture_output=True,
                    env={**os.environ, "NO_COLOR": "1"},
                    timeout=config.get("timeout_seconds"), check=False,
                )
                stdout, stderr, returncode = result.stdout, result.stderr, result.returncode
            except subprocess.TimeoutExpired as error:
                timed_out = True
                stdout = error.stdout or ""
                stderr = (error.stderr or "") + "\nmodel invocation timed out\n"
                if isinstance(stdout, bytes):
                    stdout = stdout.decode(errors="replace")
                if isinstance(stderr, bytes):
                    stderr = stderr.decode(errors="replace")
                returncode = 124
            finished = utc_now()
        events_path.write_text(stdout, encoding="utf-8")
        stderr_path.write_text(stderr, encoding="utf-8")
        if not raw_path.exists():
            raw_path.write_text("", encoding="utf-8")
        write_json(metadata_path, _metadata(config, command, output_schema, instructions, started, finished, returncode, timed_out))
        return BackendResult(raw_path, metadata_path, returncode)


class FixtureFileBackend:
    """Deterministic transport used only by tests and bounded demonstrations."""

    def invoke(self, *, prompt: str, output_schema: Path, instructions: Path,
               unit_dir: Path, config: dict[str, Any]) -> BackendResult:
        prompt_path, raw_path, events_path, stderr_path, metadata_path = _paths(unit_dir)
        prompt_path.write_text(prompt, encoding="utf-8")
        response = Path(config["response_file"]).expanduser().resolve()
        shutil.copy2(response, raw_path)
        events_path.write_text("", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        now = utc_now()
        command = ["fixture_file", str(response)]
        write_json(metadata_path, _metadata(config, command, output_schema, instructions, now, now, 0, False))
        return BackendResult(raw_path, metadata_path, 0)


def get_backend(name: str) -> ModelBackend:
    if name == "codex_exec":
        return CodexExecBackend()
    if name == "fixture_file":
        return FixtureFileBackend()
    raise ValueError(f"unknown model backend: {name}")


def save_model_result(unit_dir: Path, parsed: Any, errors: list[str]) -> None:
    write_json(unit_dir / "parsed_output.json", parsed)
    write_json(unit_dir / "validation.json", {"valid": not errors, "errors": errors})
