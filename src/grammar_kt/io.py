"""Small JSON/YAML/path helpers shared by the harness."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml


ROOT = Path(__file__).resolve().parents[2]
DIMENSIONS = ("tense", "aspect", "voice", "polarity", "clause", "modal")


def path(value: str | Path) -> Path:
    candidate = Path(value).expanduser()
    return candidate.resolve() if candidate.is_absolute() else (ROOT / candidate).resolve()


def resource(module: str, group: str, name: str | Path, suffix: str) -> Path:
    """Resolve either an explicit path or a short scientific-resource name."""

    value = Path(name)
    candidates = [path(value)] if value.is_absolute() or len(value.parts) > 1 else []
    candidates.append(ROOT / "modules" / module / group / value)
    if not value.suffix:
        candidates.append((ROOT / "modules" / module / group / value).with_suffix(suffix))
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError(f"{module} {group} resource not found: {name}")


def read_json(filename: str | Path) -> Any:
    return json.loads(path(filename).read_text(encoding="utf-8"))


def read_jsonl(filename: str | Path) -> list[dict[str, Any]]:
    rows = []
    for number, line in enumerate(path(filename).read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{filename}:{number}: expected a JSON object")
            rows.append(value)
    return rows


def read_yaml(filename: str | Path) -> dict[str, Any]:
    value = yaml.safe_load(path(filename).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a YAML mapping: {filename}")
    return value


def write_json(filename: str | Path, value: Any) -> None:
    target = path(filename)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(filename: str | Path, rows: Iterable[dict[str, Any]], *, sort_keys: bool = True) -> None:
    target = path(filename)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=sort_keys) + "\n" for row in rows),
        encoding="utf-8",
    )


def sha256_file(filename: str | Path) -> str:
    digest = hashlib.sha256()
    with path(filename).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_csv(filename: str | Path) -> list[dict[str, str]]:
    with path(filename).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))
