from __future__ import annotations

from copy import deepcopy

from grammar_kt.io import read_jsonl, read_yaml
from scripts.investigate_generator_kcs import (
    ALTERNATIVE_ORDER,
    build_exact_cell_inventory,
    build_feature_only_inventory,
    investigate_generator_kcs,
)

from .helpers import ROOT


def test_schema_driven_controls_work_without_english_feature_names() -> None:
    schema = {
        "schema_id": "toy_mood_person_v1",
        "dimension_order": ["mood", "person"],
        "dimensions": {
            "mood": {"allowed_values": ["indicative", "subjunctive"]},
            "person": {"allowed_values": ["first", "third"]},
        },
    }
    cells = [
        {
            "cell_id": f"toy_{index}",
            "features": {"mood": mood, "person": person},
        }
        for index, (mood, person) in enumerate(
            [
                ("indicative", "first"),
                ("indicative", "third"),
                ("subjunctive", "first"),
                ("subjunctive", "third"),
            ],
            1,
        )
    ]
    declaration = {
        "declaration_id": "toy_generator_declaration_v1",
        "language": "ToyLanguage",
        "language_specific": True,
        "reference_conditions": {
            "mood": ["indicative"],
            "person": ["third"],
        },
    }

    feature = build_feature_only_inventory(cells, schema, declaration)
    exact = build_exact_cell_inventory(cells, schema, declaration)

    assert {row["id"] for row in feature["kcs"]} == {
        "gkc_feature__mood__subjunctive",
        "gkc_feature__person__first",
    }
    assert len(exact["kcs"]) == 4
    assert all(
        set(row["activation_rule"]["cell"]) <= {"mood", "person"}
        for row in [*feature["kcs"], *exact["kcs"]]
    )
    assert feature["metadata"]["learner_outcomes_read"] is False
    assert exact["metadata"]["discovered_kcs_read"] is False


def test_medium_pilot_compares_four_outcome_free_structural_alternatives() -> None:
    cells = read_jsonl(ROOT / "data/grammar_kt_medium_v1/canonical/cells.jsonl")
    items = read_jsonl(ROOT / "data/grammar_kt_medium_v1/items/selected_bank.jsonl")
    schema = read_yaml(ROOT / "modules/grammar/canonical/schema.yaml")
    design = read_yaml(ROOT / "modules/kcs/generator/design.yaml")
    declaration = read_yaml(ROOT / "modules/kcs/generator/english_kcs.yaml")

    artifact = investigate_generator_kcs(
        cells, items, schema, design, declaration
    )

    assert [row["alternative"] for row in artifact["comparison"]] == list(
        ALTERNATIVE_ORDER
    )
    assert {
        row["alternative"]: row["generator_kcs"]
        for row in artifact["comparison"]
    } == {
        "hybrid": 9,
        "hybrid_plus_perfect_progressive_chain": 10,
        "feature_only_control": 10,
        "exact_cell_diagnostic": 24,
    }
    assert all(row["full_column_rank"] for row in artifact["comparison"])
    assert artifact["scientific_boundary"] | {
        "outcome_free": True,
        "learner_outcomes_read": False,
        "kc_selector_used": False,
        "kt_used": False,
    } == artifact["scientific_boundary"]

    chain = artifact["alternatives"][
        "hybrid_plus_perfect_progressive_chain"
    ]
    aspect_chain_contrasts = [
        row
        for row in chain["optional_interaction_pair_contrasts"]
        if "gkc_aspect_" in row["left_kc_id"]
        or "gkc_aspect_" in row["right_kc_id"]
    ]
    assert len(aspect_chain_contrasts) == 2
    assert all(row["cooccurring_items"] == 5 for row in aspect_chain_contrasts)
    assert all(not row["two_sided_contrast"] for row in aspect_chain_contrasts)
    assert chain["summary"]["q_rank"] == 10

    exact = artifact["alternatives"]["exact_cell_diagnostic"]
    assert exact["summary"]["reused_across_multiple_cells"] == 0
    assert exact["summary"]["pair_geometry"]["cooccurring_pairs"] == 0
    assert exact["measurement_audit"]["failures"] == [
        "generator_kcs_below_minimum_item_support"
    ]
    assert all(
        row["q_projection"]["rows_embedded"]
        for row in artifact["alternatives"].values()
    )
    assert all(
        len(row["q_projection"]["rows"]) == len(items)
        for row in artifact["alternatives"].values()
    )


def test_pilot_discards_response_and_oracle_fields_before_comparison() -> None:
    cells = read_jsonl(ROOT / "data/grammar_kt_medium_v1/canonical/cells.jsonl")
    items = read_jsonl(ROOT / "data/grammar_kt_medium_v1/items/selected_bank.jsonl")
    schema = read_yaml(ROOT / "modules/grammar/canonical/schema.yaml")
    design = read_yaml(ROOT / "modules/kcs/generator/design.yaml")
    declaration = read_yaml(ROOT / "modules/kcs/generator/english_kcs.yaml")
    baseline = investigate_generator_kcs(
        cells, items, schema, design, declaration
    )

    contaminated_cells = deepcopy(cells)
    contaminated_items = deepcopy(items)
    for cell in contaminated_cells:
        cell["oracle_mastery"] = 0.99
    for item in contaminated_items:
        item.update({"correct": 1, "learner_id": "forbidden", "kt_score": 1.0})
    repeated = investigate_generator_kcs(
        contaminated_cells,
        contaminated_items,
        schema,
        design,
        declaration,
    )

    assert repeated["comparison"] == baseline["comparison"]
    assert repeated["alternatives"] == baseline["alternatives"]
    assert repeated["inputs"] == baseline["inputs"]
