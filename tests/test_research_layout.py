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
        "baseline_simulation.py",
        "sensitivity_simulation.py",
        "dataset_freeze.py",
        "full_items.py",
        "grammar_regimes.py",
        "measurement_gate.py",
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


def test_research_modules_match_the_pipeline_and_measurement_groups() -> None:
    groups = {path.name for path in (ROOT / "modules").iterdir() if path.is_dir()}
    assert groups == {
        "grammar",
        "items",
        "simulation",
        "kcs",
        "evaluation",
        "measurement_realism",
    }


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

    required_full_v1_artifacts = [
        "manifest.json",
        "provenance/normalisation/full_audit.json",
        "grammar/cells.jsonl",
        "grammar/regime_assignments.jsonl",
        "kcs.jsonl",
        "items/items.jsonl",
        "provenance/measurement/audit.json",
        "q_matrix.csv",
        "interactions.jsonl.gz",
        "reports/full_v1_artifacts/rq2_misspecification_v1/results.json",
        "experiments/full_v1/rq3_kc_discovery_v1/final_evaluation.json",
        "experiments/full_v1/rq4_generalisation_v1/results.json",
        "reports/full_v1_artifacts/mastery_recovery_v1/results.json",
        "experiments/full_v1/simulator_robustness_v1/results.json",
        "experiments/full_v1/collection_design_v1/results.json",
    ]
    assert all(artifact in source_text for artifact in required_full_v1_artifacts)
    assert "grammar_kt_full_v1" in source_text
    assert "GrammarCell != generator K* != discovered K_hat" in source_text
    assert "pd.DataFrame" in source_text
    assert "show_table(" in source_text
    assert "FINAL_DATASET_SUMMARY" in source_text
    assert "learner_truth.jsonl" not in source_text
    assert 'DATASET / "oracle' not in source_text
    assert "oracle/q_matrix_sparse.jsonl" not in source_text
    assert "oracle_debug" not in source_text
    assert "call_model" not in source_text
    assert "write_text(" not in source_text

    code_cells = [cell for cell in notebook["cells"] if cell["cell_type"] == "code"]
    assert all(cell["execution_count"] is not None for cell in code_cells)
    assert sum(bool(cell["outputs"]) for cell in code_cells) >= 18
    assert not any(
        output.get("output_type") == "error"
        for cell in code_cells
        for output in cell["outputs"]
    )
    output_text = json.dumps(
        [output for cell in code_cells for output in cell["outputs"]],
        sort_keys=True,
    )
    assert "FROZEN_BASELINE_COMPLETE" in output_text
    assert "283000" in output_text
    assert "true_kstar" in output_text
    assert "hash_distractor_negative_control" in output_text
    assert "all_ab_no_anchors" in output_text


def test_final_dataset_notebook_is_full_v1_public_viewer() -> None:
    path = ROOT / "notebooks/final_dataset.ipynb"
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
    assert "GRAMMAR_KT_DATA_FOLDER" in source_text
    assert "grammar_kt_full_v1" in source_text
    assert "GrammarCell != generator K* != discovered K_hat" in source_text
    for artifact in (
        "manifest.json",
        "grammar/cells.jsonl",
        "grammar/regime_assignments.jsonl",
        "kcs.jsonl",
        "items/items.jsonl",
        "q_matrix.csv",
        "interactions.jsonl.gz",
        "provenance/measurement/audit.json",
    ):
        assert artifact in source_text
    for stale_or_private_reference in (
        "grammar_kt_medium_v1",
        "kc/policies/automated.yaml",
        "oracle/learner_truth.jsonl",
        "protocol_phase",
        "dataset_split",
        "item_difficulty",
    ):
        assert stale_or_private_reference not in source_text
    assert "write_text(" not in source_text

    code_cells = [cell for cell in notebook["cells"] if cell["cell_type"] == "code"]
    assert len(code_cells) == 9
    assert all(cell["execution_count"] is not None for cell in code_cells)
    assert sum(bool(cell["outputs"]) for cell in code_cells) == 7
    assert not any(
        output.get("output_type") == "error"
        for cell in code_cells
        for output in cell["outputs"]
    )
    output_text = json.dumps(
        [output for cell in code_cells for output in cell["outputs"]],
        sort_keys=True,
    )
    for expected in (
        "FROZEN_BASELINE_COMPLETE",
        "Prompt shown to learner",
        "Binary outcome only; no free-text learner answer is stored",
        "283000",
        "269",
    ):
        assert expected in output_text


def test_acl_paper_uses_preprint_shell_with_known_truth_and_measurement_evidence() -> None:
    paper = (ROOT / "ACL/paper.tex").read_text(encoding="utf-8")
    section_text = " ".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "ACL/sections").glob("*.tex"))
    )
    normalized = " ".join(section_text.split())

    for required in (
        r"\usepackage[preprint]{acl}",
        "Abdullah Akram",
        "University of Cambridge",
        r"aa2527@cam.ac.uk",
        "Known Truth, Ambiguous Measurement",
    ):
        assert required in paper

    assert r"\usepackage[review]{acl}" not in paper
    assert "Anonymous ACL submission" not in paper
    assert paper.index(r"\input{sections/limitations}") < paper.index(
        r"\input{sections/conclusion}"
    )

    for required in (
        "neither renders a prompt nor collects or scores free text",
        "controlled forward-generation and inverse-recovery benchmark",
        "Known truth is necessary, not sufficient",
        "Content-free controlled scenario",
        "no new dataset release",
        "matched-format successor freezes only 5/38 families",
        "Shared answer-space failure",
        "Modal answer-space failure",
        r"\section{Artifact Map}",
    ):
        assert required in normalized

    for stale in (
        "139 descriptors",
        "Current Evidence Status and Results Contract",
        "quantitative research comparisons are deliberately reserved",
    ):
        assert stale not in normalized


def test_final_dataset_visualization_is_public_full_v1_only() -> None:
    path = ROOT / "reports/final_dataset_visualization.html"
    html = path.read_text(encoding="utf-8")

    for required in (
        "Grammar-KT full-v1",
        "learner_000001",
        "sequence 1–10 of 283",
        "Binary + Q* view",
        "Stored prompt view",
        "item_id → Q* required KCs · mastery over those KCs → P(correct) → sampled y",
        "Q*=1",
        "Q*=0",
        "Q star row 000100000000000000",
        "Q star row 000000000000001001",
        "candidate_gc_4601bed02c004e37_01",
        "Mia had a map, so she found the house. Without the map, [____]. (find)",
        "candidate_gc_e7fef77abc10b5ba_01",
        "candidate_gc_172c3f1039296750_01",
        "she would not have found the house",
        "Would she open the window?",
        "Accepted response text · not used by simulator",
        "text is neither rendered nor scored by this simulator",
        "K*/Q* are controlled synthetic truth, not claims about human cognition",
        "Full dataset: 1,000 learners · 113 items · 18 generator KCs",
        "283,000 observable interactions",
    ):
        assert required in html

    assert html.count('data-event="') == 10
    assert html.count('data-entry="') == 10
    assert html.count('class="view-tab"') == 2
    assert html.count("<script>") == 1
    assert 'querySelectorAll("[data-view]")' in html

    for forbidden in (
        "learner_truth",
        "mastery_before",
        "mastery_after",
        "response_probability",
        "response_draw",
        "RQ2",
        "RQ3",
        "RQ4",
        "fetch(",
        "<script src=",
    ):
        assert forbidden not in html

    assert '<meta name="viewport"' in html
    assert "@media (max-width: 48rem)" in html
    assert path.stat().st_size < 30_000


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
