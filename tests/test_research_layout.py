from __future__ import annotations

import ast
import json
from pathlib import Path

from grammar_kt.io import ROOT, load_experiment, repo_path


def test_base_experiment_references_complete_readable_method() -> None:
    config = load_experiment("base")
    assert list(config) == [
        "experiment", "resource", "normalisation", "canonical", "generation",
        "validation", "fold", "simulation", "kc", "kt", "evaluation",
    ]
    paths = []
    for section in config.values():
        if isinstance(section, dict):
            paths.extend(value for value in section.values() if isinstance(value, str) and value.startswith(("modules/", "data/")))
    assert all(repo_path(path).is_file() for path in paths)


def test_active_source_is_one_cohesive_file_per_stage() -> None:
    expected = {
        "__init__.py", "io.py", "normalise.py", "canonicalise.py", "generate.py",
        "validate_items.py", "fold.py", "simulate.py", "kc.py", "kt.py", "evaluate.py",
    }
    actual = {path.name for path in (ROOT / "src/grammar_kt").glob("*.py")}
    assert actual == expected
    legacy_directories = {"grammar", "measurement", "generation", "knowledge", "evaluation"}
    assert not any(
        path.suffix == ".py" and path.parent.name in legacy_directories
        for path in (ROOT / "src/grammar_kt").glob("*/*.py")
    )


def test_runner_reads_as_the_pipeline_without_registry_or_hashes() -> None:
    text = (ROOT / "scripts/run.py").read_text(encoding="utf-8")
    calls = [
        "load_typed_resource(", "normalise(", "canonicalise(", "generate_items(",
        "validate_items(", "apply_fold(", "simulate(", "build_or_select_kcs(",
        "project_kcs(", "run_kt(", "evaluate(",
    ]
    positions = [text.index(call, text.index("def run_pipeline")) for call in calls]
    assert positions == sorted(positions)
    lowered = text.lower()
    assert "registry" not in lowered and "sha256" not in lowered and "fingerprint" not in lowered


def test_walkthrough_notebook_executes_current_pipeline(tmp_path) -> None:
    notebook = json.loads((ROOT / "notebooks/walkthrough.ipynb").read_text(encoding="utf-8"))
    namespace = {"__name__": "__notebook_test__"}
    for index, cell in enumerate(notebook["cells"]):
        if cell["cell_type"] == "code":
            source = "".join(cell["source"]) if isinstance(cell["source"], list) else cell["source"]
            exec(compile(source, f"walkthrough.ipynb:{index}", "exec"), namespace)
    assert namespace["items"][0]["item_id"] == "item_001"
    assert namespace["events"]
