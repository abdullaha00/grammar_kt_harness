"""One small model-backend abstraction; current implementation is Codex exec."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from .io import display_path, sha256_file, utc_now, write_json


@dataclass(frozen=True)
class BackendResult:
    raw_path: Path
    metadata_path: Path
    returncode: int


@lru_cache(maxsize=1)
def codex_cli_version() -> str:
    return subprocess.check_output(["codex", "--version"], text=True).strip()


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
        log_dir.mkdir(parents=True, exist_ok=True)
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path = log_dir / f"{stem}.prompt.txt"
        events_path = log_dir / f"{stem}.events.jsonl"
        stderr_path = log_dir / f"{stem}.stderr.txt"
        metadata_path = log_dir / f"{stem}.json"
        for path in (prompt_path, events_path, stderr_path, metadata_path, raw_path):
            if path.exists():
                raise RuntimeError(f"refusing to overwrite model artifact: {path}")
        prompt_path.write_text(prompt, encoding="utf-8")
        with tempfile.TemporaryDirectory(prefix=f"grammar-kt-{stem}-") as temporary:
            workspace = Path(temporary)
            subprocess.run(
                ["git", "init", "-q", "-b", "main", str(workspace)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            shutil.copy2(instructions, workspace / "AGENTS.md")
            command = [
                "codex",
                "--ask-for-approval",
                config["approval_policy"],
                "exec",
            ]
            if config.get("ignore_user_config", True):
                command.append("--ignore-user-config")
            if config.get("ephemeral", True):
                command.append("--ephemeral")
            command.extend(
                [
                    "--sandbox",
                    config["sandbox"],
                    "--model",
                    config["model"],
                    "--config",
                    f'model_reasoning_effort="{config["reasoning_effort"]}"',
                    "--json",
                    "--output-schema",
                    str(output_schema.resolve()),
                    "--output-last-message",
                    str(raw_path.resolve()),
                    "--cd",
                    str(workspace),
                    "-",
                ]
            )
            started = utc_now()
            process = subprocess.run(
                command,
                input=prompt,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={**os.environ, "NO_COLOR": "1"},
                check=False,
            )
            finished = utc_now()
        events_path.write_text(process.stdout, encoding="utf-8")
        stderr_path.write_text(process.stderr, encoding="utf-8")
        metadata = {
            **context,
            "backend": self.name,
            "transport": "codex-cli exec",
            "codex_cli_version": actual_cli_version,
            "model": config["model"],
            "model_snapshot_pinned": False,
            "reasoning_effort": config["reasoning_effort"],
            "decoding_parameters_pinned": False,
            "started_utc": started,
            "finished_utc": finished,
            "returncode": process.returncode,
            "command": command,
            "prompt_path": display_path(prompt_path),
            "prompt_sha256": sha256_file(prompt_path),
            "raw_output_path": display_path(raw_path),
            "raw_output_sha256": sha256_file(raw_path) if raw_path.exists() else None,
            "events_path": display_path(events_path),
            "stderr_path": display_path(stderr_path),
            "isolated_workspace_contents": [".git/", "AGENTS.md"],
            "session_resumed": False,
        }
        write_json(metadata_path, metadata)
        return BackendResult(raw_path=raw_path, metadata_path=metadata_path, returncode=process.returncode)


BACKENDS = {CodexExecBackend.name: CodexExecBackend}


def get_backend(name: str) -> CodexExecBackend:
    try:
        return BACKENDS[name]()
    except KeyError as error:
        raise ValueError(f"unknown model backend: {name}") from error
