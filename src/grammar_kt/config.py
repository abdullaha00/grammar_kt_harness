"""Load named experiment variants from ``experiments/``."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .io import ROOT, read_yaml


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


def load_experiment(name: str = "base") -> tuple[dict[str, Any], str | None]:
    """Resolve ``experiments/<name>.yaml`` and return settings and its parent name."""

    def resolve(current: str, seen: tuple[str, ...]) -> tuple[dict[str, Any], str | None]:
        if not current or "/" in current or "\\" in current or current.endswith((".yaml", ".yml")):
            raise ValueError("experiment must be a short name without a file extension")
        if current in seen:
            raise ValueError("cyclic experiment inheritance: " + " -> ".join((*seen, current)))

        filename = ROOT / "experiments" / f"{current}.yaml"
        if not filename.is_file():
            raise FileNotFoundError(f"experiment not found: {filename}")
        raw = read_yaml(filename)
        parent = raw.get("extends")
        if parent is None:
            settings = deepcopy(raw)
        else:
            if not isinstance(parent, str):
                raise ValueError(f"{filename}: extends must be an experiment name")
            parent_settings, _ = resolve(parent, (*seen, current))
            settings = deep_merge(parent_settings, raw)
        settings["experiment"] = raw.get("experiment", current)
        return settings, parent

    settings, parent = resolve(name, ())
    fold = settings.get("fold", {})
    if fold:
        if not isinstance(fold, dict) or not isinstance(fold.get("manifest"), str):
            raise ValueError("experiment fold must declare one manifest path")
        for stage in ("simulation", "kc_selection", "kc", "kt"):
            settings.setdefault(stage, {})["fold_manifest"] = fold["manifest"]
    return settings, parent
