"""Machine-readable contract validation and literal template substitution."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

from jsonschema.validators import validator_for

from .io import read_json, read_jsonl


def validate_value(value: Any, schema_path: Path, *, label: str) -> None:
    schema = read_json(schema_path)
    validator_class = validator_for(schema)
    validator_class.check_schema(schema)
    errors = sorted(validator_class(schema).iter_errors(value), key=lambda error: list(error.path))
    if errors:
        first = errors[0]
        location = ".".join(str(part) for part in first.path) or "<root>"
        raise ValueError(f"{label} at {location}: {first.message}")


def validate_jsonl(path: Path, schema_path: Path, *, label: str) -> int:
    rows = read_jsonl(path)
    for index, row in enumerate(rows, 1):
        validate_value(row, schema_path, label=f"{label} row {index}")
    return len(rows)


def render_template(template: str, values: dict[str, Any]) -> str:
    """Replace only explicit ``{{name}}`` or legacy ``{name}`` placeholders."""

    rendered = template
    for key, value in values.items():
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        rendered = rendered.replace("{{" + key + "}}", text)
        rendered = rendered.replace("{" + key + "}", text)
    unresolved = sorted(set(re.findall(r"\{\{?[A-Za-z0-9_]+\}?\}", rendered)))
    if unresolved:
        raise ValueError(f"unresolved template placeholders: {unresolved}")
    return rendered


def declared_hashes(paths: Iterable[Path]) -> list[dict[str, Any]]:
    from .manifests import describe

    return [describe(path) for path in paths]
