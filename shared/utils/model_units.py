"""Canonical on-disk evidence layout for one model invocation unit."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any

from .io import read_json, sha256_file, write_json


UNIT_FILES = (
    "input.json", "rendered_prompt.txt", "invocation.json", "raw_output.txt",
    "parsed_output.json", "validation.json",
)


def begin_model_unit(unit_dir: Path, input_value: Any) -> None:
    unit_dir.mkdir(parents=True, exist_ok=False)
    write_json(unit_dir / "input.json", input_value)
    (unit_dir / "attempts").mkdir()


def begin_attempt(unit_dir: Path, attempt: int) -> Path:
    path = unit_dir / "attempts" / f"attempt_{attempt:02d}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def finish_attempt(
    attempt_dir: Path,
    *,
    parsed: Any | None,
    validation: dict[str, Any],
) -> None:
    write_json(attempt_dir / "parsed_output.json", parsed)
    write_json(attempt_dir / "validation.json", validation)


def select_attempt(unit_dir: Path, attempt_dir: Path) -> None:
    required = ("rendered_prompt.txt", "invocation.json", "raw_output.txt", "validation.json")
    for name in required:
        source = attempt_dir / name
        if not source.is_file():
            raise RuntimeError(f"cannot select incomplete model attempt: {source}")
        shutil.copy2(source, unit_dir / name)
    shutil.copy2(attempt_dir / "parsed_output.json", unit_dir / "parsed_output.json")


def invocation_reuse_key(
    *,
    prompt: str,
    config: dict[str, Any],
    scientific_inputs: list[dict[str, Any]],
    implementation: list[dict[str, Any]],
) -> dict[str, Any]:
    """Values that must match before an existing model result may be reused."""

    return {
        "backend": config["backend"],
        "model": config.get("model"),
        "reasoning_effort": config.get("reasoning_effort"),
        "reasoning_options": config.get("reasoning_options", {}),
        "timeout_seconds": config.get("timeout_seconds"),
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "scientific_inputs": scientific_inputs,
        "implementation": implementation,
        "execution_isolation": {
            "sandbox": config.get("sandbox"),
            "approval_policy": config.get("approval_policy"),
            "ignore_user_config": bool(config.get("ignore_user_config", True)),
            "ephemeral": bool(config.get("ephemeral", True)),
        },
    }


def completed_model_unit(
    unit_dir: Path,
    expected_input: Any,
    expected_invocation: dict[str, Any] | None = None,
) -> bool:
    input_path = unit_dir / "input.json"
    complete = (
        input_path.is_file()
        and read_json(input_path) == expected_input
        and all((unit_dir / name).is_file() for name in UNIT_FILES)
        and read_json(unit_dir / "validation.json").get("valid") is True
    )
    if not complete or expected_invocation is None:
        return complete
    invocation = read_json(unit_dir / "invocation.json")
    recorded_files_match = (
        invocation.get("prompt_sha256") == sha256_file(unit_dir / "rendered_prompt.txt")
        and invocation.get("raw_output_sha256") == sha256_file(unit_dir / "raw_output.txt")
    )
    return recorded_files_match and all(
        invocation.get(key) == value for key, value in expected_invocation.items()
    )
