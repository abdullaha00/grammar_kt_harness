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


def invoke_model(
    *,
    prompt: str,
    output_schema: Path,
    instructions: Path,
    unit_dir: Path,
    backend_config: dict[str, Any],
) -> tuple[Path, int]:
    """Invoke one explicitly configured transport and retain all evidence.

    ``fixture_file`` requires ``response_file``; ``codex_exec`` instead
    requires its model, reasoning, timeout, and isolation configuration.
    """

    unit_dir.mkdir(parents=True, exist_ok=True)
    prompt_path, raw_path, events_path, stderr_path, metadata_path = (
        unit_dir / name
        for name in (
            "rendered_prompt.txt",
            "raw_output.txt",
            "events.jsonl",
            "stderr.txt",
            "invocation.json",
        )
    )
    if any(
        path.exists()
        for path in (prompt_path, raw_path, events_path, stderr_path, metadata_path)
    ):
        raise RuntimeError(f"refusing to overwrite model evidence: {unit_dir}")
    prompt_path.write_text(prompt, encoding="utf-8")
    kind = backend_config["kind"]

    if kind == "fixture_file":
        response = repo_path(backend_config["response_file"])
        shutil.copy2(response, raw_path)
        events_path.write_text("", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        started = finished = utc_now()
        command = ["fixture_file", str(response)]
        returncode = 0
        timed_out = False
    elif kind == "codex_exec":
        timed_out = False
        with tempfile.TemporaryDirectory(prefix="grammar-kt-model-") as temporary:
            workspace = Path(temporary)
            subprocess.run(["git", "init", "-q", "-b", "main", str(workspace)], check=True)
            shutil.copy2(instructions, workspace / "AGENTS.md")
            command = ["codex", "--ask-for-approval", backend_config.get("approval_policy", "never"), "exec"]
            if backend_config.get("ignore_user_config", True):
                command.append("--ignore-user-config")
            if backend_config.get("ephemeral", True):
                command.append("--ephemeral")
            command += [
                "--sandbox",
                backend_config.get("sandbox", "read-only"),
                "--model",
                backend_config["model"],
                "--config",
                f'model_reasoning_effort="{backend_config["reasoning_effort"]}"',
            ]
            for key, value in sorted(backend_config.get("reasoning_options", {}).items()):
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
                    timeout=backend_config.get("timeout_seconds"),
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
        raise ValueError(f"unknown model backend kind: {kind}")

    write_json(
        metadata_path,
        {
            "backend": kind,
            "model": backend_config.get("model"),
            "reasoning_effort": backend_config.get("reasoning_effort"),
            "reasoning_options": backend_config.get("reasoning_options", {}),
            "timeout_seconds": backend_config.get("timeout_seconds"),
            "command": command,
            "output_schema": str(output_schema),
            "instructions": str(instructions),
            "started_utc": started,
            "finished_utc": finished,
            "returncode": returncode,
            "timed_out": timed_out,
            "execution_isolation": {
                "sandbox": backend_config.get("sandbox"),
                "approval_policy": backend_config.get("approval_policy"),
                "ignore_user_config": backend_config.get("ignore_user_config", True),
                "ephemeral": backend_config.get("ephemeral", True),
            },
            "model_snapshot_pinned": bool(backend_config.get("model_snapshot_pinned", False)),
            "decoding_parameters_pinned": bool(backend_config.get("decoding_parameters_pinned", False)),
        },
    )
    return raw_path, returncode


def save_model_result(unit_dir: Path, parsed: Any, errors: list[str]) -> None:
    write_json(unit_dir / "parsed_output.json", parsed)
    write_json(unit_dir / "validation.json", {"valid": not errors, "errors": errors})
