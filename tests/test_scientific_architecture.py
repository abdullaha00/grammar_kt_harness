from __future__ import annotations

import ast
import copy
import inspect
import tempfile
import unittest
from pathlib import Path

from grammar_kt import folds
from grammar_kt.generation import generators
from grammar_kt.generation.items import item_identity
from grammar_kt.generation.validation import validate_items
from grammar_kt.grammar import canonical
from grammar_kt.io import ROOT, read_json, read_yaml
from grammar_kt.knowledge import policy, qmatrix, selection
from grammar_kt.measurement.operations import derive_operations
from grammar_kt.measurement.opportunities import build_measurement_opportunities
from grammar_kt.runner import STAGE_NAMES

from .helpers import PAST_NEGATIVE, cell_row, one_opportunity, paired_accepted_items


class GrammarAndMeasurementTests(unittest.TestCase):
    def test_normalisation_and_canonical_are_separate_runner_stages(self) -> None:
        self.assertLess(STAGE_NAMES.index("normalisation"), STAGE_NAMES.index("canonical"))
        mappings = [
            {"egp_id": "A", "result": "complete", "cells": [PAST_NEGATIVE], "note": None},
            {"egp_id": "B", "result": "partial", "cells": [{**PAST_NEGATIVE, "tense": ["past"]}], "note": "phase2 eligible: tense"},
        ]
        cells, edges = canonical.build(mappings)
        self.assertEqual((len(cells), len(edges)), (1, 1))
        self.assertEqual(edges[0]["egp_id"], "A")

    def test_operation_derivation_depends_on_cell_and_structural_conditions(self) -> None:
        cell = {**PAST_NEGATIVE, "tense": "present", "polarity": "positive", "clause": "polar_question"}
        base = {
            "subject_person": 3,
            "subject_number": "singular",
            "wh_role": None,
            "imperative_subtype": None,
        }
        lexical = derive_operations(cell, {**base, "predicate_class": "lexical_transitive"})
        copular = derive_operations(cell, {**base, "predicate_class": "copular"})
        self.assertEqual(lexical, ["do_support", "operator_inversion"])
        self.assertEqual(copular, ["operator_inversion"])
        source = inspect.getsource(derive_operations)
        self.assertNotIn("prompt", source)
        self.assertNotIn("lexicon", source)

    def test_opportunity_contains_no_surface_fold_or_kc_fields(self) -> None:
        opportunity = one_opportunity()
        keys = set(opportunity)
        self.assertEqual(
            keys,
            {
                "measurement_opportunity_id", "canonical_cell_id", "cell",
                "structural_conditions", "expected_operations",
                "source_descriptor_ids", "coverage_reasons",
            },
        )
        self.assertTrue(opportunity["measurement_opportunity_id"].startswith("OPP_"))
        self.assertFalse(any("frame" in key or "fold" in key or "kc" in key.lower() for key in keys))

    def test_fold_annotation_cannot_change_opportunity_or_item_identity(self) -> None:
        opportunity, standalone, _dialogue = paired_accepted_items()
        before = (opportunity["measurement_opportunity_id"], standalone["item_id"])
        annotated = folds.annotate_items([standalone], {standalone["canonical_cell_id"]: "compositional_holdout"})[0]
        self.assertEqual(before, (opportunity["measurement_opportunity_id"], annotated["item_id"]))
        self.assertEqual(annotated["canonical_split"], "compositional_holdout")


class GenerationAndValidationTests(unittest.TestCase):
    def test_same_opportunity_generates_different_format_item_ids(self) -> None:
        opportunity, standalone, dialogue = paired_accepted_items()
        self.assertEqual(standalone["measurement_opportunity_id"], opportunity["measurement_opportunity_id"])
        self.assertEqual(dialogue["measurement_opportunity_id"], opportunity["measurement_opportunity_id"])
        self.assertEqual(standalone["canonical_cell_id"], dialogue["canonical_cell_id"])
        self.assertEqual(standalone["validated_structure"]["operations"], dialogue["validated_structure"]["operations"])
        self.assertNotEqual(standalone["item_id"], dialogue["item_id"])
        self.assertEqual(standalone["item_family"], "standalone_completion")
        self.assertEqual(dialogue["item_family"], "dialogue_completion")

    def test_generator_interface_has_no_policy_or_fold_input(self) -> None:
        self.assertEqual(
            list(inspect.signature(generators.generate_items).parameters),
            ["opportunities", "generator_config", "evidence_root"],
        )
        source = inspect.getsource(generators)
        self.assertNotIn("grammar_kt.knowledge", source)
        self.assertNotIn("grammar_kt.folds", source)
        config = read_yaml("modules/generation/generators/llm_standalone_fixture_v0.yaml")
        config["fold"] = "development"
        with self.assertRaisesRegex(ValueError, "forbidden"):
            generators.load_generator_config(config)

    def test_live_blind_evaluator_uses_a_distinct_model(self) -> None:
        generator_backend = read_yaml("modules/generation/generators/backend.yaml")
        evaluator_backend = read_yaml("modules/generation/validation/backend.yaml")
        self.assertNotEqual(generator_backend["model"], evaluator_backend["model"])

    def test_hard_validator_catches_changed_cell_reference(self) -> None:
        opportunity, item, _ = paired_accepted_items()
        changed = copy.deepcopy(item)
        changed["canonical_cell_id"] = "CELL_OTHER"
        changed["item_id"] = item_identity(changed)
        result = validate_items(
            [changed], [opportunity], "modules/generation/validation/blind_fixture_v0.yaml"
        )
        self.assertFalse(result["accepted"])
        self.assertTrue(any("canonical cell reference" in reason for reason in result["rejected"][0]["reasons"]))

    def test_blind_validator_rejects_surface_grammar_mismatch(self) -> None:
        opportunity = one_opportunity()
        generator_config = read_yaml("modules/generation/generators/llm_standalone_fixture_v0.yaml")
        generator_config["backend_config"] = {
            "kind": "fixture_map",
            "default": {
                "content": {"prompt": "Complete: Yesterday, the technician ___ the report."},
                "target_answer": "Yesterday, the technician wrote the report.",
                "accepted_answers": ["Yesterday, the technician wrote the report."],
            },
        }
        candidate = generators.generate_items([opportunity], generator_config)["candidates"][0]
        evaluator = read_yaml("modules/generation/validation/blind_fixture_v0.yaml")
        evaluator["structural_backend_config"] = {
            "kind": "fixture_map",
            "default": {
                "cell": {**PAST_NEGATIVE, "polarity": "positive"},
                "operations": [],
                "predicate_class": "lexical_transitive",
                "agreement_site": "main_verb",
            },
        }
        result = validate_items([candidate], [opportunity], evaluator)
        self.assertEqual(len(result["rejected"]), 1)
        self.assertIn("cell_mismatch", result["report"]["failure_types"])
        evidence = result["rejected"][0]["item"]["validation_metadata"]
        self.assertTrue(evidence["intended_target_hidden_from_evaluator"])


class KnowledgeTests(unittest.TestCase):
    def test_selection_uses_cells_and_opportunities_not_wording(self) -> None:
        fixture = read_json("modules/knowledge/selection/fixtures/core.json")
        config = read_json("modules/knowledge/selection/configs/deterministic_v0.json")
        first = selection.evaluate_fixture(copy.deepcopy(fixture), config)
        fixture["irrelevant_generated_wording"] = ["one", "two"]
        second = selection.evaluate_fixture(copy.deepcopy(fixture), config)
        self.assertEqual(first["selected_policy"], second["selected_policy"])
        self.assertNotIn("items", inspect.signature(selection.evaluate_fixture).parameters)

    def test_holdout_structure_cannot_change_selected_policy(self) -> None:
        fixture = read_json("modules/knowledge/selection/fixtures/core.json")
        config = read_json("modules/knowledge/selection/configs/deterministic_v0.json")
        original = selection.evaluate_fixture(copy.deepcopy(fixture), config)
        holdout_ids = {
            row["canonical_cell_id"]
            for row in fixture["cell_splits"]
            if row["split"] != "development"
        }
        changed = copy.deepcopy(fixture)
        for row in changed["canonical_cells"]:
            if row["canonical_cell_id"] in holdout_ids:
                row["source_descriptor_ids"] = ["HELDOUT_MUTATION"]
                row["source_mapping_notes"] = {"HELDOUT_MUTATION": "evaluation-only change"}
        mutated = selection.evaluate_fixture(changed, config)
        self.assertEqual(original["selected_policy"], mutated["selected_policy"])
        self.assertTrue(original["discovery"]["holdout_content_read"] is False)

    def test_frozen_policy_applies_identically_across_formats(self) -> None:
        opportunity, standalone, dialogue = paired_accepted_items()
        for item in (standalone, dialogue):
            item["canonical_split"] = "development"
        frozen = policy.load_policy(ROOT / "modules/knowledge/policies/factorized.json")
        projections, cards = policy.project_items([standalone, dialogue], [opportunity], frozen)
        self.assertEqual(projections[0]["kc_ids"], projections[1]["kc_ids"])
        self.assertEqual({row["measurement_opportunity_id"] for row in projections}, {opportunity["measurement_opportunity_id"]})
        self.assertTrue(cards)

    def test_qmatrix_consumes_only_frozen_projection(self) -> None:
        opportunity, standalone, _ = paired_accepted_items()
        standalone["canonical_split"] = "development"
        frozen = policy.load_policy(ROOT / "modules/knowledge/policies/factorized.json")
        projections, cards = policy.project_items([standalone], [opportunity], frozen)
        _columns, rows, edges, audit = qmatrix.build([standalone], cards, projections)
        self.assertEqual(audit["status"], "PASS")
        self.assertEqual(rows[0][0], standalone["item_id"])
        self.assertTrue(all(edge["measurement_opportunity_id"] == opportunity["measurement_opportunity_id"] for edge in edges))
        self.assertNotIn("apply_policy", inspect.getsource(qmatrix.build))


class RepositoryBoundaryTests(unittest.TestCase):
    def test_active_package_has_no_archive_import(self) -> None:
        offenders = []
        for path in (ROOT / "src/grammar_kt").rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import) and any("archived_code" in name.name for name in node.names):
                    offenders.append(path)
                if isinstance(node, ast.ImportFrom) and "archived_code" in (node.module or ""):
                    offenders.append(path)
        self.assertEqual(offenders, [])

    def test_code_and_method_resources_mirror_five_modules(self) -> None:
        for name in ("grammar", "measurement", "generation", "knowledge", "evaluation"):
            self.assertTrue((ROOT / "src/grammar_kt" / name).is_dir())
            self.assertTrue((ROOT / "modules" / name).is_dir())
        self.assertTrue((ROOT / "src/grammar_kt/knowledge/selection.py").is_file())
        self.assertTrue((ROOT / "modules/knowledge/selection").is_dir())


if __name__ == "__main__":
    unittest.main()
