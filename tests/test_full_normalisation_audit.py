from __future__ import annotations

import json

import pytest

from grammar_kt.full_normalisation import (
    source_cell_relations,
    stable_canonicalise,
)
from grammar_kt.io import read_yaml, write_jsonl
from scripts.audit_full_normalisation import audit_full_normalisation

from .helpers import ROOT


SCHEMA_PATH = ROOT / "modules/grammar/canonical/schema.yaml"


def _exact_cell(tense: str = "present") -> dict[str, str]:
    return {
        "tense": tense,
        "aspect": "none",
        "voice": "active",
        "polarity": "positive",
        "clause": "declarative",
        "modal": "none",
    }


def _mapping(
    source_id: str,
    result: str,
    cells: list[dict[str, object]],
    eligible: list[str] | None = None,
    note: str = "restricted explanatory prose",
) -> dict[str, object]:
    return {
        "source_id": source_id,
        "result": result,
        "cells": cells,
        "phase2_eligible": eligible or [],
        "note": note,
    }


def _fixture_files(tmp_path):
    source = [
        {
            "source_id": "s1",
            "cefr": "A1",
            "supercategory": "VERBS",
            "subcategory": "present",
            "guideword": "private guideword one",
            "can_do": "private descriptor one",
            "examples": ["Private example one."],
        },
        {
            "source_id": "s2",
            "cefr": "A2",
            "supercategory": "VERBS",
            "subcategory": "tense",
            "guideword": "private guideword two",
            "can_do": "private descriptor two",
            "examples": ["Private example two."],
        },
        {
            "source_id": "s3",
            "cefr": "B1",
            "supercategory": "CLAUSES",
            "subcategory": "other",
            "guideword": "private guideword three",
            "can_do": "private descriptor three",
            "examples": [],
        },
    ]
    phase1 = [
        _mapping("s1", "complete", [_exact_cell()]),
        _mapping(
            "s2",
            "partial",
            [{**_exact_cell(), "tense": ["present", "past"]}],
            ["tense"],
        ),
        _mapping("s3", "unresolved", []),
    ]
    phase2 = [
        _mapping(
            "s2",
            "complete",
            [_exact_cell(), _exact_cell("past")],
            ["tense"],
        )
    ]
    final = [phase1[0], phase2[0], phase1[2]]
    schema = read_yaml(SCHEMA_PATH)
    cells = stable_canonicalise(final, schema)
    relations = source_cell_relations(final, cells, schema)
    attempts = [
        {
            "source_id": "s1",
            "status": "success",
            "attempt_count": 1,
            "runtime_seconds": 1.0,
            "errors": [],
        },
        {
            "source_id": "s2",
            "status": "success",
            "attempt_count": 2,
            "runtime_seconds": 2.0,
            "errors": [
                {
                    "error_type": "JSONDecodeError",
                    "error": "private failure message must never be published",
                }
            ],
        },
        {
            "source_id": "s3",
            "status": "success",
            "attempt_count": 1,
            "runtime_seconds": 3.0,
            "errors": [],
        },
    ]
    repeat = [
        _mapping("s1", "complete", [_exact_cell("past")]),
        phase1[1],
        _mapping("s3", "out_of_scope", []),
    ]

    paths = {}
    for name, rows in {
        "source": source,
        "phase1": phase1,
        "phase2": phase2,
        "cells": cells,
        "relations": relations,
        "attempts": attempts,
        "repeat": repeat,
    }.items():
        paths[name] = tmp_path / f"{name}.jsonl"
        write_jsonl(paths[name], rows)
    return paths


def test_audit_reports_transitions_categories_canonical_and_repeat_agreement(
    tmp_path,
) -> None:
    paths = _fixture_files(tmp_path)
    audit = audit_full_normalisation(
        source_path=paths["source"],
        phase1_path=paths["phase1"],
        phase2_path=paths["phase2"],
        phase1_attempts_path=paths["attempts"],
        cells_path=paths["cells"],
        relations_path=paths["relations"],
        repeat_mappings_path=paths["repeat"],
        schema_path=SCHEMA_PATH,
    )

    assert audit["phase1"]["results"]["counts"] == {
        "complete": 1,
        "partial": 1,
        "unresolved": 1,
        "out_of_scope": 0,
    }
    assert audit["source_coverage"]["phase2_expected_eligible_cohort"] == 1
    assert audit["phase2"]["transitions"]["result_transitions"] == {
        "partial->complete": 1
    }
    assert audit["phase2"]["transitions"]["branch_expansion"]["net_branches"] == 1
    assert audit["final"]["results"]["counts"]["complete"] == 2
    assert audit["phase1"]["by_cefr"]["A2"]["phase2_eligible"] == 1
    assert audit["phase1"]["partial_unresolved_groups"][
        "by_uncertain_dimension_signature"
    ] == {"none": 1, "tense": 1}
    assert audit["canonical"]["feature_set_match"] is True
    assert audit["canonical"]["all_cell_source_support_matches"] is True
    assert audit["canonical"]["source_cell_relations"]["relation_set_match"] is True
    assert audit["phase1_technical_status"]["rows_with_retries"] == 1
    assert audit["phase1_technical_status"]["error_type_counts"] == {
        "JSONDecodeError": 1
    }
    assert audit["repeated_annotation"]["result_exact_agreement"] == {
        "numerator": 2,
        "denominator": 3,
        "rate": 0.666667,
    }
    assert audit["repeated_annotation"][
        "feature_cell_multiset_exact_agreement_all_shared"
    ]["numerator"] == 2

    published = json.dumps(audit)
    assert "private descriptor" not in published
    assert "restricted explanatory prose" not in published
    assert "private failure message" not in published


def test_audit_fails_on_duplicate_or_unknown_source_ids(tmp_path) -> None:
    paths = _fixture_files(tmp_path)
    phase1 = [json.loads(line) for line in paths["phase1"].read_text().splitlines()]
    write_jsonl(paths["phase1"], [*phase1, phase1[0]])
    with pytest.raises(ValueError, match="duplicate source_id"):
        audit_full_normalisation(
            source_path=paths["source"],
            phase1_path=paths["phase1"],
            schema_path=SCHEMA_PATH,
        )

    paths = _fixture_files(tmp_path / "unknown")
    phase1 = [json.loads(line) for line in paths["phase1"].read_text().splitlines()]
    phase1[0] = {**phase1[0], "source_id": "not-in-source"}
    write_jsonl(paths["phase1"], phase1)
    with pytest.raises(ValueError, match="outside the expected set"):
        audit_full_normalisation(
            source_path=paths["source"],
            phase1_path=paths["phase1"],
            schema_path=SCHEMA_PATH,
        )


def test_incomplete_checkpoint_requires_explicit_opt_in(tmp_path) -> None:
    paths = _fixture_files(tmp_path)
    phase1 = [json.loads(line) for line in paths["phase1"].read_text().splitlines()]
    write_jsonl(paths["phase1"], phase1[:2])
    with pytest.raises(ValueError, match="source-ID set mismatch"):
        audit_full_normalisation(
            source_path=paths["source"],
            phase1_path=paths["phase1"],
            schema_path=SCHEMA_PATH,
        )

    audit = audit_full_normalisation(
        source_path=paths["source"],
        phase1_path=paths["phase1"],
        schema_path=SCHEMA_PATH,
        allow_incomplete=True,
    )
    assert audit["source_coverage"]["phase1"]["complete"] is False
    assert audit["source_coverage"]["phase1"]["missing_source_ids"] == 1
