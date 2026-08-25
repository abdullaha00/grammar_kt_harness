from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from grammar_kt.config import load_experiment
from grammar_kt.grammar import canonical, normalisation, source
from grammar_kt.grammar.normalisation_reliability import analyse_repeated_normalisations
from grammar_kt.grammar.normalisation_validation import (
    validate_mapping,
    validate_phase2_transition,
)
from grammar_kt.grammar.sampling import sample_records
from grammar_kt.io import ROOT, read_json, read_jsonl, sha256_file, write_json, write_jsonl
from grammar_kt.runner import PIPELINE, STAGE_NAMES, stage_input_signatures, validate_reuse

from .helpers import PAST_NEGATIVE


PAST_POSITIVE = {**PAST_NEGATIVE, "polarity": "positive"}


class SourceAndNormalisationTests(unittest.TestCase):
    def test_source_hash_selection_and_phase1_field_restriction(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            snapshot = root / "source.jsonl"
            record = {
                "egp_id": "E1",
                "supercategory": "VERBS",
                "subcategory": "past",
                "guideword": "PAST NEGATIVE",
                "can_do": "Can use a negative past form.",
                "examples": ["SECRET EXAMPLE MUST NOT REACH PHASE 1"],
            }
            write_jsonl(snapshot, [record], sort_keys=False)
            (root / "ids.txt").write_text("E1\n", encoding="utf-8")
            write_jsonl(root / "metadata.jsonl", [{"egp_id": "E1"}])
            write_jsonl(
                root / "units.jsonl",
                [{"unit_id": "U1", "egp_id": "E1", "duplicate_of": None}],
            )
            arguments = {
                "expected_sha256": sha256_file(snapshot),
                "expected_record_count": 1,
                "sample_ids_path": root / "ids.txt",
                "expected_descriptor_count": 1,
                "sample_metadata_path": root / "metadata.jsonl",
                "annotation_units_path": root / "units.jsonl",
            }
            selected, metadata, units = source.select_records(snapshot, **arguments)
            self.assertEqual(([row["egp_id"] for row in selected], len(metadata), len(units)), (["E1"], 1, 1))
            self.assertEqual(
                set(source.phase1_record(record)),
                {"egp_id", "supercategory", "subcategory", "guideword", "can_do"},
            )
            with self.assertRaisesRegex(RuntimeError, "SHA-256"):
                source.select_records(snapshot, **{**arguments, "expected_sha256": "0" * 64})

    def test_phase1_prompt_excludes_examples_and_retains_raw_evidence(self) -> None:
        record = {
            **read_jsonl(ROOT / "modules/grammar/source/fixtures/core.jsonl")[0],
            "examples": ["SECRET EXAMPLE MUST NOT REACH PHASE 1"],
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            response = root / "response.json"
            write_json(
                response,
                {"egp_id": record["egp_id"], "result": "complete", "cells": [PAST_NEGATIVE], "note": None},
            )
            result = normalisation.normalise_one(
                record,
                phase1_template=(ROOT / "modules/grammar/normalisation/prompts/phase1.txt").read_text(),
                phase2_template=(ROOT / "modules/grammar/normalisation/prompts/phase2.txt").read_text(),
                backend_config={"kind": "fixture_file", "response_file": str(response)},
                max_attempts=1,
                output=root / "normalisation",
                phase1_only=True,
            )
            attempt = root / "normalisation/units" / record["egp_id"] / "phase1/attempt-01"
            prompt = (attempt / "rendered_prompt.txt").read_text(encoding="utf-8")
            self.assertNotIn("SECRET EXAMPLE", prompt)
            self.assertEqual(
                set(read_json(attempt / "input.json")["record"]),
                set(normalisation.PHASE1_FIELDS),
            )
            self.assertEqual(read_json(attempt / "parsed_output.json"), result["phase1"])
            self.assertTrue((attempt / "raw_output.txt").is_file())

    def test_phase2_changes_only_declared_partial_dimensions(self) -> None:
        partial_cell = {**PAST_NEGATIVE, "tense": ["present", "past"]}
        first = {
            "egp_id": "E",
            "result": "partial",
            "cells": [partial_cell],
            "note": "phase2 eligible: tense",
        }
        refined = {
            "egp_id": "E",
            "result": "complete",
            "cells": [{**partial_cell, "tense": "past"}],
            "note": first["note"],
        }
        self.assertEqual(validate_mapping(first, "E", phase=1), [])
        self.assertEqual(validate_mapping(refined, "E", phase=2), [])
        self.assertEqual(validate_phase2_transition(first, refined), [])
        changed_aspect = copy.deepcopy(refined)
        changed_aspect["cells"][0]["aspect"] = "perfect"
        self.assertTrue(validate_phase2_transition(first, changed_aspect))

    def test_zero_cell_unresolved_never_routes_to_phase2(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            response = root / "response.json"
            write_json(
                response,
                {"egp_id": "E", "result": "unresolved", "cells": [], "note": "insufficient evidence"},
            )
            result = normalisation.normalise_one(
                {
                    "egp_id": "E", "supercategory": "VERBS", "subcategory": "",
                    "guideword": "", "can_do": "", "examples": ["example"],
                },
                phase1_template=(ROOT / "modules/grammar/normalisation/prompts/phase1.txt").read_text(),
                phase2_template=(ROOT / "modules/grammar/normalisation/prompts/phase2.txt").read_text(),
                backend_config={"kind": "fixture_file", "response_file": str(response)},
                max_attempts=1,
                output=root / "normalisation",
            )
            self.assertIsNone(result["phase2"])
            self.assertFalse((root / "normalisation/units/E/phase2").exists())

    def test_repeated_normalisation_reports_inventory_change(self) -> None:
        units = [
            {"unit_id": "U1", "egp_id": "E", "duplicate_of": None},
            {"unit_id": "U2", "egp_id": "E", "duplicate_of": "U1"},
        ]
        by_unit = {
            "U1": {"output": {"result": "complete", "cells": [PAST_POSITIVE]}, "phase2": None},
            "U2": {"output": {"result": "complete", "cells": [PAST_NEGATIVE]}, "phase2": None},
        }
        report, comparisons = analyse_repeated_normalisations(units, by_unit)
        self.assertEqual(report["repeated_pairs"], 1)
        self.assertEqual(report["canonical_contribution"]["different"], 1)
        self.assertTrue(comparisons[0]["affects_downstream_canonical_inventory"])

    def test_source_sampling_is_deterministic_and_auditable(self) -> None:
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


class CanonicalAndConfigurationTests(unittest.TestCase):
    def test_canonical_stage_writes_explicit_attrition_audit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary)
            (run / "normalisation").mkdir()
            write_jsonl(
                run / "normalisation/final_mappings.jsonl",
                [
                    {"egp_id": "A", "result": "complete", "cells": [PAST_POSITIVE], "note": None},
                    {"egp_id": "B", "result": "partial", "cells": [], "note": "uncertain"},
                ],
            )
            canonical.run(run, {})
            audit = read_json(run / "canonical/audit.json")
            self.assertEqual(audit["normalisation_result_classes"]["partial"], 1)
            self.assertEqual(audit["contributing_descriptor_ids"], ["A"])
            self.assertFalse(audit["partial_mappings_contribute_exact_cells"])

    def test_pipeline_and_dialogue_config_are_minimal_interventions(self) -> None:
        self.assertEqual(
            STAGE_NAMES,
            [
                "source", "normalisation", "canonical", "measurement", "generation",
                "knowledge_selection", "knowledge", "qmatrix", "simulation", "kt",
            ],
        )
        self.assertEqual([name for name, _ in PIPELINE], STAGE_NAMES)
        base, _ = load_experiment("base")
        dialogue, parent = load_experiment("dialogue")
        self.assertEqual(parent, "base")
        self.assertEqual(
            dialogue["generation"]["generator"],
            "modules/generation/generators/llm_dialogue_v0.yaml",
        )
        self.assertEqual(
            {key: value for key, value in base.items() if key not in {"experiment", "generation"}},
            {key: value for key, value in dialogue.items() if key not in {"experiment", "generation"}},
        )

    def test_reference_fold_is_external_and_exact(self) -> None:
        fold = read_json(ROOT / "modules/folds/reference_v0.json")
        groups = [
            set(fold["development_cell_ids"]),
            set(fold["compositional_holdout_cell_ids"]),
            set(fold["novel_feature_holdout_cell_ids"]),
        ]
        self.assertTrue(fold["require_exact_inventory"])
        self.assertFalse(groups[0] & groups[1] or groups[0] & groups[2] or groups[1] & groups[2])
        self.assertEqual(len(set().union(*groups)), 24)

    def test_reuse_guard_hashes_nested_generation_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            backend = root / "backend.json"
            generator = root / "generator.json"
            write_json(backend, {"model": "A"})
            write_json(generator, {"backend_config": str(backend)})
            settings = {"generation": {"generator": str(generator)}}
            parent = root / "parent"
            parent.mkdir()
            write_json(
                parent / "metadata.json",
                {"stage_input_signatures": stage_input_signatures(settings)},
            )
            write_json(backend, {"model": "B"})
            with self.assertRaisesRegex(RuntimeError, "refusing unsafe --from reuse"):
                validate_reuse(parent, settings, ["generation"])


if __name__ == "__main__":
    unittest.main()
