"""Small serialization and model-call helpers used by the chronological stages."""

from __future__ import annotations

import json
import subprocess
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Iterable

import yaml


ROOT = Path(__file__).resolve().parents[2]
ModelCall = Callable[[str, dict[str, Any], dict[str, Any], str, str, Path | None], dict[str, Any]]


def repo_path(path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else ROOT / value


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows = []
    for line in repo_path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def read_yaml(path: str | Path) -> dict[str, Any]:
    value = yaml.safe_load(repo_path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a YAML mapping: {path}")
    return value


def read_text(path: str | Path) -> str:
    return repo_path(path).read_text(encoding="utf-8")


def write_json(path: str | Path, value: Any) -> None:
    target = repo_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: str | Path, rows: Iterable[dict[str, Any]]) -> None:
    target = repo_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def write_yaml(path: str | Path, value: Any) -> None:
    target = repo_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        yaml.safe_dump(value, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )


def load_experiment(path_or_name: str | Path = "base") -> dict[str, Any]:
    """Load one self-contained experiment file; there is no inheritance graph."""

    path = Path(path_or_name)
    if not path.suffix:
        path = Path("experiments") / f"{path}.yaml"
    return read_yaml(path)


def load_typed_resource(data_path: str | Path, schema_path: str | Path) -> list[dict[str, Any]]:
    """Read the selected EGP extract and validate its declared evidence fields once."""

    schema = read_yaml(schema_path)
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
        replacement = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
        rendered = rendered.replace("{{" + name + "}}", replacement)
    unresolved = [part.split("}}", 1)[0] for part in rendered.split("{{")[1:]]
    if unresolved:
        raise ValueError(f"unresolved prompt placeholders: {unresolved}")
    return rendered


def _fixture_response(prompt: str, config: dict[str, Any], stage: str, call_key: str) -> dict[str, Any]:
    fixtures = read_yaml(config["fixture_responses"])
    section = fixtures[stage]
    entry = section.get(call_key, section.get("default"))
    if entry is None:
        raise KeyError(f"fixture responses lack {stage}/{call_key}")
    for variant in entry.get("variants", []):
        if variant["prompt_contains"] in prompt:
            return deepcopy(variant["response"])
    return deepcopy(entry["response"])


def call_model(
    prompt: str,
    input_data: dict[str, Any],
    config: dict[str, Any],
    stage: str,
    call_key: str,
    evidence_dir: Path | None,
) -> dict[str, Any]:
    """Make one JSON model call and retain the evidence a researcher needs."""

    if config["model"] == "fixture":
        parsed = _fixture_response(prompt, config, stage, call_key)
        raw = json.dumps(parsed, ensure_ascii=False)
    else:
        command = [
            "codex",
            "exec",
            "--ephemeral",
            "--sandbox",
            "read-only",
            "--model",
            config["model"],
            "--config",
            f'model_reasoning_effort="{config.get("reasoning_effort", "medium")}"',
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
        target = repo_path(evidence_dir / "rendered_prompt.txt")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(prompt, encoding="utf-8")
        raw_target = repo_path(evidence_dir / "raw_output.txt")
        raw_target.write_text(raw + "\n", encoding="utf-8")
        write_json(evidence_dir / "parsed_result.json", parsed)
        write_json(
            evidence_dir / "model_settings.json",
            {
                "model": config["model"],
                "reasoning_effort": config.get("reasoning_effort"),
            },
        )
    return parsed
