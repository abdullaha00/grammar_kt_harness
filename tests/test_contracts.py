"""Small tests for frozen contracts and module boundaries, not historical behavior."""

from __future__ import annotations

import unittest
from pathlib import Path

from modules.canonical.run import build
from modules.items.helpers import item_id, render_prompt
from modules.kc.policy import matches
from modules.normalization.run import _load_validator
from modules.provenance.run import build_graph
from modules.realization.engine import realize, validate_spec
from modules.simulation.run import FORBIDDEN_OBSERVABLE, difficulty
from shared.utils.io import ROOT, read_json, sha256_file


SUBJECT = {"text": "The technician", "person": 3, "number": "singular"}
WRITE = {
    "frame_type": "transitive", "base": "write", "past": "wrote",
    "past_participle": "written", "present_participle": "writing",
    "third_singular": "writes", "object": "the report", "complement": None,
    "passive_compatible": True,
}
COPULAR = {
    "frame_type": "copular", "base": "be", "past": None,
    "past_participle": "been", "present_participle": "being",
    "third_singular": None, "object": None, "complement": "ready",
    "passive_compatible": False,
}


def spec(wh=None) -> dict:
    return {
        "realization_id": "REAL_0000000000000000",
        "canonical_cell_id": "CELL_0000000000000000",
        "source_descriptor_id": "fixture", "predicate_frame_id": "frame",
        "subject": SUBJECT, "wh": wh, "imperative_subtype": None, "let_pronoun": None,
    }


class FrozenNormalizationTests(unittest.TestCase):
    def test_frozen_hashes(self) -> None:
        frozen = ROOT / "modules/normalization/v1_3"
        for filename, expected in read_json(frozen / "artifact_hashes.json").items():
            self.assertEqual(sha256_file(frozen / filename), expected, filename)

    def test_phase2_changes_only_eligible_dimension(self) -> None:
        validator = _load_validator(ROOT / "modules/normalization/v1_3/validate.py")
        cell = {
            "tense": ["present", "past"], "aspect": "none", "voice": "active",
            "polarity": "positive", "clause": "declarative", "modal": "none",
        }
        first = {"egp_id": "E", "result": "partial", "cells": [cell], "note": "phase2 eligible: tense"}
        refined = {"egp_id": "E", "result": "complete", "cells": [{**cell, "tense": "present"}], "note": first["note"]}
        self.assertEqual(validator.validate_mapping(first, "E", phase=1), [])
        self.assertEqual(validator.validate_mapping(refined, "E", phase=2), [])
        self.assertEqual(validator.validate_phase2_transition(first, refined), [])
        changed = {**refined, "cells": [{**refined["cells"][0], "aspect": "perfect"}]}
        self.assertTrue(validator.validate_phase2_transition(first, changed))


class CanonicalTests(unittest.TestCase):
    def test_deduplicates_complete_cells_and_ignores_partial(self) -> None:
        cell = {
            "tense": "past", "aspect": "none", "voice": "active",
            "polarity": "positive", "clause": "declarative", "modal": "none",
        }
        mappings = [
            {"egp_id": "A", "result": "complete", "cells": [cell], "note": None},
            {"egp_id": "B", "result": "complete", "cells": [dict(cell)], "note": None},
            {"egp_id": "C", "result": "partial", "cells": [{**cell, "tense": ["past"]}], "note": "x"},
        ]
        cells, edges = build(mappings)
        self.assertEqual(len(cells), 1)
        self.assertEqual(len(edges), 2)
        self.assertEqual({row["egp_id"] for row in edges}, {"A", "B"})


class RealizationTests(unittest.TestCase):
    def test_copular_question(self) -> None:
        cell = {"tense": "present", "aspect": "none", "voice": "active", "polarity": "positive", "clause": "polar_question", "modal": "none"}
        self.assertEqual(realize(spec(), cell, COPULAR)["surface"], "Is the technician ready?")

    def test_subject_and_object_wh_differ(self) -> None:
        subject_cell = {"tense": "present", "aspect": "none", "voice": "active", "polarity": "positive", "clause": "subject_wh_question", "modal": "none"}
        object_cell = {**subject_cell, "clause": "non_subject_wh_question"}
        subject = realize(spec({"role": "subject", "phrase": "who"}), subject_cell, WRITE)
        obj = realize(spec({"role": "object", "phrase": "what"}), object_cell, WRITE)
        self.assertEqual(subject["surface"], "Who writes the report?")
        self.assertNotIn("do_support", subject["operations"])
        self.assertEqual(obj["surface"], "What does the technician write?")
        self.assertIn("do_support", obj["operations"])

    def test_incompatible_passive_rejected(self) -> None:
        cell = {"tense": "present", "aspect": "none", "voice": "passive", "polarity": "positive", "clause": "declarative", "modal": "none"}
        self.assertIn("predicate frame is not passive-compatible", validate_spec(spec(), cell, COPULAR, None))


class KCAndItemTests(unittest.TestCase):
    def test_activation_expression(self) -> None:
        opportunity = {
            "cell": {"tense": "past", "clause": "polar_question"},
            "realization_operations": ["do_support", "operator_inversion"],
        }
        self.assertTrue(matches({"cell": {"tense": "past"}}, opportunity))
        self.assertTrue(matches({"all": [{"operation": "do_support"}, {"cell": {"clause": "polar_question"}}]}, opportunity))
        self.assertFalse(matches({"cell": {"tense": "present"}}, opportunity))

    def test_item_id_and_template_are_structural(self) -> None:
        current_spec = spec()
        self.assertEqual(item_id("KC_A", current_spec, 0), item_id("KC_A", current_spec, 0))
        self.assertNotEqual(item_id("KC_A", current_spec, 0), item_id("KC_B", current_spec, 0))
        cell = {"tense": "past", "aspect": "perfect", "voice": "active", "polarity": "negative", "clause": "declarative", "modal": "none"}
        template = (ROOT / "modules/items/config/controlled_transformation_v0_1.txt").read_text(encoding="utf-8")
        prompt = render_prompt(template, cell, current_spec, {"lemma": "write", "object": "the report", "complement": None})
        for value in cell.values():
            self.assertIn(value, prompt)


class SimulationAndProvenanceTests(unittest.TestCase):
    def test_simulator_difficulty_and_oracle_boundary(self) -> None:
        self.assertEqual(difficulty("ITEM_X", -0.8, 0.8), difficulty("ITEM_X", -0.8, 0.8))
        self.assertLessEqual(abs(difficulty("ITEM_X", -0.8, 0.8)), 0.8)
        self.assertTrue({"pre_mastery", "post_mastery", "random_draw", "response_probability"} <= FORBIDDEN_OBSERVABLE)

    def test_typed_provenance_chain(self) -> None:
        item = {
            "item_id": "ITEM_0000000000000000", "canonical_cell_id": "CELL_0",
            "source_descriptor_ids": ["E"], "primary_kc_id": "KC_0", "all_kc_ids": ["KC_0"],
            "realization_spec": {"realization_id": "REAL_0", "source_descriptor_id": "E"},
            "item_family": "FIXTURE", "provenance": {"realization_version": "v1", "item_method_version": "v1"},
        }
        edges, audit = build_graph(
            [{"egp_id": "E", "primary_unit_id": "U", "final_phase": 1, "phase1_sha256": "x", "phase2_sha256": None}],
            [{"egp_id": "E", "canonical_cell_id": "CELL_0", "source_cell_index": 0, "source_mapping_result": "complete"}],
            [item],
            [{"item_id": item["item_id"], "kc_id": "KC_0", "edge_id": "Q", "activation_rule": {}}],
            [{"item_id": item["item_id"], "event_id": "EVENT_0"}],
        )
        self.assertEqual(audit["status"], "PASS")
        self.assertEqual(len(edges), 6)
        self.assertEqual({row["edge_type"] for row in edges}, {"SOURCE_TO_PHASE1", "FINAL_MAPPING_TO_CELL", "CELL_TO_REALIZATION", "REALIZATION_TO_ITEM", "ITEM_TO_KC", "ITEM_TO_INTERACTION"})


if __name__ == "__main__":
    unittest.main()
