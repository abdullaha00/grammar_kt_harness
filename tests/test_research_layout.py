from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def test_runner_names_every_baseline_research_declaration_directly() -> None:
    text = (ROOT / "scripts/run.py").read_text(encoding="utf-8")
    paths = [
        "data/fixtures/egp_pilot.jsonl",
        "modules/grammar/resource/egp/schema.yaml",
        "modules/grammar/resource/egp/normalisation/phase1.txt",
        "modules/grammar/resource/egp/normalisation/phase2.txt",
        "modules/grammar/resource/egp/normalisation/rulebook.md",
        "modules/grammar/canonical/schema.yaml",
        "modules/items/generation/prompt.txt",
        "modules/items/generation/rulebook.md",
        "modules/items/generation/design.yaml",
        "modules/items/generation/formats/controlled_production.yaml",
        "modules/items/generation/lexicon.jsonl",
        "modules/items/validation/prompt.txt",
        "modules/items/validation/criteria.yaml",
        "modules/simulation/folds/reference.yaml",
        "modules/simulation/world.yaml",
        "modules/kcs/policies/factorized.yaml",
        "modules/evaluation/kt/protocol.yaml",
        "modules/evaluation/protocol.yaml",
    ]
    assert all(path in text for path in paths)
    assert "load_experiment" not in text
    assert "config[" not in text
    assert "experiments/" not in text


def test_active_source_is_one_cohesive_file_per_stage() -> None:
    expected = {
        "__init__.py",
        "io.py",
        "normalise.py",
        "canonicalise.py",
        "generate.py",
        "validate_items.py",
        "fold.py",
        "simulate.py",
        "kc.py",
        "kt.py",
        "evaluate.py",
    }
    actual = {path.name for path in (ROOT / "src/grammar_kt").glob("*.py")}
    assert actual == expected
    legacy_directories = {
        "grammar",
        "measurement",
        "generation",
        "knowledge",
        "evaluation",
    }
    assert not any(
        path.suffix == ".py" and path.parent.name in legacy_directories
        for path in (ROOT / "src/grammar_kt").glob("*/*.py")
    )


def test_research_modules_match_the_five_pipeline_groups() -> None:
    groups = {path.name for path in (ROOT / "modules").iterdir() if path.is_dir()}
    assert groups == {"grammar", "items", "simulation", "kcs", "evaluation"}


def test_runner_reads_as_the_pipeline_without_config_resolution() -> None:
    text = (ROOT / "scripts/run.py").read_text(encoding="utf-8")
    calls = [
        "load_typed_resource(",
        "normalise(",
        "canonicalise(",
        "generate_items(",
        "validate_items(",
        "apply_fold(",
        "simulate(",
        "project_kcs(",
        "run_kt(",
        "evaluate(",
    ]
    positions = [text.index(call, text.index("def run_pipeline")) for call in calls]
    assert positions == sorted(positions)
    lowered = text.lower()
    assert "registry" not in lowered
    assert "deep_merge" not in lowered
    assert "fingerprint" not in lowered


def test_stage_files_transform_objects_without_reading_declaration_paths() -> None:
    for name in (
        "normalise.py",
        "canonicalise.py",
        "generate.py",
        "validate_items.py",
        "fold.py",
        "simulate.py",
        "kc.py",
        "kt.py",
        "evaluate.py",
    ):
        text = (ROOT / "src/grammar_kt" / name).read_text(encoding="utf-8")
        assert "load_experiment" not in text
        assert "read_yaml" not in text
        assert "read_text" not in text
        assert "read_jsonl" not in text
        assert "config: dict" not in text


def test_pipeline_walkthrough_notebook_executes_current_pipeline_without_live_calls() -> None:
    path = ROOT / "notebooks/pipeline_walkthrough.ipynb"
    assert path.is_file()
    notebook = json.loads(path.read_text(encoding="utf-8"))
    source_text = "\n".join(
        "".join(cell["source"])
        if isinstance(cell["source"], list)
        else cell["source"]
        for cell in notebook["cells"]
    )
    required_calls = [
        "read_text(",
        "read_yaml(",
        "read_jsonl(",
        "load_typed_resource(",
        "normalise(",
        "canonicalise(",
        "generate_items(",
        "validate_items(",
        "bank_summary(",
        "apply_fold(",
        "simulate(",
        "select_kcs(",
        "project_kcs(",
        "run_kt(",
        "evaluate(",
    ]
    assert all(call in source_text for call in required_calls)
    assert "LIVE_MODE = False" in source_text
    assert "load_experiment" not in source_text
    assert "config[" not in source_text
    code_cells = [cell for cell in notebook["cells"] if cell["cell_type"] == "code"]
    assert all(cell["execution_count"] is not None for cell in code_cells)
    assert not any(
        output.get("output_type") == "error"
        for cell in code_cells
        for output in cell["outputs"]
    )

    namespace = {"__name__": "__notebook_test__"}
    with patch(
        "grammar_kt.io.subprocess.run",
        side_effect=AssertionError("live model call"),
    ):
        for index, cell in enumerate(notebook["cells"]):
            if cell["cell_type"] == "code":
                source = (
                    "".join(cell["source"])
                    if isinstance(cell["source"], list)
                    else cell["source"]
                )
                exec(
                    compile(source, f"pipeline_walkthrough.ipynb:{index}", "exec"),
                    namespace,
                )

    assert namespace["LIVE_MODE"] is False
    assert namespace["resource_schema"]["resource_id"] == "egp_english_pilot"
    assert namespace["accepted_items"][0]["item_id"] == "item_001"
    assert namespace["WALKTHROUGH_SUMMARY"] == {
        "live_mode": False,
        "source_descriptors": 6,
        "mappings": 6,
        "canonical_cells": 6,
        "candidate_items": 6,
        "accepted_items": 6,
        "learners": 8,
        "events": 96,
        "baseline_kcs": 7,
        "kt_techniques": ["empirical", "bkt", "logistic"],
    }
