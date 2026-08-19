"""Readable experiment inheritance."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .io import ROOT, read_yaml


@dataclass(frozen=True)
class Experiment:
    name: str
    settings: dict[str, Any]
    parent: str | None


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if key == "extends":
            continue
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def experiment_path(value: str | Path) -> Path:
    candidate = Path(value).expanduser()
    candidates = [candidate] if candidate.is_absolute() else [ROOT / candidate, ROOT / "experiments" / candidate]
    for item in tuple(candidates):
        if not item.suffix:
            candidates.extend((item.with_suffix(".yaml"), item.with_suffix(".yml")))
    for item in candidates:
        if item.is_file():
            return item.resolve()
    raise FileNotFoundError(f"experiment not found: {value}")


def _resolve(filename: Path, seen: tuple[Path, ...]) -> tuple[dict[str, Any], str | None]:
    if filename in seen:
        raise ValueError("cyclic experiment inheritance: " + " -> ".join(map(str, (*seen, filename))))
    raw = read_yaml(filename)
    parent_value = raw.get("extends")
    if parent_value is None:
        return deepcopy(raw), None
    parent_path = experiment_path(filename.parent / str(parent_value))
    parent, _ = _resolve(parent_path, (*seen, filename))
    return deep_merge(parent, raw), parent_path.stem


def resolve_experiment(value: str | Path = "base") -> Experiment:
    filename = experiment_path(value)
    raw = read_yaml(filename)
    settings, parent = _resolve(filename, ())
    settings["experiment"] = raw.get("experiment", filename.stem)
    return Experiment(filename.stem, settings, parent)


def changed_values(base: Any, target: Any, prefix: str = "") -> list[dict[str, Any]]:
    if isinstance(base, dict) and isinstance(target, dict):
        changes = []
        for key in sorted(set(base) | set(target)):
            dotted = f"{prefix}.{key}" if prefix else key
            if key not in base:
                changes.append({"path": dotted, "from": None, "to": target[key]})
            elif key not in target:
                changes.append({"path": dotted, "from": base[key], "to": None})
            else:
                changes.extend(changed_values(base[key], target[key], dotted))
        return changes
    return [] if base == target else [{"path": prefix, "from": base, "to": target}]
