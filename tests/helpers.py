from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from grammar_kt.generation.generators import generate_items
from grammar_kt.generation.validation import validate_items
from grammar_kt.measurement.opportunities import build_measurement_opportunities


PAST_NEGATIVE = {
    "tense": "past",
    "aspect": "none",
    "voice": "active",
    "polarity": "negative",
    "clause": "declarative",
    "modal": "none",
}


def cell_row(
    cell: dict[str, str] | None = None,
    *,
    canonical_cell_id: str = "CELL_FIX_PAST_NEGATIVE",
) -> dict[str, Any]:
    return {
        "canonical_cell_id": canonical_cell_id,
        "cell": deepcopy(cell or PAST_NEGATIVE),
        "source_descriptor_ids": ["FIXTURE_EGP"],
        "source_mapping_notes": {"FIXTURE_EGP": None},
    }


def one_opportunity() -> dict[str, Any]:
    return build_measurement_opportunities(
        [cell_row()],
        {
            "include_predicate_class_contrasts": False,
            "include_agreement_variants": False,
        },
    )[0]


def paired_accepted_items(root: Path | None = None) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    opportunity = one_opportunity()
    items = []
    for label in ("standalone", "dialogue"):
        generated = generate_items(
            [opportunity],
            f"modules/generation/generators/llm_{label}_fixture_v0.yaml",
            evidence_root=(root / label / "generation") if root else None,
        )
        validated = validate_items(
            generated["candidates"],
            [opportunity],
            "modules/generation/validation/blind_fixture_v0.yaml",
            evidence_root=(root / label / "validation") if root else None,
        )
        assert validated["report"]["status"] == "PASS"
        items.append(validated["accepted"][0])
    return opportunity, items[0], items[1]
