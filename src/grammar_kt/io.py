"""Small file and stable-ID helpers shared by the harness."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml


ROOT = Path(__file__).resolve().parents[2]


def repo_path(value: str | Path) -> Path:
    """Return an absolute path, resolving relative paths from the repository root."""

    candidate = Path(value).expanduser()
    return candidate.resolve() if candidate.is_absolute() else (ROOT / candidate).resolve()


def stable_id(prefix: str, *parts: object) -> str:
    """Create a short content-derived semantic ID from explicit identity parts."""

    encoded = "|".join(
        part if isinstance(part, str) else json.dumps(part, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for part in parts
    )
    digest = hashlib.sha256(encoded.encode()).hexdigest()[:16].upper()
    return f"{prefix}_{digest}"


def read_json(filename: str | Path) -> Any:
    return json.loads(repo_path(filename).read_text(encoding="utf-8"))


def read_jsonl(filename: str | Path) -> list[dict[str, Any]]:
    rows = []
    for number, line in enumerate(repo_path(filename).read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{filename}:{number}: expected a JSON object")
            rows.append(value)
    return rows


def read_yaml(filename: str | Path) -> dict[str, Any]:
    value = yaml.safe_load(repo_path(filename).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a YAML mapping: {filename}")
    return value


def write_json(filename: str | Path, value: Any) -> None:
    target = repo_path(filename)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(filename: str | Path, rows: Iterable[dict[str, Any]], *, sort_keys: bool = True) -> None:
    target = repo_path(filename)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=sort_keys) + "\n" for row in rows),
        encoding="utf-8",
    )


def sha256_file(filename: str | Path) -> str:
    digest = hashlib.sha256()
    with repo_path(filename).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
