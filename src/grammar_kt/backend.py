"""Auditable prompt-in/raw-response-out model invocation.

Every call retains the effective prompt, raw response, command metadata, and
transport logs in one unit directory. ``fixture_file`` is a deterministic
transport used by tests; ``codex_exec`` is the research backend.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .io import repo_path, utc_now, write_json


def _evidence_paths(unit_dir: Path) -> tuple[Path, Path, Path, Path, Path]:
    unit_dir.mkdir(parents=True, exist_ok=True)
    paths = tuple(
        unit_dir / name
        for name in (
            "rendered_prompt.txt",
            "raw_output.txt",
            "events.jsonl",
            "stderr.txt",
            "invocation.json",
        )
    )
    if any(item.exists() for item in paths):
        raise RuntimeError(f"refusing to overwrite model evidence: {unit_dir}")
    return paths


def _invocation_metadata(
    settings: dict[str, Any],
    command: list[str],
    output_schema: Path,
    instructions: Path,
    started: str,
    finished: str,
    returncode: int,
    timed_out: bool,
) -> dict[str, Any]:
    return {
        "backend": settings["backend"],
        "model": settings.get("model"),
        "reasoning_effort": settings.get("reasoning_effort"),
        "reasoning_options": settings.get("reasoning_options", {}),
        "timeout_seconds": settings.get("timeout_seconds"),
        "command": command,
        "output_schema": str(output_schema),
        "instructions": str(instructions),
        "started_utc": started,
        "finished_utc": finished,
        "returncode": returncode,
        "timed_out": timed_out,
        "execution_isolation": {
            "sandbox": settings.get("sandbox"),
            "approval_policy": settings.get("approval_policy"),
            "ignore_user_config": settings.get("ignore_user_config", True),
            "ephemeral": settings.get("ephemeral", True),
        },
        "model_snapshot_pinned": bool(settings.get("model_snapshot_pinned", False)),
        "decoding_parameters_pinned": bool(settings.get("decoding_parameters_pinned", False)),
    }


def invoke_model(
    *,
    prompt: str,
    output_schema: Path,
    instructions: Path,
    unit_dir: Path,
    settings: dict[str, Any],
) -> tuple[Path, int]:
    """Invoke the selected backend and retain all transport evidence."""

    prompt_path, raw_path, events_path, stderr_path, metadata_path = _evidence_paths(unit_dir)
    prompt_path.write_text(prompt, encoding="utf-8")
    backend = settings["backend"]

    if backend == "fixture_file":
        response = repo_path(settings["response_file"])
        shutil.copy2(response, raw_path)
        events_path.write_text("", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        started = finished = utc_now()
        command = ["fixture_file", str(response)]
        returncode = 0
        timed_out = False
    elif backend == "codex_exec":
        timed_out = False
        with tempfile.TemporaryDirectory(prefix="grammar-kt-model-") as temporary:
            workspace = Path(temporary)
            subprocess.run(["git", "init", "-q", "-b", "main", str(workspace)], check=True)
            shutil.copy2(instructions, workspace / "AGENTS.md")
            command = ["codex", "--ask-for-approval", settings.get("approval_policy", "never"), "exec"]
            if settings.get("ignore_user_config", True):
                command.append("--ignore-user-config")
            if settings.get("ephemeral", True):
                command.append("--ephemeral")
            command += [
                "--sandbox",
                settings.get("sandbox", "read-only"),
                "--model",
                settings["model"],
                "--config",
                f'model_reasoning_effort="{settings["reasoning_effort"]}"',
            ]
            for key, value in sorted(settings.get("reasoning_options", {}).items()):
                command += ["--config", f"{key}={json.dumps(value, sort_keys=True)}"]
            command += [
                "--json",
                "--output-schema",
                str(output_schema),
                "--output-last-message",
                str(raw_path),
                "--cd",
                str(workspace),
                "-",
            ]
            started = utc_now()
            try:
                result = subprocess.run(
                    command,
                    input=prompt,
                    text=True,
                    capture_output=True,
                    env={**os.environ, "NO_COLOR": "1"},
                    timeout=settings.get("timeout_seconds"),
                    check=False,
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
    else:
        raise ValueError(f"unknown model backend: {backend}")

    write_json(
        metadata_path,
        _invocation_metadata(
            settings,
            command,
            output_schema,
            instructions,
            started,
            finished,
            returncode,
            timed_out,
        ),
    )
    return raw_path, returncode


def save_model_result(unit_dir: Path, parsed: Any, errors: list[str]) -> None:
    write_json(unit_dir / "parsed_output.json", parsed)
    write_json(unit_dir / "validation.json", {"valid": not errors, "errors": errors})
