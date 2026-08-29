from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import yaml


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
        "modules/grammar/canonical/english_operations.yaml",
        "modules/items/generation/prompt.txt",
        "modules/items/generation/rulebook.md",
        "modules/items/generation/design.yaml",
        "modules/items/generation/formats/controlled_production.yaml",
        "modules/items/validation/prompt.txt",
        "modules/items/validation/criteria.yaml",
        "modules/simulation/folds/semantic.yaml",
        "modules/simulation/protocol.yaml",
        "modules/simulation/worlds/phase4_factorized.yaml",
        "modules/kcs/candidate_design.yaml",
        "modules/kcs/selection.yaml",
        "modules/evaluation/kt/protocol.yaml",
        "modules/evaluation/protocol.yaml",
        "modules/model_backends.yaml",
    ]
    assert all(path in text for path in paths)
    assert "load_experiment" not in text
    assert "config[" not in text
    assert "experiments/" not in text
    assert "lexicon.jsonl" not in text


def test_model_backend_declaration_is_small_and_stage_complete() -> None:
    settings = yaml.safe_load(
        (ROOT / "modules/model_backends.yaml").read_text(encoding="utf-8")
    )
    assert set(settings) == {"normalisation", "generation", "validation"}
    for backend in settings.values():
        assert set(backend) == {"model", "reasoning_effort"}
        assert isinstance(backend["model"], str) and backend["model"]
        assert backend["reasoning_effort"] in {"medium", "high", "xhigh"}


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
        "kc_candidates.py",
        "kc_selection.py",
        "kt.py",
        "evaluate.py",
        "full_normalisation.py",
        "generator_kcs.py",
        "measurement.py",
        "model_evidence.py",
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


def test_fixture_only_declarations_are_not_presented_as_active_modules() -> None:
    assert not (ROOT / "modules/simulation/folds/reference.yaml").exists()
    assert not (ROOT / "modules/simulation/world.yaml").exists()
    assert not (ROOT / "modules/kcs/policies").exists()
    operations = (ROOT / "modules/grammar/canonical/english_operations.yaml").read_text(
        encoding="utf-8"
    )
    assert "generator_tag" not in operations
    assert (
        ROOT / "data/fixtures/historical/english_generator_tag_rules.yaml"
    ).is_file()


def test_runner_reads_as_the_pipeline_without_config_resolution() -> None:
    text = (ROOT / "scripts/run.py").read_text(encoding="utf-8")
    calls = [
        "load_typed_resource(",
        "normalise(",
        "canonicalise(",
        "generate_items(",
        "validate_items(",
        "select_item_bank(",
        "build_semantic_fold(",
        "make_kc_candidates(",
        "materialize_latent_world(",
        "simulate_frozen_probes(",
        "select_kcs(",
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
        "kc_candidates.py",
        "kc_selection.py",
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
        "load_typed_resource(",
        "normalise(",
        "canonicalise(",
        "generate_items(",
        "validate_items(",
        "select_item_bank(",
        "bank_summary(",
        "build_semantic_fold(",
        "simulate_frozen_probes(",
        "make_kc_candidates(",
        "select_kcs(",
        "project_kcs(",
        "run_kt(",
        "evaluate(",
    ]
    assert all(call in source_text for call in required_calls)
    assert "LIVE_MODE = False" in source_text
    assert "load_experiment" not in source_text
    assert "config[" not in source_text
    assert "generation/lexicon.jsonl" not in source_text
    assert "data/fixtures/semantic_fold.yaml" in source_text
    assert "modules/simulation/protocol.yaml" in source_text
    assert "modules/model_backends.yaml" in source_text
    assert "backend_settings['normalisation']['reasoning_effort']" in source_text
    assert "backend_settings['generation']['reasoning_effort']" in source_text
    assert "backend_settings['validation']['reasoning_effort']" in source_text
    assert "normalisation_model = generation_model" not in source_text
    assert "reasoning_effort = 'medium'" not in source_text
    assert "INPUT GrammarCell" in source_text
    assert "RENDERED LLM PROMPT" in source_text
    assert "Vocabulary is model-selected" in source_text
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
    assert namespace["backend_settings"] == {
        stage: {"model": "fixture", "reasoning_effort": "deterministic"}
        for stage in ("normalisation", "generation", "validation")
    }
    assert namespace["resource_schema"]["resource_id"] == "egp_english_pilot"
    assert namespace["accepted_items"][0]["item_id"] == "candidate_cell_001_01"
    assert namespace["WALKTHROUGH_SUMMARY"] == {
        "live_mode": False,
        "source_descriptors": 6,
        "mappings": 6,
        "canonical_cells": 6,
        "candidate_items": 6,
        "accepted_items": 6,
        "development_cells": 4,
        "compositional_holdout_cells": 1,
        "novel_feature_holdout_cells": 1,
        "learners": 8,
        "acquisition_events": 160,
        "probe_events": 48,
        "events": 208,
        "structural_candidates": 27,
        "selection_eligible_candidates": 6,
        "selected_kcs": 4,
        "kt_techniques": ["empirical", "bkt", "logistic"],
    }


def test_final_dataset_results_notebook_is_parameterized_and_executed() -> None:
    path = ROOT / "notebooks/final_dataset_results.ipynb"
    assert path.is_file()
    notebook = json.loads(path.read_text(encoding="utf-8"))
    source_text = "\n".join(
        "".join(cell["source"])
        if isinstance(cell["source"], list)
        else cell["source"]
        for cell in notebook["cells"]
    )

    parameter_cells = [
        cell
        for cell in notebook["cells"]
        if "parameters" in cell.get("metadata", {}).get("tags", [])
    ]
    assert len(parameter_cells) == 1
    assert "DATA_FOLDER" in "".join(parameter_cells[0]["source"])
    assert "GRAMMAR_KT_DATA_FOLDER" in source_text

    required_stage_artifacts = [
        "source/descriptors.jsonl",
        "normalisation/mappings.jsonl",
        "canonical/cells.jsonl",
        "items/generation_attempts.jsonl",
        "items/curated_validation.jsonl",
        "items/selected_bank.jsonl",
        "fold/assignments.jsonl",
        "kc/candidate_inventory.json",
        "simulation/events.jsonl.gz",
        "kc/selection_trace.json",
        "kc/q_matrices/automated.csv",
        "kt/automated/predictions.jsonl.gz",
        "evaluation/automated/results.json",
        "evaluation/paired_logistic.json",
        "kc/selection_stability.json",
    ]
    assert all(artifact in source_text for artifact in required_stage_artifacts)
    assert "pd.DataFrame" in source_text
    assert "show_table(" in source_text
    assert "FINAL_DATASET_SUMMARY" in source_text
    assert "reports/" not in source_text
    assert "oracle_debug" not in source_text
    assert "call_model" not in source_text

    code_cells = [cell for cell in notebook["cells"] if cell["cell_type"] == "code"]
    assert all(cell["execution_count"] is not None for cell in code_cells)
    assert sum(bool(cell["outputs"]) for cell in code_cells) >= 15
    assert not any(
        output.get("output_type") == "error"
        for cell in code_cells
        for output in cell["outputs"]
    )


def test_baseline_generation_has_no_controlled_lexicon_dependency() -> None:
    active_paths = [
        ROOT / "scripts/run.py",
        ROOT / "scripts/run_one.py",
        ROOT / "scripts/run_experiments.py",
        ROOT / "src/grammar_kt/generate.py",
        ROOT / "notebooks/pipeline_walkthrough.ipynb",
    ]
    for path in active_paths:
        text = path.read_text(encoding="utf-8")
        assert "generation/lexicon.jsonl" not in text

    # Resource provenance such as CEFR is allowed in the upstream EGP adapter,
    # but it must not leak into item generation or its experiment runners.
    active_source = "\n".join(
        path.read_text(encoding="utf-8") for path in active_paths
    )
    for legacy_name in ("passive_compatible", "lexeme_id", '"cefr"'):
        assert legacy_name not in active_source

    assert not (ROOT / "modules/items/generation/lexicon.jsonl").exists()
    assert (
        ROOT
        / "modules/items/generation/ablations/controlled_lexicon.jsonl"
    ).is_file()
