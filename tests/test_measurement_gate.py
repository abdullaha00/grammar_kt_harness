from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from grammar_kt.io import write_jsonl, write_yaml
from grammar_kt.kc import activation_matches
from grammar_kt.measurement_gate import (
    audit_q_star,
    build_measurement_bundle,
    project_q_star,
    render_dense_q_matrix_csv,
    verify_measurement_artifacts,
    write_measurement_artifacts,
)

from .helpers import ROOT


def _toy_inputs():
    cells = [
        {
            "cell_id": "cell_ind_first",
            "features": {"mood": "indicative", "person": "first"},
        },
        {
            "cell_id": "cell_sub_first",
            "features": {"mood": "subjunctive", "person": "first"},
        },
        {
            "cell_id": "cell_ind_third",
            "features": {"mood": "indicative", "person": "third"},
        },
        {
            "cell_id": "cell_sub_third",
            "features": {"mood": "subjunctive", "person": "third"},
        },
    ]
    declarations = [
        ("kc_mood_indicative", {"cell": {"mood": "indicative"}}),
        ("kc_mood_subjunctive", {"cell": {"mood": "subjunctive"}}),
        ("kc_person_third", {"cell": {"person": "third"}}),
    ]
    kcs = []
    for kc_id, activation_rule in declarations:
        support = sorted(
            cell["cell_id"]
            for cell in cells
            if activation_matches(cell["features"], activation_rule)
        )
        kcs.append(
            {
                "id": kc_id,
                "name": kc_id,
                "activation_rule": activation_rule,
                "supporting_cell_ids": support,
                "cell_support": len(support),
            }
        )
    items = [
        {
            "item_id": "item_" + cell["cell_id"],
            "cell_id": cell["cell_id"],
            "prompt": "Choose the form: ____",
            "target_answer": "form",
            "accepted_answers": ["form"],
        }
        for cell in cells
    ]
    design = {
        "design_id": "toy_generator_v1",
        "support": {
            "minimum_items_per_kc_before_simulation": 1,
            "rare_kc_cell_threshold": 2,
            "rare_kc_item_threshold": 2,
        },
        "identifiability": {
            "require_nonempty_item_projection": True,
            "require_unique_q_columns": True,
            "require_full_column_rank": True,
        },
    }
    return cells, items, kcs, design


def _artifact_paths(tmp_path: Path) -> dict[str, Path]:
    return {
        "dense_q_matrix_path": tmp_path / "q_matrix.csv",
        "sparse_q_matrix_path": tmp_path / "q_matrix_sparse.jsonl",
        "audit_path": tmp_path / "measurement_audit.json",
        "manifest_path": tmp_path / "q_matrix_manifest.json",
    }


def test_toy_mood_person_q_star_and_gate_are_language_agnostic() -> None:
    cells, items, kcs, design = _toy_inputs()
    bundle = build_measurement_bundle(cells, items, kcs, design)

    assert bundle["audit"]["status"] == "PASS"
    assert bundle["audit"]["counts"] == {
        "canonical_cells": 4,
        "measured_cells": 4,
        "items": 4,
        "generator_kcs": 3,
        "q_edges": 6,
        "q_density": 0.5,
        "q_rank": 3,
        "full_column_rank": True,
        "distinct_canonical_cell_activation_rows": 4,
        "kc_pairs": 3,
    }
    assert all("tense" not in json.dumps(row) for row in bundle["q_rows"])
    pair = next(
        row
        for row in bundle["audit"]["identifiability"]["pair_geometry"]
        if row["left_kc_id"] == "kc_mood_indicative"
        and row["right_kc_id"] == "kc_person_third"
    )
    assert pair | {
        "a_only_items": 1,
        "b_only_items": 1,
        "a_plus_b_items": 1,
        "geometry": "a_only_b_only_and_a_plus_b",
    } == pair
    assert bundle["audit"]["provenance"] | {
        "learner_events_read": False,
        "discovered_kcs_read": False,
    } == bundle["audit"]["provenance"]


def test_projection_and_all_provenance_hashes_are_input_order_invariant() -> None:
    cells, items, kcs, design = _toy_inputs()
    forward = build_measurement_bundle(cells, items, kcs, design)
    reversed_inputs = build_measurement_bundle(
        list(reversed(cells)),
        list(reversed(items)),
        list(reversed(kcs)),
        deepcopy(design),
    )

    assert reversed_inputs == forward
    assert render_dense_q_matrix_csv(
        reversed_inputs["q_rows"], reversed_inputs["generator_kc_ids"]
    ) == render_dense_q_matrix_csv(
        forward["q_rows"], forward["generator_kc_ids"]
    )


def test_q_audit_rejects_added_removed_or_relabelled_edges() -> None:
    cells, items, kcs, design = _toy_inputs()
    q_rows = project_q_star(cells, items, kcs)
    tampered = deepcopy(q_rows)
    target = next(
        row for row in tampered if row["cell_id"] == "cell_ind_third"
    )
    target["generator_kc_ids"].remove("kc_person_third")

    with pytest.raises(ValueError, match="does not match declared activation rules"):
        audit_q_star(cells, items, kcs, tampered, design)

    tampered = deepcopy(q_rows)
    tampered[0]["cell_id"] = "cell_sub_first"
    with pytest.raises(ValueError, match="does not match declared activation rules"):
        audit_q_star(cells, items, kcs, tampered, design)


def test_generator_support_is_a_tamper_evident_activation_contract() -> None:
    cells, items, kcs, design = _toy_inputs()
    kcs[0]["supporting_cell_ids"].pop()

    with pytest.raises(ValueError, match="declared support does not match"):
        build_measurement_bundle(cells, items, kcs, design)


@pytest.mark.parametrize(
    "mutate, message",
    [
        (
            lambda cells, items, kcs: items.append(deepcopy(items[0])),
            "duplicate item ID",
        ),
        (
            lambda cells, items, kcs: kcs.append(deepcopy(kcs[0])),
            "duplicate generator-KC ID",
        ),
        (
            lambda cells, items, kcs: cells.append(deepcopy(cells[0])),
            "duplicate GrammarCell ID",
        ),
    ],
)
def test_duplicate_scientific_objects_are_rejected(mutate, message: str) -> None:
    cells, items, kcs, design = _toy_inputs()
    mutate(cells, items, kcs)
    with pytest.raises(ValueError, match=message):
        build_measurement_bundle(cells, items, kcs, design)


def test_malformed_or_unknown_activation_dimensions_are_rejected() -> None:
    cells, items, kcs, design = _toy_inputs()
    kcs[0]["activation_rule"] = {
        "cell": {"mood": "indicative"},
        "any": [{"cell": {"person": "first"}}],
    }
    with pytest.raises(ValueError, match="exactly one"):
        build_measurement_bundle(cells, items, kcs, design)

    cells, items, kcs, design = _toy_inputs()
    kcs[0]["activation_rule"] = {"cell": {"english_tense": "past"}}
    with pytest.raises(ValueError, match="unknown GrammarCell dimension"):
        build_measurement_bundle(cells, items, kcs, design)


def test_item_bank_cannot_smuggle_observed_or_oracle_fields_into_q_stage() -> None:
    cells, items, kcs, design = _toy_inputs()
    items[0]["correct"] = 1
    with pytest.raises(ValueError, match="learner/oracle/Q fields"):
        build_measurement_bundle(cells, items, kcs, design)


def test_equivalent_and_near_identical_columns_are_explicit_gate_findings() -> None:
    cells, items, kcs, design = _toy_inputs()
    duplicate = deepcopy(kcs[0])
    duplicate["id"] = "kc_duplicate_indicative"
    kcs.append(duplicate)
    audit = build_measurement_bundle(cells, items, kcs, design)["audit"]

    assert audit["status"] == "FAIL"
    assert "identical_q_columns" in audit["failures"]
    assert "rank_deficient_q_matrix" in audit["failures"]
    assert audit["identifiability"]["identical_q_columns"] == [
        {
            "generator_kc_ids": [
                "kc_duplicate_indicative",
                "kc_mood_indicative",
            ],
            "supporting_item_ids": [
                "item_cell_ind_first",
                "item_cell_ind_third",
            ],
        }
    ]
    assert audit["identifiability"][
        "canonical_kc_activation_equivalence_classes"
    ]

    cells, items, kcs, design = _toy_inputs()
    design["identifiability"].update(
        {"near_identical_jaccard": 0.3, "reject_near_identical_columns": True}
    )
    audit = build_measurement_bundle(cells, items, kcs, design)["audit"]
    assert audit["status"] == "FAIL"
    assert "near_identical_q_columns" in audit["failures"]
    assert len(audit["identifiability"]["near_identical_q_column_pairs"]) == 2


def test_rare_isolating_and_optional_regime_support_are_audited() -> None:
    cells, items, kcs, design = _toy_inputs()
    design["support"]["rare_kc_cell_threshold"] = 3
    design["support"]["rare_kc_item_threshold"] = 3
    regimes = {
        "cell_ind_first": "seen",
        "cell_sub_first": "seen",
        "cell_ind_third": "unseen_combination",
        "cell_sub_third": "unseen_combination",
    }
    audit = build_measurement_bundle(
        cells,
        items,
        kcs,
        design,
        grammar_regime_by_cell=regimes,
    )["audit"]

    assert len(audit["support"]["rare_generator_kcs"]) == 3
    support = {
        row["kc_id"]: row for row in audit["support"]["by_generator_kc"]
    }
    assert support["kc_mood_indicative"]["isolating_items"] == 1
    assert support["kc_person_third"]["isolating_items"] == 0
    assert support["kc_person_third"]["regime_support"] == {
        "seen": {"items": 0, "cells": 0},
        "unseen_combination": {"items": 2, "cells": 2},
    }
    assert audit["grammar_regime_support"]["seen"]["items"] == 2

    del regimes["cell_sub_third"]
    with pytest.raises(ValueError, match="cover exactly"):
        build_measurement_bundle(
            cells,
            items,
            kcs,
            design,
            grammar_regime_by_cell=regimes,
        )


def test_full_regime_assignment_rows_are_accepted_but_outcomes_are_rejected() -> None:
    cells, items, kcs, design = _toy_inputs()
    rows = [
        {
            "cell_id": cell["cell_id"],
            "grammar_regime": "seen",
            "features": cell["features"],
            "combination_subtype": None,
            "selection_reason": "structural fixture",
        }
        for cell in cells
    ]
    audit = build_measurement_bundle(
        cells,
        items,
        kcs,
        design,
        grammar_regime_by_cell=rows,
    )["audit"]
    assert audit["grammar_regime_support"]["seen"]["items"] == 4

    rows[0]["correct"] = 1
    with pytest.raises(ValueError, match="learner/oracle/Q fields"):
        build_measurement_bundle(
            cells,
            items,
            kcs,
            design,
            grammar_regime_by_cell=rows,
        )


def test_frozen_dense_sparse_audit_and_manifest_detect_byte_tampering(
    tmp_path: Path,
) -> None:
    cells, items, kcs, design = _toy_inputs()
    bundle = build_measurement_bundle(cells, items, kcs, design)
    paths = _artifact_paths(tmp_path)
    manifest = write_measurement_artifacts(bundle, **paths)
    verify_measurement_artifacts(bundle, **paths)

    dense_text = paths["dense_q_matrix_path"].read_text(encoding="utf-8")
    assert dense_text.splitlines()[0] == (
        "item_id,kc_mood_indicative,kc_mood_subjunctive,kc_person_third"
    )
    assert manifest["scientific_boundary"]["learner_events_read"] is False
    paths["dense_q_matrix_path"].write_text(
        dense_text.replace(",1,0,0", ",0,0,0", 1), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="refusing to overwrite changed frozen"):
        verify_measurement_artifacts(bundle, **paths)
    with pytest.raises(ValueError, match="refusing to overwrite changed frozen"):
        write_measurement_artifacts(bundle, **paths)


def test_direct_q_builder_script_writes_and_verifies_standard_artifacts(
    tmp_path: Path,
) -> None:
    cells, items, kcs, design = _toy_inputs()
    cells_path = tmp_path / "cells.jsonl"
    items_path = tmp_path / "items.jsonl"
    kcs_path = tmp_path / "kcs.jsonl"
    design_path = tmp_path / "design.yaml"
    write_jsonl(cells_path, cells)
    write_jsonl(items_path, items)
    write_jsonl(kcs_path, kcs)
    write_yaml(design_path, design)
    paths = _artifact_paths(tmp_path / "artifacts")
    base_command = [
        sys.executable,
        str(ROOT / "scripts/build_true_q_matrix.py"),
        "--cells",
        str(cells_path),
        "--items",
        str(items_path),
        "--kcs",
        str(kcs_path),
        "--design",
        str(design_path),
        "--dense-q-matrix",
        str(paths["dense_q_matrix_path"]),
        "--sparse-q-matrix",
        str(paths["sparse_q_matrix_path"]),
        "--audit",
        str(paths["audit_path"]),
        "--manifest",
        str(paths["manifest_path"]),
    ]
    result = subprocess.run(base_command, text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stderr
    assert "measurement gate PASS" in result.stdout
    verify = subprocess.run(
        [*base_command, "--verify-only"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert verify.returncode == 0, verify.stderr
    assert "verified frozen Q* artifacts" in verify.stdout
