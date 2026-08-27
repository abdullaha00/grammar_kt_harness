from __future__ import annotations

from functools import partial
from pathlib import Path
from typing import Any

from grammar_kt.canonicalise import canonicalise
from grammar_kt.fold import apply_fold
from grammar_kt.generate import generate_items
from grammar_kt.io import call_model, load_typed_resource, read_jsonl, read_text, read_yaml
from grammar_kt.normalise import normalise
from grammar_kt.validate_items import validate_items


ROOT = Path(__file__).resolve().parents[1]

RESOURCE_PATH = ROOT / "data/fixtures/egp_pilot.jsonl"
RESOURCE_SCHEMA = read_yaml(ROOT / "modules/grammar/resource/egp/schema.yaml")
PHASE1_PROMPT = read_text(
    ROOT / "modules/grammar/resource/egp/normalisation/phase1.txt"
)
PHASE2_PROMPT = read_text(
    ROOT / "modules/grammar/resource/egp/normalisation/phase2.txt"
)
NORMALISATION_RULEBOOK = read_text(
    ROOT / "modules/grammar/resource/egp/normalisation/rulebook.md"
)
GRAMMAR_SCHEMA = read_yaml(ROOT / "modules/grammar/canonical/schema.yaml")

GENERATION_PROMPT = read_text(ROOT / "modules/items/generation/prompt.txt")
GENERATION_RULEBOOK = read_text(ROOT / "modules/items/generation/rulebook.md")
GENERATION_DESIGN = read_yaml(ROOT / "modules/items/generation/design.yaml")
ITEM_FORMAT = read_yaml(
    ROOT / "modules/items/generation/formats/controlled_production.yaml"
)
LEXICON = read_jsonl(ROOT / "modules/items/generation/lexicon.jsonl")

VALIDATION_PROMPT = read_text(ROOT / "modules/items/validation/prompt.txt")
VALIDATION_CRITERIA = read_yaml(ROOT / "modules/items/validation/criteria.yaml")

GRAMMAR_FOLD_SPEC = read_yaml(ROOT / "modules/simulation/folds/reference.yaml")
SIMULATION_WORLD = read_yaml(ROOT / "modules/simulation/world.yaml")
FACTORIZED_POLICY = read_yaml(ROOT / "modules/kcs/policies/factorized.yaml")
FULL_CELL_POLICY = read_yaml(ROOT / "modules/kcs/policies/full_cell.yaml")
CANDIDATE_SPACE = read_yaml(ROOT / "modules/kcs/candidates.yaml")
OBLIGATION_POLICY = read_yaml(ROOT / "modules/kcs/obligations.yaml")
SELECTOR = read_yaml(ROOT / "modules/kcs/selector.yaml")
KT_PROTOCOL = read_yaml(ROOT / "modules/evaluation/kt/protocol.yaml")
EVALUATION_PROTOCOL = read_yaml(ROOT / "modules/evaluation/protocol.yaml")

FIXTURE_MODEL_CALL = partial(
    call_model,
    fixture_responses=read_yaml(ROOT / "data/fixtures/model_responses.yaml"),
)

PRESENT = {
    "tense": "present",
    "aspect": "none",
    "voice": "active",
    "polarity": "positive",
    "clause": "declarative",
    "modal": "none",
}
PAST_NEGATIVE = {**PRESENT, "tense": "past", "polarity": "negative"}


def base_bank() -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    resources = load_typed_resource(RESOURCE_PATH, RESOURCE_SCHEMA)
    mappings = normalise(
        resources,
        PHASE1_PROMPT,
        PHASE2_PROMPT,
        NORMALISATION_RULEBOOK,
        GRAMMAR_SCHEMA,
        model="fixture",
        reasoning_effort="deterministic",
        model_call=FIXTURE_MODEL_CALL,
    )
    cells = canonicalise(mappings, GRAMMAR_SCHEMA)
    candidates = generate_items(
        cells,
        GENERATION_PROMPT,
        GENERATION_RULEBOOK,
        GENERATION_DESIGN,
        ITEM_FORMAT,
        LEXICON,
        model="fixture",
        reasoning_effort="deterministic",
        model_call=FIXTURE_MODEL_CALL,
    )
    accepted, judgments = validate_items(
        candidates,
        cells,
        VALIDATION_PROMPT,
        VALIDATION_CRITERIA,
        model="fixture",
        reasoning_effort="deterministic",
        model_call=FIXTURE_MODEL_CALL,
    )
    fold = apply_fold(cells, GRAMMAR_FOLD_SPEC)
    return mappings, cells, candidates, accepted, judgments, fold


def validator_output(
    criteria: dict[str, Any], failing: str | None = None
) -> dict[str, Any]:
    return {
        "judgments": {
            name: {"passed": name != failing, "note": "fixture judgment"}
            for name in criteria
        }
    }
