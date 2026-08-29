from __future__ import annotations

from grammar_kt.full_normalisation import (
    adapt_full_egp_source,
    source_cell_relations,
    stable_canonicalise,
)
from grammar_kt.io import read_yaml

from .helpers import ROOT


def test_full_source_adapter_uses_only_the_typed_resource_boundary() -> None:
    raw = [
        {
            "source": "EGP",
            "egp_id": "opaque-1",
            "cefr_band": "B1",
            "supercategory": "EXAMPLE",
            "subcategory": "example",
            "guideword": "FORM: EXAMPLE",
            "can_do": "Can use an example form.",
            "usable": False,
            "examples": ["Example."],
            "lexical_range": "N/A",
        }
    ]

    assert adapt_full_egp_source(raw) == [
        {
            "source_id": "opaque-1",
            "supercategory": "EXAMPLE",
            "subcategory": "example",
            "guideword": "FORM: EXAMPLE",
            "can_do": "Can use an example form.",
            "examples": ["Example."],
            "cefr": "B1",
        }
    ]


def test_stable_canonical_ids_do_not_depend_on_source_or_branch_order() -> None:
    schema = read_yaml(ROOT / "modules/grammar/canonical/schema.yaml")
    present = {
        "tense": "present",
        "aspect": "none",
        "voice": "active",
        "polarity": "positive",
        "clause": "declarative",
        "modal": "none",
    }
    past = {**present, "tense": "past"}
    mappings = [
        {
            "source_id": "b",
            "result": "complete",
            "cells": [present, past],
            "phase2_eligible": [],
            "note": "two branches",
        },
        {
            "source_id": "a",
            "result": "complete",
            "cells": [present],
            "phase2_eligible": [],
            "note": "duplicate cell",
        },
    ]

    first = stable_canonicalise(mappings, schema)
    second = stable_canonicalise(list(reversed(mappings)), schema)
    assert first == second
    assert len(first) == 2
    assert all(row["cell_id"].startswith("gc_") for row in first)
    present_row = next(row for row in first if row["features"] == present)
    assert present_row["source_ids"] == ["a", "b"]


def test_public_source_cell_relations_are_opaque_and_traceable() -> None:
    schema = read_yaml(ROOT / "modules/grammar/canonical/schema.yaml")
    features = {
        "tense": "present",
        "aspect": "none",
        "voice": "active",
        "polarity": "positive",
        "clause": "declarative",
        "modal": "none",
    }
    mappings = [
        {
            "source_id": "opaque-1",
            "result": "complete",
            "cells": [features],
            "phase2_eligible": [],
            "note": "derived note not copied to the relation",
        }
    ]
    cells = stable_canonicalise(mappings, schema)
    relations = source_cell_relations(mappings, cells, schema)

    assert relations == [
        {
            "source_id": "opaque-1",
            "cell_id": cells[0]["cell_id"],
            "source_branch_index": 0,
        }
    ]
    assert "note" not in relations[0]
