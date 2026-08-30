from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/experiments/measurement_realism_audit.py"
SPEC = importlib.util.spec_from_file_location("measurement_realism_audit", SCRIPT)
assert SPEC and SPEC.loader
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def test_frozen_full_v1_audit_input_has_public_measurement_fields_only() -> None:
    rows = audit.load_enriched_items(ROOT / "data/grammar_kt_full_v1")
    assert len(rows) == 113
    assert len({row["item_id"] for row in rows}) == 113
    assert {row["format"] for row in rows} == {"controlled_production"}
    forbidden = {
        "correct",
        "learner_id",
        "mastery",
        "response_probability",
        "response_draw",
    }
    assert all(not (set(row) & forbidden) for row in rows)
    assert all(row["active_generator_kcs"] for row in rows)


def test_plurality_uses_declared_severity_only_for_ties() -> None:
    order = ["pass", "minor_concern", "major_concern"]
    assert audit.plurality(["pass", "pass", "major_concern"], order) == "pass"
    assert audit.plurality(["pass", "major_concern"], order) == "major_concern"


def test_learner_prompt_hides_generator_annotations() -> None:
    config = audit.read_yaml(ROOT / "modules/measurement_realism/item_audit.yaml")
    row = audit.load_enriched_items(ROOT / "data/grammar_kt_full_v1")[0]
    prompt = audit.render_prompt("learner", config["roles"]["learner"], config, [row])
    encoded = prompt.split("ITEMS:\n", 1)[1]
    assert "active_generator_kcs" not in encoded
    assert "grammar_cell" not in encoded
    assert row["item_id"] in encoded


def test_role_result_requires_exact_dimensions_and_item_coverage() -> None:
    config = audit.read_yaml(ROOT / "modules/measurement_realism/item_audit.yaml")
    ratings = {name: "pass" for name in config["dimensions"]}
    valid = {
        "role": "learner",
        "judgments": [
            {
                "item_id": "item_1",
                "ratings": ratings,
                "disposition": "usable_as_is",
                "primary_concern": "none",
                "confidence": "high",
            }
        ],
    }
    rows = audit.validate_role_result(valid, "learner", ["item_1"], config)
    assert rows[0]["item_id"] == "item_1"
    invalid = {**valid, "judgments": [{**valid["judgments"][0], "ratings": {}}]}
    with pytest.raises(ValueError, match="dimensions"):
        audit.validate_role_result(invalid, "learner", ["item_1"], config)


def test_critic_output_schema_requires_exact_rating_keys() -> None:
    config = audit.read_yaml(ROOT / "modules/measurement_realism/item_audit.yaml")
    schema = audit.critic_output_schema("learner", config)
    judgment = schema["properties"]["judgments"]["items"]
    ratings = judgment["properties"]["ratings"]
    assert ratings["required"] == list(config["dimensions"])
    assert ratings["additionalProperties"] is False
    assert schema["properties"]["role"]["enum"] == ["learner"]
