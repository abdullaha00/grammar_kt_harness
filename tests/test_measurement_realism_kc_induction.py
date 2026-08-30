from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/experiments/measurement_realism_kc_induction.py"
SPEC = importlib.util.spec_from_file_location("measurement_realism_kc_induction", SCRIPT)
assert SPEC and SPEC.loader
kc_induction = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(kc_induction)


def _hypothesis(index: int, dimension: str, value: str) -> dict:
    all_of = {
        "tense": [],
        "aspect": [],
        "voice": [],
        "polarity": [],
        "clause": [],
        "modal": [],
    }
    all_of[dimension] = [value]
    return {
        "proposal_id": f"p{index:02d}",
        "name": f"hypothesis {index}",
        "hypothesis_type": "feature_value",
        "pedagogical_interpretation": "A bounded practice hypothesis.",
        "reuse_and_parsimony_rationale": "Reused wherever the predicate activates.",
        "activation": {"any_of": [{"all_of": all_of}]},
        "limitation_or_needed_evidence": "Requires independent expert and learner evidence.",
    }


def _twelve_hypotheses() -> list[dict]:
    pairs = [
        ("tense", "present"),
        ("tense", "past"),
        ("aspect", "progressive"),
        ("aspect", "perfect"),
        ("aspect", "perfect_progressive"),
        ("voice", "passive"),
        ("polarity", "negative"),
        ("clause", "polar_question"),
        ("clause", "non_subject_wh_question"),
        ("clause", "imperative"),
        ("modal", "can"),
        ("modal", "will"),
    ]
    return [_hypothesis(index, *pair) for index, pair in enumerate(pairs, 1)]


def test_predicate_semantics_are_executable() -> None:
    features = {
        "tense": "present",
        "aspect": "none",
        "voice": "active",
        "polarity": "negative",
        "clause": "declarative",
        "modal": "none",
    }
    empty = {name: [] for name in ("tense", "aspect", "voice", "polarity", "clause", "modal")}
    activation = {"any_of": [
        {"all_of": {**empty, "tense": ["past"]}},
        {"all_of": {**empty, "tense": ["present"], "polarity": ["negative"]}},
    ]}
    assert kc_induction._activates(features, activation)
    assert not kc_induction._activates(
        {**features, "polarity": "positive"}, activation
    )


def test_plan_freezes_only_public_cell_input(tmp_path: Path) -> None:
    output = tmp_path / "study"
    plan = kc_induction.plan(
        kc_induction.DEFAULT_DATASET,
        kc_induction.DEFAULT_CONFIG,
        kc_induction.DEFAULT_PROMPT,
        kc_induction.DEFAULT_SCHEMA,
        output,
    )
    frozen = json.loads((output / "proposal_input.json").read_text(encoding="utf-8"))
    assert plan["scale"] == {"cells": 75, "dimensions": 6}
    assert set(frozen) == {"canonical_schema", "cells"}
    assert len(frozen["cells"]) == 75
    assert all(set(row) == {"cell_id", "features", "source_support_count"} for row in frozen["cells"])
    rendered = kc_induction._render_prompt(
        kc_induction.DEFAULT_PROMPT.read_text(encoding="utf-8"),
        replicate_id="independent_01",
        config=kc_induction.read_yaml(kc_induction.DEFAULT_CONFIG),
        canonical_schema=frozen["canonical_schema"],
        cells=frozen["cells"],
        output_schema=json.loads(kc_induction.DEFAULT_SCHEMA.read_text(encoding="utf-8")),
    )
    assert "gkc_aspect_perfect" not in rendered
    assert "learner_id" not in rendered


def test_local_validation_rejects_unknown_schema_value(tmp_path: Path) -> None:
    config = kc_induction.read_yaml(kc_induction.DEFAULT_CONFIG)
    schema = json.loads(kc_induction.DEFAULT_SCHEMA.read_text(encoding="utf-8"))
    canonical_schema, _cells = kc_induction._load_public_inputs(kc_induction.DEFAULT_DATASET)
    result = {
        "replicate_id": "independent_01",
        "hypotheses": _twelve_hypotheses(),
        "ontology_level_limitations": ["The schema omits lexical morphology."],
    }
    kc_induction._validate_predicates(
        result,
        replicate_id="independent_01",
        config=config,
        schema=schema,
        canonical_schema=canonical_schema,
    )
    result["hypotheses"][0]["activation"]["any_of"][0]["all_of"]["tense"] = ["future"]
    with pytest.raises(ValueError, match="unknown value"):
        kc_induction._validate_predicates(
            result,
            replicate_id="independent_01",
            config=config,
            schema=schema,
            canonical_schema=canonical_schema,
        )


def test_analysis_canonicalises_by_activation_not_wording(tmp_path: Path) -> None:
    output = tmp_path / "study"
    plan = kc_induction.plan(
        kc_induction.DEFAULT_DATASET,
        kc_induction.DEFAULT_CONFIG,
        kc_induction.DEFAULT_PROMPT,
        kc_induction.DEFAULT_SCHEMA,
        output,
    )
    rows = []
    for replicate_id in plan["replicate_ids"]:
        hypotheses = _twelve_hypotheses()
        for hypothesis in hypotheses:
            hypothesis["name"] = f"{replicate_id} {hypothesis['name']}"
        rows.append(
            {
                "replicate_id": replicate_id,
                "hypotheses": hypotheses,
                "ontology_level_limitations": ["Cells do not prove independent mastery."],
            }
        )
    payload = "".join(kc_induction.canonical_json(row) + "\n" for row in rows)
    (output / "raw_proposals.jsonl").write_text(payload, encoding="utf-8")
    (output / "run_manifest.json").write_text(
        json.dumps(
            {
                "raw_proposals_sha256": hashlib.sha256(payload.encode()).hexdigest()
            }
        )
        + "\n",
        encoding="utf-8",
    )
    result = kc_induction.analyse(kc_induction.DEFAULT_DATASET, output)
    assert result["activation_hypotheses_shared_by_all_replicates"] == 12
    assert result["activation_hypotheses_in_union"] == 12
    assert len(result["pairwise_activation_set_agreement"]) == 3
    assert all(row["jaccard"] == 1.0 for row in result["pairwise_activation_set_agreement"])
