"""Small serialization, prompt, and model-call helpers."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Callable, Iterable

import yaml

ModelCall = Callable[..., dict[str, Any]]


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def read_yaml(path: str | Path) -> Any:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def read_text(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def write_json(path: str | Path, value: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: str | Path, rows: Iterable[dict[str, Any]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def write_yaml(path: str | Path, value: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        yaml.safe_dump(value, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )


def load_typed_resource(
    data_path: str | Path, schema: dict[str, Any]
) -> list[dict[str, Any]]:
    """Read the selected EGP extract and validate its declared evidence fields once."""

    fields = schema["fields"]
    allowed = set(fields)
    required = {name for name, declaration in fields.items() if declaration["required"]}
    rows = read_jsonl(data_path)
    for row in rows:
        missing = required - set(row)
        unknown = set(row) - allowed
        if missing or unknown:
            raise ValueError(
                f"typed resource {row.get('source_id', '<unknown>')}: "
                f"missing={sorted(missing)}, unknown={sorted(unknown)}"
            )
    return rows


def render(template: str, values: dict[str, Any]) -> str:
    rendered = template
    for name, value in values.items():
        replacement = (
            value
            if isinstance(value, str)
            else json.dumps(value, ensure_ascii=False, indent=2)
        )
        rendered = rendered.replace("{{" + name + "}}", replacement)
    unresolved = [part.split("}}", 1)[0] for part in rendered.split("{{")[1:]]
    if unresolved:
        raise ValueError(f"unresolved prompt placeholders: {unresolved}")
    return rendered


def _fixture_response(
    prompt: str,
    fixture_responses: dict[str, Any],
    stage: str,
    call_key: str,
) -> dict[str, Any]:
    section = fixture_responses[stage]
    entry = section.get(call_key, section.get("default"))
    if entry is None:
        raise KeyError(f"fixture responses lack {stage}/{call_key}")
    for variant in entry.get("variants", []):
        if variant["prompt_contains"] in prompt:
            return variant["response"]
    return entry["response"]


def call_model(
    prompt: str,
    *,
    model: str,
    reasoning_effort: str,
    input_data: dict[str, Any],
    stage: str,
    call_key: str,
    evidence_dir: Path | None = None,
    fixture_responses: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Make one JSON model call and retain the evidence a researcher needs."""

    if model == "fixture":
        if fixture_responses is None:
            raise ValueError("fixture model calls require fixture responses")
        parsed = _fixture_response(prompt, fixture_responses, stage, call_key)
        raw = json.dumps(parsed, ensure_ascii=False)
    else:
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
        result = subprocess.run(
            command,
            input=prompt,
            text=True,
            capture_output=True,
            check=True,
        )
        raw = result.stdout.strip()
        parsed = json.loads(raw)

    if evidence_dir is not None:
        write_json(evidence_dir / "input.json", input_data)
        target = evidence_dir / "rendered_prompt.txt"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(prompt, encoding="utf-8")
        raw_target = evidence_dir / "raw_output.txt"
        raw_target.write_text(raw + "\n", encoding="utf-8")
        write_json(evidence_dir / "parsed_result.json", parsed)
        write_json(
            evidence_dir / "model_settings.json",
            {
                "model": model,
                "reasoning_effort": reasoning_effort,
            },
        )
    return parsed
