"""Small, explicit experiment inheritance and scientific-config loading."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .io import ROOT, repo_path


@dataclass(frozen=True)
class ExperimentResolution:
    """A resolved manifest plus the direct parent needed for a controlled diff."""

    path: Path
    raw: dict[str, Any]
    resolved: dict[str, Any]
    source_chain: tuple[Path, ...]
    parent_path: Path | None
    parent_resolved: dict[str, Any] | None


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


def _mapping(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"configuration must be a mapping: {path}")
    return value


def resolve_experiment_path(value: str | Path, *, relative_to: Path | None = None) -> Path:
    """Resolve a path or a short experiment name such as ``current``."""

    path = Path(value).expanduser()
    candidates: list[Path] = []
    if path.is_absolute():
        candidates.append(path)
    else:
        if relative_to is not None:
            candidates.append(relative_to / path)
        candidates.extend((ROOT / path, ROOT / "experiments" / path))
    expanded: list[Path] = []
    for candidate in candidates:
        expanded.append(candidate)
        if not candidate.suffix:
            expanded.extend((candidate.with_suffix(".yaml"), candidate.with_suffix(".yml")))
    for candidate in expanded:
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError(f"experiment not found: {value}")


def _load_chain(path: Path, seen: tuple[Path, ...]) -> tuple[dict[str, Any], tuple[Path, ...], Path | None, dict[str, Any] | None]:
    path = path.resolve()
    if path in seen:
        chain = " -> ".join(str(item) for item in (*seen, path))
        raise ValueError(f"cyclic experiment inheritance: {chain}")
    raw = _mapping(path)
    parent_value = raw.get("extends")
    if parent_value is None:
        return raw, (path,), None, None
    parent_path = resolve_experiment_path(parent_value, relative_to=path.parent)
    parent, chain, _, _ = _load_chain(parent_path, (*seen, path))
    return deep_merge(parent, raw), (*chain, path), parent_path, parent


def _included_mapping(value: str | Path) -> dict[str, Any]:
    path = repo_path(value)
    if not path.is_file():
        raise FileNotFoundError(f"included scientific configuration not found: {path}")
    return _mapping(path)


def expand_scientific_config(config: dict[str, Any]) -> dict[str, Any]:
    """Inline small model-config files while retaining their paths for hashing."""

    result = deepcopy(config)
    normalization = result.get("normalization")
    if isinstance(normalization, dict) and normalization.get("model_config"):
        result["normalization"] = deep_merge(
            _included_mapping(normalization["model_config"]), normalization
        )
    items = result.get("items")
    if isinstance(items, dict) and isinstance(items.get("validation"), dict):
        validation = items["validation"]
        if validation.get("model_config"):
            items["validation"] = deep_merge(
                _included_mapping(validation["model_config"]), validation
            )
    return result


def resolve_experiment(value: str | Path) -> ExperimentResolution:
    path = resolve_experiment_path(value)
    raw = _mapping(path)
    merged, chain, parent_path, parent = _load_chain(path, ())
    return ExperimentResolution(
        path=path,
        raw=raw,
        resolved=expand_scientific_config(merged),
        source_chain=chain,
        parent_path=parent_path,
        parent_resolved=expand_scientific_config(parent) if parent is not None else None,
    )


def load_experiment(path: Path) -> dict[str, Any]:
    """Compatibility wrapper used by callers that only need the resolved mapping."""

    return resolve_experiment(path).resolved


def diff_values(base: Any, target: Any, prefix: str = "") -> list[dict[str, Any]]:
    """Return leaf-level changes in stable dotted-path order."""

    if isinstance(base, dict) and isinstance(target, dict):
        changes: list[dict[str, Any]] = []
        for key in sorted(set(base) | set(target)):
            path = f"{prefix}.{key}" if prefix else key
            if key not in base:
                changes.append({"path": path, "from": "<missing>", "to": target[key]})
            elif key not in target:
                changes.append({"path": path, "from": base[key], "to": "<missing>"})
            else:
                changes.extend(diff_values(base[key], target[key], path))
        return changes
    if base != target:
        return [{"path": prefix, "from": base, "to": target}]
    return []


def scientific_paths(value: Any) -> list[Path]:
    """Find declared paths that exist; values such as model names are ignored."""

    found: dict[Path, None] = {}

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            for child in node.values():
                visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)
        elif isinstance(node, str):
            candidate = repo_path(node)
            if candidate.exists():
                found[candidate.resolve()] = None

    visit(value)
    return sorted(found)
