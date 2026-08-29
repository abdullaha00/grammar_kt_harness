"""Audited Codex model calls for immutable, resumable research evidence."""

from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any

from .io import write_json


TOKEN_PATTERN = re.compile(r"total tokens used\s*\n?\s*([0-9,]+)", re.IGNORECASE)


def audited_model_call(
    prompt: str,
    *,
    model: str,
    reasoning_effort: str,
    input_data: dict[str, Any],
    stage: str,
    call_key: str,
    evidence_dir: Path | None = None,
) -> dict[str, Any]:
    """Make one call while retaining inputs, raw output, stderr, and usage.

    Files written here may reproduce consult-only source evidence. Callers must
    place the evidence directory in a restricted, untracked location.
    """

    if evidence_dir is None:
        raise ValueError("audited model calls require an evidence directory")
    evidence_dir.mkdir(parents=True, exist_ok=False)
    write_json(evidence_dir / "input.json", input_data)
    (evidence_dir / "rendered_prompt.txt").write_text(prompt, encoding="utf-8")
    command = [
        "codex",
        "exec",
        "--ephemeral",
        "--sandbox",
        "read-only",
        "--model",
        model,
        "--config",
        f'model_reasoning_effort="{reasoning_effort}"',
        "-",
    ]
    write_json(
        evidence_dir / "model_settings.json",
        {
            "model": model,
            "reasoning_effort": reasoning_effort,
            "stage": stage,
            "call_key": call_key,
            "command": command,
        },
    )
    started = time.monotonic()
    result = subprocess.run(
        command,
        cwd=evidence_dir,
        input=prompt,
        text=True,
        capture_output=True,
        check=False,
    )
    runtime = time.monotonic() - started
    raw = result.stdout.strip()
    (evidence_dir / "raw_output.txt").write_text(raw + "\n", encoding="utf-8")
    (evidence_dir / "cli_stderr.txt").write_text(result.stderr, encoding="utf-8")
    token_matches = TOKEN_PATTERN.findall(result.stderr)
    write_json(
        evidence_dir / "call_metadata.json",
        {
            "returncode": result.returncode,
            "runtime_seconds": runtime,
            "tokens_used": (
                int(token_matches[-1].replace(",", ""))
                if token_matches
                else None
            ),
            "token_metric": "codex_cli_total_tokens_used",
        },
    )
    if result.returncode != 0:
        raise RuntimeError(f"codex exec failed with return code {result.returncode}")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("model output must be one JSON object")
    write_json(evidence_dir / "parsed_result.json", parsed)
    return parsed
