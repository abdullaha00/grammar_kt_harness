from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from grammar_kt import canonical, folds, items, kc_candidates, kc_selection, realisation, simulation
from grammar_kt.canonical_schema import consistency_report
from grammar_kt.io import ROOT, read_json, read_jsonl, write_json, write_jsonl
from grammar_kt.item_diagnostic_reliability import analyse_repeated_diagnostics
from grammar_kt.normalisation_reliability import analyse_repeated_normalisations
from grammar_kt.realisation_space import enumerate_valid_realisations, validate_spec
from grammar_kt.records import grammar_cell
from grammar_kt.runner import stage_input_signatures, validate_reuse
from grammar_kt.source_sampling import sample_records


def fixture_bank() -> tuple[dict, dict, list[dict]]:
    fixture = read_json(ROOT / "modules/kc_selection/fixtures/core.json")
    frames = {
        row["predicate_frame_id"]: row
        for row in read_jsonl(realisation.LEXICON)
    }
    opportunities = items.build_item_opportunities(
        fixture["canonical_cells"],
        frames,
        read_json(ROOT / "modules/items/configs/fixed_bank_v0.json"),
    )
    bank = items.construct_items(
        opportunities,
        frames,
        (ROOT / "modules/items/families/controlled_transformation.txt").read_text(
            encoding="utf-8"
        ),
    )
    return fixture, frames, bank


class FoldAndRealisationBoundaryTests(unittest.TestCase):
    def test_fold_assignment_cannot_change_intrinsic_bank(self) -> None:
        fixture, _frames, bank = fixture_bank()
        first = {
            row["canonical_cell_id"]: row["split"] for row in fixture["cell_splits"]
        }
        second = {
            cell_id: (
                "compositional_holdout"
                if split == "development"
                else "development"
            )
            for cell_id, split in first.items()
        }
        first_view = folds.annotate_items(bank, first)
        second_view = folds.annotate_items(bank, second)

        intrinsic_fields = (
            "item_id", "realization_spec", "prompt", "target_answer",
            "accepted_answers", "realization_evidence",
        )
        self.assertEqual(
            [{field: row[field] for field in intrinsic_fields} for row in first_view],
            [{field: row[field] for field in intrinsic_fields} for row in second_view],
        )
        self.assertNotEqual(
            [row["canonical_split"] for row in first_view],
            [row["canonical_split"] for row in second_view],
        )
        self.assertEqual(
            items.item_bank_fingerprint(first_view),
            items.item_bank_fingerprint(second_view),
        )
        self.assertFalse(
            any("canonical_split" in row["generation_metadata"] for row in bank)
        )

    def test_subject_and_non_subject_wh_regressions(self) -> None:
        frames = {
            row["predicate_frame_id"]: row
            for row in read_jsonl(realisation.LEXICON)
        }
        fixtures = {
            row["fixture_label"]: row
            for row in read_jsonl(ROOT / "modules/realisation/fixtures/core.jsonl")
        }
        expected = {
            "subject_wh_no_inversion": "Who writes the report?",
            "object_wh_lexical_do": "What does the technician write?",
            "adjunct_wh_lexical_do": "When does the technician write the report?",
            "adjunct_wh_inherent_operator": "When was the technician ready?",
        }
        for label, surface in expected.items():
            fixture = fixtures[label]
            frame = frames[fixture["spec"]["predicate_frame_id"]]
            self.assertEqual(
                validate_spec(fixture["spec"], fixture["cell"], frame, None), [], label
            )
            derivation = realisation.realise(fixture["spec"], fixture["cell"], frame)
            self.assertEqual(derivation["surface"], surface, label)
        self.assertNotIn(
            "operator_inversion",
            realisation.realise(
                fixtures["subject_wh_no_inversion"]["spec"],
                fixtures["subject_wh_no_inversion"]["cell"],
                frames["FRAME_WRITE"],
            )["operations"],
        )

    def test_wh_item_opportunities_do_not_enter_agreement_baselines(self) -> None:
        frames = {
            row["predicate_frame_id"]: row
            for row in read_jsonl(realisation.LEXICON)
        }
        mapping = {
            "egp_id": "FIX_WH_ITEM",
            "result": "complete",
            "cells": [
                {
                    "tense": "present",
                    "aspect": "none",
                    "voice": "active",
                    "polarity": "positive",
                    "clause": "non_subject_wh_question",
                    "modal": "none",
                }
            ],
            "note": None,
        }
        cells, _edges = canonical.build([mapping])
        opportunities = items.build_item_opportunities(
            cells,
            frames,
            read_json(ROOT / "modules/items/configs/fixed_bank_v0.json"),
        )
        self.assertTrue(opportunities)
        self.assertTrue(
            all(row["realization_spec"]["wh"] is not None for row in opportunities)
        )
        self.assertFalse(
            any(
                reason.startswith("agreement_measurement:")
                for row in opportunities
                for reason in row["coverage_reasons"]
            )
        )

    def test_all_three_consumers_use_admissible_spec_validation(self) -> None:
        fixture, frames, _bank = fixture_bank()
        cells = fixture["canonical_cells"]
        edges = [
            {
                "canonical_cell_id": row["canonical_cell_id"],
                "egp_id": row["source_descriptor_ids"][0],
                "source_note": row["source_mapping_notes"].get(
                    row["source_descriptor_ids"][0]
                ),
            }
            for row in cells
        ]
        consumer_specs = [
            case["spec"] for case in realisation.build_cases(cells, edges, frames)
        ]
        for cell_row in cells:
            consumer_specs.extend(
                row["realization_spec"]
                for row in kc_candidates.nuisance_opportunities(cell_row, frames)
            )
        consumer_specs.extend(
            row["realization_spec"]
            for row in items.build_item_opportunities(
                cells,
                frames,
                read_json(ROOT / "modules/items/configs/fixed_bank_v0.json"),
            )
        )
        cell_by_id = {row["canonical_cell_id"]: row for row in cells}
        self.assertTrue(consumer_specs)
        for spec in consumer_specs:
            cell_row = cell_by_id[spec["canonical_cell_id"]]
            note = cell_row["source_mapping_notes"].get(spec["source_descriptor_id"])
            self.assertEqual(
                validate_spec(spec, cell_row["cell"], frames[spec["predicate_frame_id"]], note),
                [],
                spec["realization_id"],
            )
        for cell_row in cells:
            self.assertTrue(enumerate_valid_realisations(cell_row, frames))


class DeclarativeMethodTests(unittest.TestCase):
    def test_canonical_declaration_schema_prompt_and_python_agree(self) -> None:
        self.assertEqual(consistency_report()["status"], "PASS")
        grammar_cell(
            {
                "tense": "NA", "aspect": "none", "voice": "active",
                "polarity": "positive", "clause": "imperative", "modal": "none",
            }
        )
        with self.assertRaisesRegex(ValueError, "imperative_tense_modal"):
            grammar_cell(
                {
                    "tense": "present", "aspect": "none", "voice": "active",
                    "polarity": "positive", "clause": "imperative", "modal": "none",
                }
            )

    def test_reference_candidates_and_marked_obligations_regress(self) -> None:
        fixture = read_json(ROOT / "modules/kc_selection/fixtures/core.json")
        config = read_json(
            ROOT / "modules/kc_selection/configs/deterministic_v0.json"
        )
        result = kc_selection.evaluate_fixture(copy.deepcopy(fixture), config)
        self.assertEqual(
            result["selected_kc_ids"],
            [
                "KC_ASPECT_PERFECT", "KC_ASPECT_PROGRESSIVE", "KC_BE_PASSIVE",
                "KC_FINITE_PAST", "KC_FINITE_PRESENT", "KC_IMPERATIVE",
                "KC_NEGATION", "KC_QUESTION_GENERIC",
            ],
        )
        perfect_progressive = next(
            row["cell"]
            for row in fixture["canonical_cells"]
            if row["canonical_cell_id"] == "CELL_FIX_PERFECT_PROGRESSIVE"
        )
        self.assertEqual(
            kc_candidates.salient_facts(perfect_progressive),
            ["aspect:perfect", "aspect:progressive", "tense:present"],
        )

    def test_declarative_oracle_matches_previous_structural_semantics(self) -> None:
        fixture, _frames, bank = fixture_bank()
        params = read_json(
            ROOT / "modules/simulation/configs/structural_oracle_v0.json"
        )
        bank = folds.annotate_items(
            bank,
            {
                row["canonical_cell_id"]: row["split"]
                for row in fixture["cell_splits"]
            },
        )
        projected, feature_ids = simulation.project_oracle_items(
            bank, fixture["canonical_cells"], params
        )
        cells = {
            row["canonical_cell_id"]: row["cell"]
            for row in fixture["canonical_cells"]
        }

        def old_features(item: dict) -> list[str]:
            cell = cells[item["canonical_cell_id"]]
            operations = set(item["realization_evidence"]["operations"])
            site = item["realization_evidence"]["agreement_site"]
            frame_type = next(
                tag.removeprefix("frame_type:")
                for tag in item["realization_evidence"]["coverage_tags"]
                if tag.startswith("frame_type:")
            )
            active = {
                "ORACLE_FINITE_FORM": cell["tense"] in {"present", "past"},
                "ORACLE_FINITE_AGREEMENT": (
                    site == "be"
                    or (cell["tense"] == "present" and site in {"main_verb", "do", "have"})
                    or (frame_type == "copular" and cell["tense"] == "past")
                ),
                "ORACLE_PERFECT_DEPENDENCY": cell["aspect"] in {"perfect", "perfect_progressive"},
                "ORACLE_PROGRESSIVE_DEPENDENCY": cell["aspect"] in {"progressive", "perfect_progressive"},
                "ORACLE_PASSIVE_DEPENDENCY": cell["voice"] == "passive",
                "ORACLE_NEGATION": cell["polarity"] == "negative",
                "ORACLE_OPERATOR_INVERSION": "operator_inversion" in operations,
                "ORACLE_DO_SUPPORT": bool({"do_support", "do_support_negation"} & operations),
                "ORACLE_CENTRAL_MODAL": cell["modal"] != "none",
                "ORACLE_IMPERATIVE": cell["clause"] == "imperative",
            }
            return [feature for feature in feature_ids if active[feature]]

        self.assertEqual(
            {row["item_id"]: row["oracle_feature_ids"] for row in projected},
            {row["item_id"]: old_features(row) for row in bank},
        )


class ReliabilityAndSafetyTests(unittest.TestCase):
    def test_normalisation_reliability_surfaces_inventory_change(self) -> None:
        past = {
            "tense": "past", "aspect": "none", "voice": "active",
            "polarity": "positive", "clause": "declarative", "modal": "none",
        }
        partial = {**past, "tense": ["present", "past"]}
        units = [
            {"unit_id": "U1", "egp_id": "E", "duplicate_of": None},
            {"unit_id": "U2", "egp_id": "E", "duplicate_of": "U1"},
        ]
        by_unit = {
            "U1": {"output": {"egp_id": "E", "result": "complete", "cells": [past]}, "phase2": None},
            "U2": {"output": {"egp_id": "E", "result": "partial", "cells": [partial]}, "phase2": {}},
        }
        report, comparisons = analyse_repeated_normalisations(units, by_unit)
        self.assertEqual(report["repeated_pairs"], 1)
        self.assertEqual(report["exact_cell_set"]["agreements"], 0)
        self.assertEqual(report["dimension_wise"]["tense"]["agreements"], 0)
        self.assertEqual(report["complete_vs_partial_disagreements"]["count"], 1)
        self.assertEqual(report["phase2_routing"]["agreements"], 0)
        self.assertTrue(comparisons[0]["affects_downstream_canonical_inventory"])
        self.assertTrue(comparisons[0]["alternate_substitution_removed_cell_ids"])

    def test_item_diagnostic_disagreement_and_acceptance_effect_are_reported(self) -> None:
        acceptance = {"natural": True, "unsupported_construction": False}
        units = [
            {"validation_unit_id": "V1", "item_id": "I1", "duplicate_of": None},
            {"validation_unit_id": "V2", "item_id": "I1", "duplicate_of": "V1"},
        ]
        diagnostics = [
            {"validation_unit_id": "V1", "result": {"natural": True, "unsupported_construction": False}},
            {"validation_unit_id": "V2", "result": {"natural": False, "unsupported_construction": False}},
        ]
        report, comparisons = analyse_repeated_diagnostics(units, diagnostics, acceptance)
        self.assertEqual(report["model_check_role"], "acceptance_gate")
        self.assertEqual(report["item_ids_with_disagreement"], ["I1"])
        self.assertEqual(report["acceptance_sensitive_disagreements"]["count"], 1)
        self.assertTrue(comparisons[0]["could_change_final_acceptance"])

    def test_source_sampler_is_deterministic_and_auditable(self) -> None:
        records = [
            {"egp_id": "B", "supercategory": "VERBS", "level": "B2"},
            {"egp_id": "A", "supercategory": "VERBS", "level": "B1"},
            {"egp_id": "C", "supercategory": "NOUNS", "level": "B1"},
        ]
        design = {
            "design_id": "TEST",
            "allowed": {"supercategory": ["VERBS"]},
            "ordering": ["egp_id"],
            "strata": [{"stratum_id": "verbs", "match": {}, "quota": 1, "minimum": 1}],
        }
        first = sample_records(copy.deepcopy(records), design)
        second = sample_records(list(reversed(records)), design)
        self.assertEqual(first, second)
        self.assertEqual([row["egp_id"] for row in first[0]], ["A"])
        self.assertEqual(first[2]["eligible_after_scope_filters"], 2)

    def test_canonical_stage_writes_explicit_attrition_audit(self) -> None:
        complete = {
            "tense": "past", "aspect": "none", "voice": "active",
            "polarity": "positive", "clause": "declarative", "modal": "none",
        }
        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary)
            (run / "normalisation").mkdir()
            write_jsonl(
                run / "normalisation/final_mappings.jsonl",
                [
                    {"egp_id": "A", "result": "complete", "cells": [complete], "note": None},
                    {"egp_id": "B", "result": "partial", "cells": [], "note": "uncertain"},
                ],
            )
            canonical.run(run, {})
            audit = read_json(run / "canonical/audit.json")
            self.assertEqual(audit["source_descriptors"], 2)
            self.assertEqual(audit["normalisation_result_classes"]["partial"], 1)
            self.assertEqual(audit["contributing_descriptor_ids"], ["A"])
            self.assertEqual(audit["canonical_cell_count"], 1)
            self.assertFalse(audit["partial_mappings_contribute_exact_cells"])

    def test_reuse_guard_hashes_nested_module_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            family = root / "family.json"
            config = root / "config.json"
            write_json(family, {"hypothesis": "A"})
            write_json(config, {"candidate_family": str(family)})
            settings = {"items": {"bank_config": str(config)}}
            parent = root / "parent"
            parent.mkdir()
            write_json(
                parent / "metadata.json",
                {"stage_input_signatures": stage_input_signatures(settings)},
            )
            write_json(family, {"hypothesis": "B"})
            with self.assertRaisesRegex(RuntimeError, "refusing unsafe --from reuse"):
                validate_reuse(parent, settings, ["items"])


if __name__ == "__main__":
    unittest.main()
