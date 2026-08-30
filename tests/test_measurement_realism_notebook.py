from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts/experiments/build_measurement_realism_notebook.py"
NOTEBOOK = ROOT / "notebooks/measurement_realism_results.ipynb"


def _builder_module():
    spec = importlib.util.spec_from_file_location("measurement_realism_notebook_builder", BUILDER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _source_text(notebook: dict[str, object]) -> str:
    return "\n".join(
        "".join(cell["source"]) if isinstance(cell["source"], list) else cell["source"]
        for cell in notebook["cells"]
    )


def test_builder_is_deterministic_and_uses_only_frozen_compact_inputs() -> None:
    module = _builder_module()
    first = module.build_notebook()
    second = module.build_notebook()
    assert first == second

    expected_names = {
        "strict_audit",
        "cross_audit",
        "kc_induction",
        "matched_bank",
        "controlled_worlds",
        "policy_recovery",
        "dialogue_continuum",
    }
    assert set(module.SOURCE_PATHS) == expected_names
    assert set(module.EXPECTED_SOURCE_SHA256) == expected_names
    assert all(path.endswith((".json", ".jsonl")) for path in module.SOURCE_PATHS.values())
    assert all((ROOT / path).is_file() for path in module.SOURCE_PATHS.values())

    cell_ids = [cell["id"] for cell in first["cells"]]
    assert len(cell_ids) == len(set(cell_ids))
    assert first["metadata"]["measurement_realism"] == {
        "controlled_scenario": True,
        "release_eligible": False,
        "human_validation": False,
        "source_kind": "compact_retained_json_only",
    }


def test_notebook_is_executed_and_makes_boundaries_prominent() -> None:
    assert NOTEBOOK.is_file()
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    code_cells = [cell for cell in notebook["cells"] if cell["cell_type"] == "code"]
    assert code_cells
    assert all(cell["execution_count"] is not None for cell in code_cells)
    assert not any(
        output.get("output_type") == "error"
        for cell in code_cells
        for output in cell["outputs"]
    )

    text = _source_text(notebook)
    required = [
        "CONTROLLED SCENARIO — NOT A DATASET RELEASE",
        "NO HUMAN VALIDATION",
        "content-free controlled instrument",
        "No new dataset is released",
        "oracle-aligned,\nsame-seen-item positive control",
        "No policy ranking",
        "ecological-realism/measurement-precision tradeoff",
    ]
    assert all(phrase in text for phrase in required)


def test_notebook_has_no_raw_stream_or_external_call_path() -> None:
    module = _builder_module()
    text = _source_text(module.build_notebook()).lower()
    forbidden = [
        "requests.",
        "urllib.",
        "subprocess",
        "openai.",
        "observable.jsonl",
        "oracle.jsonl",
        "test_predictions",
        ".jsonl.gz",
        "raw_output",
        "model_call",
        "to_csv(",
        "to_json(",
        "write_text(",
    ]
    # The prose explicitly says no model calls; only executable API spellings are forbidden.
    executable_text = "\n".join(
        "".join(cell["source"]) if isinstance(cell["source"], list) else cell["source"]
        for cell in module.build_notebook()["cells"]
        if cell["cell_type"] == "code"
    ).lower()
    assert not any(token in executable_text for token in forbidden)
    assert "data/grammar_kt_full_v1" not in text


def test_retained_artifacts_match_claim_and_numeric_anchors() -> None:
    module = _builder_module()
    artifacts = {
        name: json.loads((ROOT / path).read_text(encoding="utf-8"))
        for name, path in module.SOURCE_PATHS.items()
    }

    strict = artifacts["strict_audit"]
    bank = artifacts["matched_bank"]
    worlds = artifacts["controlled_worlds"]
    policy = artifacts["policy_recovery"]
    dialogue = artifacts["dialogue_continuum"]

    assert strict["categorical_results"]["primary_disposition"] == {
        "answer_space_problem": 10,
        "minor_ui_or_context_change": 15,
        "rewrite_or_withhold": 3,
        "technically_valid_but_artificial": 15,
        "usable_as_stored": 70,
    }
    assert bank["release_gate_failure"]["freeze_permitted"] is False
    assert bank["accepted_family_geometry"]["accepted_family_count"] == 5
    assert bank["accepted_family_geometry"]["accepted_seen_q_rank"] == 3
    assert worlds["release_eligible"] is False and worlds["content_free_instrument"] is True
    did = worlds["contrasts"]["primary_cross_world"]["format_confounding_difference_in_differences"]
    assert abs(did["across_seed_point_estimate"]["mean"] - (-0.03155148583847481)) < 1e-15
    assert "increases false format-split model B's predictive advantage" in did["corrected_sign_gloss"]
    assert policy["classification"] == "derived_exploratory_policy_robustness_not_preregistered_confirmatory_evidence"
    assert dialogue["scale"]["judgments"] == 100
    assert dialogue["evidence_boundary"]["scalar_realism_score_computed"] is False
