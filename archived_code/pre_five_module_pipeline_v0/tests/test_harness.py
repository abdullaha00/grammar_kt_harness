from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

from grammar_kt import canonical, folds, items, kc, kc_candidates, kc_selection, kt, qmatrix, realisation, simulation, source
from grammar_kt.backend import invoke_model, save_model_result
from grammar_kt.config import load_experiment
from grammar_kt.io import read_json, read_jsonl, sha256_file, write_json, write_jsonl
from grammar_kt.normalisation import normalise_one
from grammar_kt.normalisation_validation import validate_mapping, validate_phase2_transition
from grammar_kt.records import (
    FORBIDDEN_BASE_EVENT_FIELDS,
    compositional_base_event,
    kc_opportunity,
    observable_base_event,
)
from grammar_kt.runner import PIPELINE, STAGE_NAMES, run_experiment, stage_input_signatures


CELL = {"tense": "past", "aspect": "none", "voice": "active", "polarity": "positive", "clause": "declarative", "modal": "none"}


def fixture_assignment(fixture: dict) -> dict[str, str]:
    return {row["canonical_cell_id"]: row["split"] for row in fixture["cell_splits"]}


def fixture_runtime_items(rows: list[dict], fixture: dict) -> list[dict]:
    return folds.annotate_items(rows, fixture_assignment(fixture))


class ExperimentTests(unittest.TestCase):
    def test_inheritance_changes_only_declared_component(self) -> None:
        base, _ = load_experiment("base")
        variant, parent = load_experiment("kc_full_cell")
        self.assertEqual(parent, "base")
        self.assertEqual(variant["kc_selection"]["policy"], "modules/kc/policies/full_cell.json")
        self.assertEqual(set(base) - {"experiment", "kc_selection"}, set(variant) - {"experiment", "kc_selection"})
        for stage in set(base) - {"experiment", "kc_selection"}:
            self.assertEqual(base[stage], variant[stage])
        self.assertEqual(variant["kc"], base["kc"])

    def test_development_frozen_full_cell_is_an_explicit_control(self) -> None:
        settings, parent = load_experiment("kc_full_cell_dev_frozen")
        self.assertEqual(parent, "base")
        self.assertEqual(settings["kc_selection"]["mode"], "development_frozen_full_cell")
        self.assertEqual(settings["items"], load_experiment("base")[0]["items"])

    def test_development_frozen_factorized_is_an_explicit_inductive_control(self) -> None:
        settings, parent = load_experiment("kc_factorized_dev_frozen")
        self.assertEqual(parent, "base")
        self.assertEqual(settings["kc_selection"]["mode"], "development_frozen_factorized")
        self.assertEqual(
            settings["kc_selection"]["policy"], "modules/kc/policies/factorized.json"
        )

    def test_experiments_are_loaded_only_by_short_name(self) -> None:
        with self.assertRaisesRegex(ValueError, "short name"):
            load_experiment("experiments/base.yaml")

    def test_pipeline_order_is_defined_once_without_numbered_modules(self) -> None:
        self.assertEqual(STAGE_NAMES, ["source", "normalisation", "canonical", "realisation", "items", "simulation", "kc_selection", "kc", "qmatrix", "kt"])
        self.assertEqual([name for name, _run in PIPELINE], STAGE_NAMES)
        self.assertFalse(list((ROOT / "modules").glob("stage_*")), "legacy numbered modules remain")

    def test_baseline_declares_accepted_design_counts(self) -> None:
        settings, _ = load_experiment("base")
        expected = read_json(ROOT / "reference/current/expected_counts.json")
        parameters = read_json(ROOT / settings["simulation"]["parameters"])
        self.assertEqual(settings["source"]["selected_descriptors"], expected["unique_source_descriptors"])
        self.assertEqual(settings["kc"]["policy"], "modules/kc/policies/factorized.json")
        self.assertEqual(settings["kc_selection"]["policy"], "modules/kc/policies/factorized.json")
        self.assertEqual(parameters["learners_per_profile"] * len(parameters["profiles"]), expected["learners"])
        self.assertEqual(expected["accepted_items"] * parameters["item_passes_per_learner"], expected["events_per_learner"])
        self.assertNotIn("events_per_learner", settings["simulation"])

    def test_fold_explicitly_partitions_the_24_cell_inventory(self) -> None:
        split = read_json(ROOT / "modules/folds/reference_v0.json")
        groups = [
            set(split["development_cell_ids"]),
            set(split["compositional_holdout_cell_ids"]),
            set(split["novel_feature_holdout_cell_ids"]),
        ]
        self.assertTrue(split["require_exact_inventory"])
        self.assertFalse(groups[0] & groups[1] or groups[0] & groups[2] or groups[1] & groups[2])
        self.assertEqual(len(set().union(*groups)), 24)

    def test_from_stage_reuse_is_explicit_and_records_parent(self) -> None:
        resolution = load_experiment("kc_full_cell")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            parent = root / "base"
            for stage in STAGE_NAMES[:STAGE_NAMES.index("kc_selection")]:
                (parent / stage).mkdir(parents=True)
                (parent / stage / "marker.txt").write_text(stage, encoding="utf-8")
            write_json(
                parent / "metadata.json",
                {"stage_input_signatures": stage_input_signatures(resolution[0])},
            )

            def fake(stage: str):
                def execute(run: Path, _config: dict) -> dict:
                    (run / stage).mkdir()
                    return {"stage": stage}
                return execute

            replacement_pipeline = [(stage, fake(stage)) for stage in STAGE_NAMES]
            with patch("grammar_kt.runner.load_experiment", return_value=resolution), patch("grammar_kt.runner.PIPELINE", replacement_pipeline):
                output = run_experiment("kc_full_cell", from_stage="kc_selection", runs_root=root)
            metadata = read_json(output / "metadata.json")
            self.assertEqual(metadata["reused_from"]["run"], "base")
            self.assertEqual(metadata["stages"]["realisation"]["status"], "reused")
            self.assertEqual(metadata["stages"]["items"]["status"], "reused")
            self.assertEqual(metadata["stages"]["simulation"]["status"], "reused")
            self.assertEqual(metadata["stages"]["kc_selection"]["status"], "executed")

    def test_full_fixture_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_file = root / "source.jsonl"
            write_jsonl(
                source_file,
                [{"egp_id": "E", "supercategory": "VERBS", "subcategory": "past", "guideword": "PAST SIMPLE", "can_do": "Can use past simple.", "examples": []}],
                sort_keys=False,
            )
            (root / "ids.txt").write_text("E\n", encoding="utf-8")
            write_jsonl(root / "metadata.jsonl", [{"egp_id": "E"}])
            write_jsonl(root / "units.jsonl", [{"unit_id": "u1", "egp_id": "E", "duplicate_of": None}])
            normalisation_response = root / "normalisation_response.json"
            write_json(normalisation_response, {"egp_id": "E", "result": "complete", "cells": [CELL], "note": None})
            diagnostic_response = root / "diagnostic_response.json"
            write_json(diagnostic_response, {"structurally_plausible": True, "natural": True, "world_knowledge_required": False, "unsupported_construction": False, "answer_ambiguity_suspected": False, "note": "fixture"})
            normalisation_backend = root / "normalisation_backend.yaml"
            item_backend = root / "item_backend.yaml"
            fold_manifest = root / "fold.json"
            write_json(normalisation_backend, {"kind": "fixture_file", "response_file": str(normalisation_response)})
            write_json(item_backend, {"kind": "fixture_file", "response_file": str(diagnostic_response)})
            fixture_cell_id = canonical.build(
                [{"egp_id": "E", "result": "complete", "cells": [CELL], "note": None}]
            )[0][0]["canonical_cell_id"]
            write_json(
                fold_manifest,
                {
                    "fold_id": "FIXTURE_FOLD",
                    "require_exact_inventory": True,
                    "development_cell_ids": [fixture_cell_id],
                    "compositional_holdout_cell_ids": [],
                    "novel_feature_holdout_cell_ids": [],
                },
            )
            fold_setting = {"fold_manifest": str(fold_manifest)}
            fixture_settings = {
                "experiment": "fixture_e2e",
                "source": {
                    "path": str(source_file), "sha256": sha256_file(source_file),
                    "records": 1, "selected_descriptors": 1,
                    "sample_ids": str(root / "ids.txt"), "sample_metadata": str(root / "metadata.jsonl"),
                    "annotation_units": str(root / "units.jsonl"),
                },
                "normalisation": {
                    "phase1_prompt": "modules/normalisation/prompts/phase1.txt",
                    "phase2_prompt": "modules/normalisation/prompts/phase2.txt",
                    "backend_config": str(normalisation_backend), "workers": 1, "max_attempts": 1,
                },
                "canonical": {},
                "realisation": {},
                "kc_selection": {
                    **fold_setting,
                    "mode": "predefined",
                    "config": "modules/kc_selection/configs/deterministic_v0.json",
                    "policy": "modules/kc/policies/factorized.json",
                },
                "kc": {
                    **fold_setting,
                    "policy": "modules/kc/policies/factorized.json",
                    "selected_policy": "kc_selection/selected_policy.json",
                },
                "items": {
                    "family_prompt": "modules/items/families/controlled_transformation.txt",
                    "bank_config": "modules/items/configs/fixed_bank_v0.json",
                    "validation": {
                        "acceptance": "modules/items/validation/model_acceptance.json",
                        "backend_config": str(item_backend), "workers": 2, "max_attempts": 1,
                        "repeated_diagnostics": 2,
                    },
                },
                "simulation": {**fold_setting, "parameters": "modules/simulation/configs/default.json", "seed": 20260817},
                "kt": {**fold_setting, "parameters": "modules/kt/configs/default.json", "techniques": ["empirical", "bkt"]},
            }
            with patch("grammar_kt.runner.load_experiment", return_value=(fixture_settings, None)):
                run = run_experiment("fixture_e2e", runs_root=root / "runs")
            for artifact in (
                "candidates.jsonl", "activations.jsonl", "diagnostics.jsonl",
                "selection_trace.jsonl", "selected_policy.json", "evaluation.json",
            ):
                self.assertTrue((run / "kc_selection" / artifact).is_file(), artifact)
            self.assertEqual(len(read_jsonl(run / "items/validation/accepted_items.jsonl")), 3)
            self.assertEqual(read_json(run / "qmatrix/audit.json")["status"], "PASS")
            self.assertEqual(read_json(run / "simulation/audit.json")["status"], "PASS")
            self.assertFalse(read_json(run / "kt/metrics.json")["oracle_used"])
            validation = subprocess.run(
                [sys.executable, "scripts/validate.py", str(run)],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(
                validation.returncode, 0, validation.stdout + validation.stderr
            )


class NormalisationTests(unittest.TestCase):
    def test_phase2_may_change_only_eligible_dimension(self) -> None:
        cell = {"tense": ["present", "past"], "aspect": "none", "voice": "active", "polarity": "positive", "clause": "declarative", "modal": "none"}
        first = {"egp_id": "E", "result": "partial", "cells": [cell], "note": "phase2 eligible: tense"}
        refined = {"egp_id": "E", "result": "complete", "cells": [{**cell, "tense": "present"}], "note": first["note"]}
        self.assertEqual(validate_mapping(first, "E", phase=1), [])
        self.assertEqual(validate_mapping(refined, "E", phase=2), [])
        self.assertEqual(validate_phase2_transition(first, refined), [])
        changed = {**refined, "cells": [{**refined["cells"][0], "aspect": "perfect"}]}
        self.assertTrue(validate_phase2_transition(first, changed))

    def test_prompt_is_rendered_from_selected_files(self) -> None:
        settings, _ = load_experiment("base")
        settings = settings["normalisation"]
        record = read_jsonl(ROOT / "modules/normalisation/fixtures/core.jsonl")[0]
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            response = output / "response.json"
            write_json(
                response,
                {"egp_id": record["egp_id"], "result": "complete", "cells": [CELL], "note": None},
            )
            normalise_one(
                record,
                phase1_template=(ROOT / settings["phase1_prompt"]).read_text(encoding="utf-8"),
                phase2_template=(ROOT / settings["phase2_prompt"]).read_text(encoding="utf-8"),
                backend_config={"kind": "fixture_file", "response_file": str(response)},
                max_attempts=1,
                output=output,
                phase1_only=True,
            )
            prompt = (
                output / "units" / record["egp_id"] / "phase1" / "attempt-01" / "rendered_prompt.txt"
            ).read_text(encoding="utf-8")
            self.assertIn(record["egp_id"], prompt)
            self.assertIn("tense", prompt)
            self.assertNotIn("{{record}}", prompt)

    def test_fixture_backend_retains_exact_evidence_without_hash_graph(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            response = root / "response.json"
            response.write_text('{"ok":true}\n', encoding="utf-8")
            schema = root / "schema.json"
            schema.write_text('{"type":"object"}\n', encoding="utf-8")
            instructions = root / "instructions.md"
            instructions.write_text("instructions\n", encoding="utf-8")
            unit = root / "unit"
            write_json(unit / "input.json", {"id": "one"})
            raw_path, returncode = invoke_model(prompt="EXACT PROMPT\n", output_schema=schema, instructions=instructions, unit_dir=unit, backend_config={"kind": "fixture_file", "response_file": str(response)})
            self.assertEqual(returncode, 0)
            save_model_result(unit, json.loads(raw_path.read_text()), [])
            self.assertEqual((unit / "rendered_prompt.txt").read_text(), "EXACT PROMPT\n")
            for name in ("input.json", "invocation.json", "raw_output.txt", "parsed_output.json", "validation.json"):
                self.assertTrue((unit / name).is_file())
            self.assertNotIn("prompt_sha256", read_json(unit / "invocation.json"))

    def test_zero_cell_unresolved_does_not_route_to_phase2(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            response = root / "unresolved.json"
            write_json(response, {"egp_id": "E", "result": "unresolved", "cells": [], "note": "insufficient source evidence"})
            output = root / "normalisation"
            output.mkdir()
            prompt_dir = ROOT / "modules" / "normalisation" / "prompts"
            result = normalise_one(
                {"egp_id": "E", "supercategory": "VERBS", "subcategory": "", "guideword": "", "can_do": "", "examples": []},
                phase1_template=(prompt_dir / "phase1.txt").read_text(encoding="utf-8"),
                phase2_template=(prompt_dir / "phase2.txt").read_text(encoding="utf-8"),
                backend_config={"kind": "fixture_file", "response_file": str(response)},
                max_attempts=1,
                unit_id="u1",
                output=output,
            )
            self.assertIsNone(result["phase2"])
            self.assertFalse((output / "units" / "u1" / "phase2").exists())


class SourceTests(unittest.TestCase):
    def source_settings(self, root: Path) -> dict:
        source_file = root / "source.jsonl"
        write_jsonl(source_file, [{"egp_id": "E1", "guideword": "PRESENT"}], sort_keys=False)
        (root / "ids.txt").write_text("E1\n", encoding="utf-8")
        write_jsonl(root / "metadata.jsonl", [{"egp_id": "E1"}])
        write_jsonl(root / "units.jsonl", [{"unit_id": "u1", "egp_id": "E1", "duplicate_of": None}])
        return {
            "path": str(source_file),
            "sha256": sha256_file(source_file),
            "records": 1,
            "selected_descriptors": 1,
            "sample_ids": str(root / "ids.txt"),
            "sample_metadata": str(root / "metadata.jsonl"),
            "annotation_units": str(root / "units.jsonl"),
        }

    def test_source_selection_and_hash_guard(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            settings = self.source_settings(Path(temporary))
            selected, metadata, units = source.select_records(
                settings["path"],
                expected_sha256=settings["sha256"],
                expected_record_count=settings["records"],
                sample_ids_path=settings["sample_ids"],
                expected_descriptor_count=settings["selected_descriptors"],
                sample_metadata_path=settings["sample_metadata"],
                annotation_units_path=settings["annotation_units"],
            )
            self.assertEqual(([row["egp_id"] for row in selected], len(metadata), len(units)), (["E1"], 1, 1))
            with self.assertRaisesRegex(RuntimeError, "SHA-256"):
                source.select_records(
                    settings["path"],
                    expected_sha256="0" * 64,
                    expected_record_count=settings["records"],
                    sample_ids_path=settings["sample_ids"],
                    expected_descriptor_count=settings["selected_descriptors"],
                    sample_metadata_path=settings["sample_metadata"],
                    annotation_units_path=settings["annotation_units"],
                )


class ComponentTests(unittest.TestCase):
    def test_canonical_deduplicates_only_complete_cells(self) -> None:
        mappings = [
            {"egp_id": "A", "result": "complete", "cells": [CELL], "note": None},
            {"egp_id": "B", "result": "complete", "cells": [dict(CELL)], "note": None},
            {"egp_id": "C", "result": "partial", "cells": [{**CELL, "tense": ["past"]}], "note": "phase2 eligible: tense"},
        ]
        cells, edges = canonical.build(mappings)
        self.assertEqual((len(cells), len(edges)), (1, 2))

    def test_realisation_and_kc_policy_application(self) -> None:
        frames = {
            row["predicate_frame_id"]: row
            for row in read_jsonl(realisation.LEXICON)
        }
        for fixture in read_jsonl(ROOT / "modules/realisation/fixtures/core.jsonl"):
            cell, spec = fixture["cell"], fixture["spec"]
            frame = frames[spec["predicate_frame_id"]]
            errors = realisation.validate_spec(spec, cell, frame, fixture.get("source_note"))
            derivation = realisation.realise(spec, cell, frame) if not errors else None
            self.assertEqual(errors, [], fixture["fixture_label"])
            self.assertEqual(derivation["surface"], fixture["expected_surface"])
        opportunity = kc_opportunity(read_json(ROOT / "modules/kc/fixtures/perfect_progressive.json"))
        factorized = kc.apply_policy(
            kc.load_policy(ROOT / "modules/kc/policies/factorized.json"),
            opportunity,
        )
        interactions = kc.apply_policy(
            kc.load_policy(ROOT / "modules/kc/policies/factorized_plus_interactions.json"),
            opportunity,
        )
        self.assertEqual(factorized["activated_kcs"], ["KC_ASPECT_PERFECT", "KC_ASPECT_PROGRESSIVE", "KC_FINITE_PRESENT"])
        self.assertIn("KC_INT_PERFECT_PROGRESSIVE_CHAIN", interactions["activated_kcs"])

    def test_new_supported_policy_requires_no_python_change(self) -> None:
        opportunity = read_json(ROOT / "modules/kc/fixtures/perfect_progressive.json")
        with tempfile.TemporaryDirectory() as temporary:
            policy = Path(temporary) / "new_policy.json"
            policy.write_text(json.dumps({"policy_id": "TEST", "kind": "rules", "rules": [{"kc_id": "KC_TEST", "name": "test", "definition": "test", "activation_rule": {"cell": {"aspect": "perfect_progressive"}}, "required_conditions": [], "includes": [], "excludes": [], "realization_dependencies": [], "near_neighbours": [], "rationale": "test"}]}), encoding="utf-8")
            result = kc.apply_policy(kc.load_policy(policy), kc_opportunity(opportunity))
            self.assertEqual(result["activated_kcs"], ["KC_TEST"])

    def test_generic_run_one_cli(self) -> None:
        result = subprocess.run([sys.executable, "scripts/run_one.py", "kc", "--fixture", "perfect_progressive", "--policy", "factorized"], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("=== BEFORE ===", result.stdout)
        self.assertIn("KC_ASPECT_PERFECT", result.stdout)

    def test_structural_kc_selection_run_one_cli(self) -> None:
        result = subprocess.run(
            [sys.executable, "scripts/run_one.py", "kc_selection", "--fixture", "structural_selection"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("KC_ASPECT_PERFECT", result.stdout)
        self.assertIn('"selection_data_partition": "development"', result.stdout)

    def test_qmatrix_is_derived_from_item_level_frozen_projection(self) -> None:
        item = {"item_id": "ITEM_A", "canonical_cell_id": "CELL_A", "realization_spec": {"realization_id": "REAL_A"}, "source_descriptor_ids": ["E"], "generation_metadata": {"deterministic": True}}
        card = {"kc_id": "KC_A", "activation_rule": {"cell": {"tense": "past"}}}
        projection = {"item_id": "ITEM_A", "canonical_cell_id": "CELL_A", "realization_id": "REAL_A", "kc_ids": ["KC_A"]}
        columns, rows, edges, audit = qmatrix.build([item], [card], [projection])
        self.assertEqual((columns, rows, len(edges), audit["status"]), (["KC_A"], [("ITEM_A", [1])], 1, "PASS"))
        self.assertNotIn("edge_id", edges[0])

    def test_qmatrix_redundancy_is_diagnostic_not_failure(self) -> None:
        item = {"item_id": "ITEM_A", "canonical_cell_id": "CELL_A", "realization_spec": {"realization_id": "REAL_A"}, "source_descriptor_ids": ["E"], "generation_metadata": {"deterministic": True}}
        cards = [
            {"kc_id": "KC_A", "activation_rule": {"cell": {"tense": "past"}}},
            {"kc_id": "KC_B", "activation_rule": {"cell": {"tense": "past"}}},
        ]
        projection = {"item_id": "ITEM_A", "canonical_cell_id": "CELL_A", "realization_id": "REAL_A", "kc_ids": ["KC_A", "KC_B"]}
        _columns, _rows, _edges, audit = qmatrix.build([item], cards, [projection])
        self.assertEqual(audit["status"], "PASS")
        self.assertEqual(audit["scientific_diagnostics"]["identical_q_columns"], [["KC_A", "KC_B"]])

    def test_deterministic_item_answer(self) -> None:
        fixture = read_jsonl(ROOT / "modules/items/fixtures/core.jsonl")[0]
        result = items.evaluate_fixture(fixture)
        self.assertTrue(result["valid"])
        self.assertEqual(result["output"]["surface"], fixture["target_answer"])

    def test_item_opportunities_cover_cells_and_agreement_without_kcs(self) -> None:
        cell_row = {
            "canonical_cell_id": "CELL_PAST",
            "cell": CELL,
            "source_descriptor_ids": ["E"],
            "source_mapping_notes": {"E": None},
        }
        frames = {row["predicate_frame_id"]: row for row in read_jsonl(ROOT / "modules/realisation/lexicons/default.jsonl")}
        opportunities = items.build_item_opportunities(
            [cell_row],
            frames,
            read_json(ROOT / "modules/items/configs/fixed_bank_v0.json"),
        )
        template = (ROOT / "modules/items/families/controlled_transformation.txt").read_text(encoding="utf-8")
        generated = items.construct_items(opportunities, frames, template)
        self.assertEqual(len(generated), 3)
        self.assertEqual(
            {row["realization_spec"]["subject"]["text"] for row in generated},
            {"I", "the technician", "the technicians"},
        )
        self.assertFalse({key for row in generated for key in row if "kc" in key.lower()})

    def test_different_ontologies_share_bank_ids_hash_and_difficulty_but_change_q(self) -> None:
        fixture = read_json(ROOT / "modules/kc_selection/fixtures/core.json")
        frames = {
            row["predicate_frame_id"]: row
            for row in read_jsonl(ROOT / "modules/realisation/lexicons/default.jsonl")
        }
        opportunities = items.build_item_opportunities(
            fixture["canonical_cells"],
            frames,
            read_json(ROOT / "modules/items/configs/fixed_bank_v0.json"),
        )
        template = (ROOT / "modules/items/families/controlled_transformation.txt").read_text(encoding="utf-8")
        accepted_bank = fixture_runtime_items(
            items.construct_items(opportunities, frames, template), fixture
        )
        selected = kc_selection.evaluate_fixture(
            copy.deepcopy(fixture),
            read_json(ROOT / "modules/kc_selection/configs/deterministic_v0.json"),
        )["selected_policy"]
        factorized = kc.load_policy(ROOT / "modules/kc/policies/factorized.json")
        selected_bank = copy.deepcopy(accepted_bank)
        factorized_bank = copy.deepcopy(accepted_bank)

        selected_projection, selected_cards = kc.project_items(
            selected_bank, fixture["canonical_cells"], selected
        )
        factorized_projection, factorized_cards = kc.project_items(
            factorized_bank, fixture["canonical_cells"], factorized
        )
        _sc, selected_rows, selected_edges, selected_audit = qmatrix.build(
            selected_bank, selected_cards, selected_projection
        )
        _fc, factorized_rows, factorized_edges, factorized_audit = qmatrix.build(
            factorized_bank, factorized_cards, factorized_projection
        )

        self.assertEqual(selected_audit["status"], "PASS")
        self.assertEqual(factorized_audit["status"], "PASS")
        self.assertEqual(
            [items.item_bank_record(row) for row in selected_bank],
            [items.item_bank_record(row) for row in factorized_bank],
        )
        self.assertEqual(
            items.item_bank_fingerprint(selected_bank),
            items.item_bank_fingerprint(factorized_bank),
        )
        self.assertEqual(
            {
                row["item_id"]: simulation.difficulty(row["item_id"], -1.0, 1.0)
                for row in selected_bank
            },
            {
                row["item_id"]: simulation.difficulty(row["item_id"], -1.0, 1.0)
                for row in factorized_bank
            },
        )
        self.assertNotEqual(
            {(row["item_id"], row["kc_id"]) for row in selected_edges},
            {(row["item_id"], row["kc_id"]) for row in factorized_edges},
        )
        self.assertEqual(
            [item_id for item_id, _values in selected_rows],
            [item_id for item_id, _values in factorized_rows],
        )

    def test_item_level_projection_distinguishes_realisation_scope_operation(self) -> None:
        fixture = read_json(ROOT / "modules/kc_selection/fixtures/core.json")
        negative = next(
            row
            for row in fixture["canonical_cells"]
            if row["canonical_cell_id"] == "CELL_FIX_NEGATIVE"
        )
        frames = {
            row["predicate_frame_id"]: row
            for row in read_jsonl(ROOT / "modules/realisation/lexicons/default.jsonl")
        }
        opportunities = items.build_item_opportunities(
            [negative],
            frames,
            read_json(ROOT / "modules/items/configs/fixed_bank_v0.json"),
        )
        bank = folds.annotate_items(items.construct_items(
            opportunities,
            frames,
            (ROOT / "modules/items/families/controlled_transformation.txt").read_text(encoding="utf-8"),
        ), {"CELL_FIX_NEGATIVE": "development"})
        policy = kc.load_policy(ROOT / "modules/kc/policies/factorized_plus_interactions.json")
        projections, _cards = kc.project_items(bank, [negative], policy)
        lexical = next(row for row in projections if "do_support" in row["realization_operations"])
        copular = next(
            row
            for row in projections
            if "do_support" not in row["realization_operations"]
            and next(item for item in bank if item["item_id"] == row["item_id"])["realization_spec"]["predicate_frame_id"] == "FRAME_COPULAR_READY"
        )
        self.assertIn("KC_INT_DO_NEGATION", lexical["kc_ids"])
        self.assertNotIn("KC_INT_DO_NEGATION", copular["kc_ids"])
        self.assertEqual(lexical["canonical_cell_id"], copular["canonical_cell_id"])

    def test_simulation_observable_has_no_oracle_fields(self) -> None:
        settings, _ = load_experiment("base")
        settings = settings["simulation"]
        fixture_dir = ROOT / "modules/simulation/fixtures"
        fixture_items = folds.annotate_items(
            read_jsonl(fixture_dir / "accepted_items.jsonl"),
            {"CELL_0000000000000001": "development"},
        )
        parameters = read_json(settings["parameters"])
        parameters["seed"] = settings["seed"]
        oracle_feature_ids = ["ORACLE_FINITE_FORM"]
        oracle_by_item = {
            row["item_id"]: list(oracle_feature_ids) for row in fixture_items
        }
        event_count = len(fixture_items) * parameters["item_passes_per_learner"]
        train_end, validation_end = simulation.split_boundaries(
            event_count, parameters["train_fraction"], parameters["validation_fraction"]
        )
        observed, _oracle, _learners, _learner_oracle = simulation.simulate_records(
            parameters,
            {row["item_id"]: row for row in fixture_items},
            oracle_by_item,
            oracle_feature_ids,
            train_end,
            validation_end,
            target_learner="L0001",
        )
        for row in observed:
            self.assertFalse(FORBIDDEN_BASE_EVENT_FIELDS & set(row))
            observable_base_event(row)

    def test_six_ontologies_share_temporal_and_compositional_fixed_events(self) -> None:
        fixture = read_json(ROOT / "modules/kc_selection/fixtures/core.json")
        frames = {
            row["predicate_frame_id"]: row for row in read_jsonl(realisation.LEXICON)
        }
        opportunities = items.build_item_opportunities(
            fixture["canonical_cells"],
            frames,
            read_json(ROOT / "modules/items/configs/fixed_bank_v0.json"),
        )
        bank = fixture_runtime_items(items.construct_items(
            opportunities,
            frames,
            (ROOT / "modules/items/families/controlled_transformation.txt").read_text(
                encoding="utf-8"
            ),
        ), fixture)
        params = read_json(ROOT / "modules/simulation/configs/structural_oracle_v0.json")
        params.update(
            {
                "seed": 20260817,
                "learners_per_profile": 2,
                "profiles": {
                    "fixture": {
                        "beta_alpha": 2.0,
                        "beta_beta": 2.0,
                        "learning_rate": 0.05,
                    }
                },
            }
        )
        oracle_projection, oracle_feature_ids = simulation.project_oracle_items(
            bank, fixture["canonical_cells"], params
        )
        oracle_by_item = {
            row["item_id"]: row["oracle_feature_ids"] for row in oracle_projection
        }
        item_by_id = {row["item_id"]: row for row in bank}
        event_count = len(bank) * params["item_passes_per_learner"]
        train_end, validation_end = simulation.split_boundaries(
            event_count, params["train_fraction"], params["validation_fraction"]
        )

        selected = kc_selection.evaluate_fixture(
            copy.deepcopy(fixture),
            read_json(ROOT / "modules/kc_selection/configs/deterministic_v0.json"),
        )["selected_policy"]
        development_cells = [
            row
            for row in fixture["canonical_cells"]
            if next(
                split["split"]
                for split in fixture["cell_splits"]
                if split["canonical_cell_id"] == row["canonical_cell_id"]
            )
            == "development"
        ]
        development_items = [
            row
            for row in bank
            if row["canonical_split"] == "development"
        ]
        factorized_dev_frozen, _support = (
            kc_selection.development_frozen_factorized_policy(
                ROOT / "modules/kc/policies/factorized.json",
                development_cells,
                development_items,
            )
        )
        policies = {
            "SELECTED_STRUCTURAL": selected,
            "FACTORIZED_DEV_FROZEN": factorized_dev_frozen,
            "CURRENT_FACTORIZED": kc.load_policy(
                ROOT / "modules/kc/policies/factorized.json"
            ),
            "CURRENT_FACTORIZED_PLUS_INTERACTIONS": kc.load_policy(
                ROOT / "modules/kc/policies/factorized_plus_interactions.json"
            ),
            "FULL_CELL_DEV_FROZEN": kc_selection.development_frozen_full_cell_policy(
                development_cells
            ),
            "FULL_CELL_ALL_TRANSDUCTIVE": kc.load_policy(
                ROOT / "modules/kc/policies/full_cell.json"
            ),
        }

        fixed_hashes = {}
        fixed_rows = {}
        q_columns = {}
        q_edges = {}
        histories = {}
        uncovered_events = {}
        phase_d_hashes = {}
        phase_d_boundaries = {}
        phase_d_histories = {}
        for label, policy in policies.items():
            base_events, _oracle, _learners, _parameters = simulation.simulate_records(
                params,
                item_by_id,
                oracle_by_item,
                oracle_feature_ids,
                train_end,
                validation_end,
            )
            fixed_hashes[label] = simulation.event_stream_fingerprint(base_events)
            fixed_rows[label] = [
                (
                    row["event_id"],
                    row["learner_id"],
                    row["item_id"],
                    row["sequence_index"],
                    row["timestamp"],
                    row["item_difficulty"],
                    row["correct"],
                    row["dataset_split"],
                    row["canonical_split"],
                )
                for row in base_events
            ]
            item_projection, cards = kc.project_items(
                bank, fixture["canonical_cells"], policy
            )
            columns, _rows, edges, audit = qmatrix.build(bank, cards, item_projection)
            self.assertEqual(audit["status"], "PASS")
            projected = kt.project_interactions(base_events, item_projection)
            self.assertEqual(len(projected), len(base_events))
            for base, annotated in zip(base_events, projected, strict=True):
                self.assertEqual(
                    base,
                    {
                        key: value
                        for key, value in annotated.items()
                        if key not in {"kc_ids", "opportunity_indices"}
                    },
                )
            q_columns[label] = tuple(columns)
            q_edges[label] = frozenset((row["item_id"], row["kc_id"]) for row in edges)
            histories[label] = tuple(
                (row["event_id"], tuple(row["kc_ids"]), tuple(row["opportunity_indices"].items()))
                for row in projected
            )
            uncovered_events[label] = sum(not row["kc_ids"] for row in projected)
            phase_d = simulation.simulate_compositional_records(
                params,
                item_by_id,
                oracle_by_item,
                oracle_feature_ids,
            )
            probes = (
                phase_d["compositional_probe_events"]
                + phase_d["novel_feature_probe_events"]
            )
            phase_d_hashes[label] = simulation.event_stream_fingerprint(probes)
            phase_d_boundaries[label] = [
                (
                    row["event_id"],
                    row["learner_id"],
                    row["item_id"],
                    row["correct"],
                    row["item_difficulty"],
                    row["canonical_split"],
                )
                for row in probes
            ]
            acquisition_projection, probe_projection, _supported, _counts = (
                kt.project_compositional_interactions(
                    phase_d["acquisition_events"], probes, item_projection
                )
            )
            self.assertTrue(
                all(row["canonical_split"] == "development" for row in acquisition_projection)
            )
            phase_d_histories[label] = tuple(
                (
                    row["event_id"],
                    tuple(row["kc_ids"]),
                    tuple(row["opportunity_indices"].items()),
                    tuple(row["cold_kc_ids"]),
                )
                for row in probe_projection
            )

        self.assertEqual(len(set(fixed_hashes.values())), 1)
        self.assertEqual(len(set(phase_d_hashes.values())), 1)
        self.assertEqual(len({tuple(rows) for rows in fixed_rows.values()}), 1)
        self.assertEqual(len({tuple(rows) for rows in phase_d_boundaries.values()}), 1)
        self.assertEqual(items.item_bank_fingerprint(bank), items.item_bank_fingerprint(copy.deepcopy(bank)))
        self.assertNotEqual(q_columns["SELECTED_STRUCTURAL"], q_columns["CURRENT_FACTORIZED"])
        self.assertNotEqual(
            q_edges["CURRENT_FACTORIZED"],
            q_edges["CURRENT_FACTORIZED_PLUS_INTERACTIONS"],
        )
        self.assertNotEqual(
            histories["CURRENT_FACTORIZED"],
            histories["CURRENT_FACTORIZED_PLUS_INTERACTIONS"],
        )
        self.assertNotEqual(
            phase_d_histories["CURRENT_FACTORIZED"],
            phase_d_histories["CURRENT_FACTORIZED_PLUS_INTERACTIONS"],
        )
        self.assertGreater(
            uncovered_events["FULL_CELL_DEV_FROZEN"],
            uncovered_events["FULL_CELL_ALL_TRANSDUCTIVE"],
        )
        self.assertEqual(uncovered_events["FULL_CELL_ALL_TRANSDUCTIVE"], 0)

    def test_zero_kc_event_is_retained_with_empty_opportunity_history(self) -> None:
        base = {
            "event_id": "EVENT_L1_001",
            "learner_id": "L1",
            "item_id": "ITEM_UNCOVERED",
            "canonical_cell_id": "CELL_HELDOUT",
            "canonical_split": "compositional_holdout",
            "sequence_index": 1,
            "timestamp": "2026-01-01T00:01:00+00:00",
            "correct": 0,
            "item_difficulty": 0.25,
            "dataset_split": "test",
        }
        projected = kt.project_interactions(
            [base], [{"item_id": "ITEM_UNCOVERED", "kc_ids": []}]
        )
        self.assertEqual(len(projected), 1)
        self.assertEqual(projected[0]["kc_ids"], [])
        self.assertEqual(projected[0]["opportunity_indices"], {})
        self.assertEqual(
            kt.coverage_report(projected, [{"item_id": "ITEM_UNCOVERED", "kc_ids": []}])[
                "uncovered_events"
            ],
            1,
        )

    def test_phase_d_acquisition_and_oracle_probes_are_strictly_frozen(self) -> None:
        fixture = read_json(ROOT / "modules/kc_selection/fixtures/core.json")
        frames = {row["predicate_frame_id"]: row for row in read_jsonl(realisation.LEXICON)}
        opportunities = items.build_item_opportunities(
            fixture["canonical_cells"],
            frames,
            read_json(ROOT / "modules/items/configs/fixed_bank_v0.json"),
        )
        bank = fixture_runtime_items(items.construct_items(
            opportunities,
            frames,
            (ROOT / "modules/items/families/controlled_transformation.txt").read_text(
                encoding="utf-8"
            ),
        ), fixture)
        params = read_json(ROOT / "modules/simulation/configs/structural_oracle_v0.json")
        params.update(
            seed=20260817,
            learners_per_profile=2,
            profiles={
                "fixture": {
                    "beta_alpha": 2.0,
                    "beta_beta": 2.0,
                    "learning_rate": 0.05,
                }
            },
        )
        oracle_projection, feature_ids = simulation.project_oracle_items(
            bank, fixture["canonical_cells"], params
        )
        oracle_by_item = {
            row["item_id"]: row["oracle_feature_ids"] for row in oracle_projection
        }
        item_by_id = {row["item_id"]: row for row in bank}
        result = simulation.simulate_compositional_records(
            params, item_by_id, oracle_by_item, feature_ids
        )
        self.assertTrue(result["acquisition_events"])
        self.assertTrue(
            all(
                row["canonical_split"] == "development"
                and row["evaluation_role"] == "acquisition"
                for row in result["acquisition_events"]
            )
        )
        frozen = {
            row["learner_id"]: row["post_development_mastery"]
            for row in result["learner_frozen_oracle_state"]
        }
        for row in result["oracle_probe_evidence"]:
            self.assertFalse(row["oracle_update_applied"])
            self.assertEqual(
                row["frozen_post_development_mastery"],
                {
                    feature_id: frozen[row["learner_id"]][feature_id]
                    for feature_id in row["oracle_feature_ids"]
                },
            )
        reversed_result = simulation.simulate_compositional_records(
            params,
            dict(reversed(list(item_by_id.items()))),
            dict(reversed(list(oracle_by_item.items()))),
            feature_ids,
        )
        self.assertEqual(
            result["compositional_probe_events"],
            reversed_result["compositional_probe_events"],
        )
        self.assertEqual(
            result["oracle_probe_evidence"], reversed_result["oracle_probe_evidence"]
        )
        leaked = {**result["compositional_probe_events"][0], "pre_mastery": {}}
        with self.assertRaisesRegex(ValueError, "leakage"):
            compositional_base_event(leaked)

    def test_phase_d_candidate_probe_state_is_frozen_and_labels_cold_or_uncovered(self) -> None:
        fixture = read_json(ROOT / "modules/kc_selection/fixtures/core.json")
        frames = {row["predicate_frame_id"]: row for row in read_jsonl(realisation.LEXICON)}
        bank = items.construct_items(
            items.build_item_opportunities(
                fixture["canonical_cells"],
                frames,
                read_json(ROOT / "modules/items/configs/fixed_bank_v0.json"),
            ),
            frames,
            (ROOT / "modules/items/families/controlled_transformation.txt").read_text(
                encoding="utf-8"
            ),
        )
        bank = fixture_runtime_items(bank, fixture)
        params = read_json(ROOT / "modules/simulation/configs/structural_oracle_v0.json")
        params.update(
            seed=20260817,
            learners_per_profile=1,
            profiles={
                "fixture": {
                    "beta_alpha": 2.0,
                    "beta_beta": 2.0,
                    "learning_rate": 0.05,
                }
            },
        )
        oracle_projection, feature_ids = simulation.project_oracle_items(
            bank, fixture["canonical_cells"], params
        )
        generated = simulation.simulate_compositional_records(
            params,
            {row["item_id"]: row for row in bank},
            {row["item_id"]: row["oracle_feature_ids"] for row in oracle_projection},
            feature_ids,
        )
        probes = generated["compositional_probe_events"] + generated[
            "novel_feature_probe_events"
        ]
        factorized_projection, _cards = kc.project_items(
            bank,
            fixture["canonical_cells"],
            kc.load_policy(ROOT / "modules/kc/policies/factorized.json"),
        )
        acquisition, projected, supported, _counts = kt.project_compositional_interactions(
            generated["acquisition_events"], probes, factorized_projection
        )
        novel = [row for row in projected if row["canonical_split"] == "novel_feature_holdout"]
        self.assertTrue(novel)
        self.assertTrue(all(row["covered"] and row["cold_kc_ids"] for row in novel))
        self.assertTrue(all(not row["fully_development_supported"] for row in novel))
        _acq_reversed, projected_reversed, _supported, _counts = (
            kt.project_compositional_interactions(
                generated["acquisition_events"], list(reversed(probes)), factorized_projection
            )
        )
        self.assertEqual(
            {row["event_id"]: row for row in projected},
            {row["event_id"]: row for row in projected_reversed},
        )
        states = kt.frozen_development_statistics(acquisition)
        kc_ids = sorted({kc_id for row in factorized_projection for kc_id in row["kc_ids"]})
        _features, _targets, predictions, _fallback = kt.frozen_probe_features(
            projected, kc_ids, states, alpha=1.0, beta=1.0, cold_prior=0.5
        )
        changed = copy.deepcopy(projected)
        changed[0]["correct"] = 1 - changed[0]["correct"]
        _changed_features, _changed_targets, changed_predictions, _changed_fallback = (
            kt.frozen_probe_features(
                changed, kc_ids, states, alpha=1.0, beta=1.0, cold_prior=0.5
            )
        )
        self.assertEqual(predictions.tolist(), changed_predictions.tolist())
        selected = kc_selection.evaluate_fixture(
            copy.deepcopy(fixture),
            read_json(ROOT / "modules/kc_selection/configs/deterministic_v0.json"),
        )["selected_policy"]
        selected_projection, _cards = kc.project_items(
            bank, fixture["canonical_cells"], selected
        )
        _acquisition, selected_probes, _supported, _counts = (
            kt.project_compositional_interactions(
                generated["acquisition_events"], probes, selected_projection
            )
        )
        selected_novel = [
            row
            for row in selected_probes
            if row["canonical_split"] == "novel_feature_holdout"
        ]
        self.assertTrue(all(not row["covered"] and row["kc_ids"] == [] for row in selected_novel))

    def test_phase_d_bootstrap_is_paired_at_learner_level_and_deterministic(self) -> None:
        left = [
            {
                "event_id": f"E{learner}{item}",
                "learner_id": learner,
                "item_id": item,
                "probe_type": "compositional_holdout",
                "correct": correct,
                "empirical": probability,
            }
            for learner, values in {
                "L1": (("I1", 1, 0.8), ("I2", 0, 0.3)),
                "L2": (("I1", 0, 0.2), ("I2", 1, 0.7)),
            }.items()
            for item, correct, probability in values
        ]
        right = [{**row, "empirical": 0.5} for row in left]
        first = kt.learner_bootstrap_log_loss_difference(
            left,
            right,
            technique="empirical",
            probe_type="compositional_holdout",
            repetitions=100,
            seed=17,
        )
        second = kt.learner_bootstrap_log_loss_difference(
            left,
            right,
            technique="empirical",
            probe_type="compositional_holdout",
            repetitions=100,
            seed=17,
        )
        self.assertEqual(first, second)
        self.assertEqual(first["learners"], 2)
        self.assertEqual(first["events"], 4)
        self.assertEqual(first["sampling_unit"].split(";")[0], "learner")
        self.assertLess(first["mean_difference"], 0)

    def test_simulation_split_boundaries_scale_with_item_count(self) -> None:
        self.assertEqual(simulation.split_boundaries(90, 0.6, 0.2), (54, 72))
        self.assertEqual(simulation.split_boundaries(21, 0.6, 0.2), (12, 16))

    def test_kt_rejects_oracle_fields(self) -> None:
        row = {
            "event_id": "EVENT_1", "learner_id": "L1", "item_id": "I1",
            "canonical_cell_id": "CELL_1", "canonical_split": "development",
            "sequence_index": 1, "timestamp": "2026-01-01T00:00:00+00:00",
            "dataset_split": "train", "item_difficulty": 0.0, "pre_mastery": {"K1": 0.5},
            "correct": 1,
        }
        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary)
            (run / "simulation").mkdir()
            write_jsonl(run / "simulation/base_events.jsonl", [row])
            (run / "kc").mkdir()
            write_jsonl(
                run / "kc/item_kc_projection.jsonl",
                [{"item_id": "I1", "kc_ids": ["K1"]}],
            )
            with self.assertRaisesRegex(ValueError, "leakage"):
                settings, _ = load_experiment("base")
                kt.run(run, settings["kt"])

    def test_small_fixture_pipeline_through_kt(self) -> None:
        settings, _ = load_experiment("base")
        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary)
            write_json(run / "experiment.yaml", {})
            write_json(run / "metadata.json", {})
            (run / "source").mkdir()
            write_jsonl(run / "source/source_subset.jsonl", [{"egp_id": "FIX"}])
            (run / "normalisation").mkdir()
            write_jsonl(run / "normalisation/final_mappings.jsonl", [{"egp_id": "FIX", "result": "complete", "cells": [CELL], "note": None}], sort_keys=False)
            canonical.run(run, {})
            cell_id = read_jsonl(run / "canonical/canonical_cells.jsonl")[0]["canonical_cell_id"]
            fold_manifest = run / "fold.json"
            write_json(
                fold_manifest,
                {
                    "fold_id": "SMALL_FIXTURE_FOLD",
                    "require_exact_inventory": True,
                    "development_cell_ids": [cell_id],
                    "compositional_holdout_cell_ids": [],
                    "novel_feature_holdout_cell_ids": [],
                },
            )
            fold_setting = {"fold_manifest": str(fold_manifest)}
            realisation.run(run, {})
            (run / "items").mkdir()
            item_settings = settings["items"]
            generated = items.generate_items(
                run / "items",
                run,
                family_prompt_path=item_settings["family_prompt"],
                bank_config_path=item_settings["bank_config"],
                repeated_diagnostics=item_settings["validation"]["repeated_diagnostics"],
            )
            candidates = read_jsonl(run / "items/generation/candidate_items.jsonl")
            (run / "items/validation").mkdir()
            write_jsonl(run / "items/validation/accepted_items.jsonl", candidates)
            simulation_summary = simulation.run(run, {**settings["simulation"], **fold_setting})
            kc_selection.run(run, {**settings["kc_selection"], **fold_setting})
            kc.run(run, {**settings["kc"], **fold_setting})
            q_summary = qmatrix.run(run)
            kt_summary = kt.run(run, {**settings["kt"], **fold_setting, "techniques": ["empirical", "bkt"]})
            self.assertEqual(generated["candidate_items"], 3)
            self.assertEqual(q_summary, {"rows": 3, "covered_rows": 3, "uncovered_rows": 0, "columns": 1, "edges": 3})
            self.assertEqual(simulation_summary["events_per_learner"], 6)
            self.assertEqual(kt_summary["oracle_input"], False)
            trace = subprocess.run(
                [sys.executable, "scripts/inspect.py", "trace", candidates[0]["item_id"], "--run", str(run)],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(trace.returncode, 0, trace.stderr)
            self.assertIn('"canonical_cell"', trace.stdout)
            validation = subprocess.run(
                [sys.executable, "scripts/validate.py", str(run)],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(validation.returncode, 0, validation.stdout + validation.stderr)


class KCSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = read_json(ROOT / "modules/kc_selection/fixtures/core.json")
        self.config = read_json(ROOT / "modules/kc_selection/configs/deterministic_v0.json")
        self.frames = {
            row["predicate_frame_id"]: row
            for row in read_jsonl(realisation.LEXICON)
        }

    def discover(self, fixture: dict | None = None) -> tuple[dict, dict]:
        fixture = fixture or self.fixture
        partition = kc_selection.partition_inputs(
            fixture["canonical_cells"], fixture.get("realisations", []), fixture["cell_splits"]
        )
        discovery = kc_candidates.discover_candidates(
            partition["development_cells"],
            partition["development_realisations"],
            self.frames,
            self.config,
        )
        return partition, discovery

    def test_selection_is_deterministic_and_policy_compiles_for_materializer(self) -> None:
        first = kc_selection.evaluate_fixture(copy.deepcopy(self.fixture), self.config)
        second = kc_selection.evaluate_fixture(copy.deepcopy(self.fixture), self.config)
        self.assertEqual(first, second)
        self.assertTrue(first["objective"]["feasible"])

        partition, discovery = self.discover()
        selection = kc_selection.select_inventory(discovery, self.config)
        policy = kc_selection.compile_policy(selection, partition["development_cell_ids"])
        opportunities = []
        cells_by_id = {row["canonical_cell_id"]: row for row in partition["development_cells"]}
        for cell_id in partition["development_cell_ids"]:
            nuisance = kc_candidates.nuisance_opportunities(cells_by_id[cell_id], self.frames)[0]
            opportunities.append(
                {
                    **nuisance,
                    "source_descriptor_ids": cells_by_id[cell_id]["source_descriptor_ids"],
                    "source_mapping_notes": cells_by_id[cell_id]["source_mapping_notes"],
                }
            )
        projections, cards = kc.materialize_inventory(policy, opportunities)
        self.assertTrue(cards)
        self.assertTrue(all(row["kc_ids"] for row in projections))
        self.assertEqual(
            {rule["kc_id"] for rule in policy["rules"]},
            {row["kc_id"] for row in cards},
        )

    def test_factorized_dev_frozen_uses_development_item_support_only(self) -> None:
        partition, _discovery = self.discover()
        opportunities = items.build_item_opportunities(
            self.fixture["canonical_cells"],
            self.frames,
            read_json(ROOT / "modules/items/configs/fixed_bank_v0.json"),
        )
        bank = fixture_runtime_items(items.construct_items(
            opportunities,
            self.frames,
            (ROOT / "modules/items/families/controlled_transformation.txt").read_text(
                encoding="utf-8"
            ),
        ), self.fixture)
        development_items = [
            row
            for row in bank
            if row["canonical_split"] == "development"
        ]
        first, support = kc_selection.development_frozen_factorized_policy(
            ROOT / "modules/kc/policies/factorized.json",
            partition["development_cells"],
            development_items,
        )
        heldout_mutated = copy.deepcopy(bank)
        for row in heldout_mutated:
            if row["canonical_split"] != "development":
                row["realization_evidence"]["operations"] = ["heldout_only_operation"]
                row["source_descriptor_ids"] = ["HELDOUT_MUTATION"]
        second, second_support = kc_selection.development_frozen_factorized_policy(
            ROOT / "modules/kc/policies/factorized.json",
            partition["development_cells"],
            [
                row
                for row in heldout_mutated
                if row["canonical_split"] == "development"
            ],
        )
        self.assertEqual(first, second)
        self.assertEqual(support, second_support)
        selected = {rule["kc_id"] for rule in first["rules"]}
        self.assertNotIn("KC_MODAL_WOULD", selected)
        self.assertIn("KC_ASPECT_PERFECT", selected)
        self.assertFalse(first["selection_metadata"]["held_out_content_used"])

    def test_perfect_progressive_components_and_duplicate_alternatives_are_explicit(self) -> None:
        _partition, discovery = self.discover()
        candidates = {row["kc_id"]: row for row in discovery["candidates"]}
        self.assertEqual(
            candidates["KC_ASPECT_PERFECT"]["activation_rule"],
            {"cell": {"aspect": ["perfect", "perfect_progressive"]}},
        )
        self.assertEqual(
            candidates["KC_ASPECT_PROGRESSIVE"]["activation_rule"],
            {"cell": {"aspect": ["progressive", "perfect_progressive"]}},
        )
        self.assertEqual(
            candidates["KC_ASPECT_PERFECT_PROGRESSIVE_ATOMIC"]["activation_rule"],
            {"cell": {"aspect": "perfect_progressive"}},
        )
        equivalent_kc_sets = [set(row["member_kc_ids"]) for row in discovery["equivalence_classes"]]
        self.assertTrue(
            any(
                {"KC_ASPECT_PERFECT_PROGRESSIVE_ATOMIC", "KC_INT_PERFECT_PROGRESSIVE_CHAIN"}
                <= members
                for members in equivalent_kc_sets
            )
        )
        self.assertTrue(
            any(
                {"KC_QUESTION_GENERIC", "KC_POLAR_QUESTION", "KC_OP_OPERATOR_INVERSION"}
                <= members
                for members in equivalent_kc_sets
            )
        )

    def test_heldout_contents_and_support_cannot_change_selection(self) -> None:
        partition, discovery = self.discover()
        self.assertEqual(
            {row["canonical_cell_id"] for row in discovery["activations"]},
            set(partition["development_cell_ids"]),
        )
        operation_probe = copy.deepcopy(self.fixture)
        operation_probe["realisations"] = [
            {
                "spec": {
                    "canonical_cell_id": "CELL_FIX_PERFECT_PASSIVE",
                    "realization_id": "REAL_HELDOUT_PROBE",
                },
                "derivation": {"operations": ["heldout_only_operation"]},
            }
        ]
        probe_partition = kc_selection.partition_inputs(
            operation_probe["canonical_cells"],
            operation_probe["realisations"],
            operation_probe["cell_splits"],
        )
        self.assertEqual(probe_partition["development_realisations"], [])
        original = kc_selection.evaluate_fixture(copy.deepcopy(self.fixture), self.config)
        changed = copy.deepcopy(self.fixture)
        for row in changed["canonical_cells"]:
            if row["canonical_cell_id"] == "CELL_FIX_PERFECT_PASSIVE":
                row["cell"] = {
                    "tense": "past", "aspect": "progressive", "voice": "active",
                    "polarity": "negative", "clause": "polar_question", "modal": "none",
                }
                row["source_descriptor_ids"] = ["HELDOUT_A", "HELDOUT_B"]
                row["source_mapping_notes"] = {"HELDOUT_A": "changed", "HELDOUT_B": "changed"}
            elif row["canonical_cell_id"] == "CELL_FIX_WOULD":
                row["cell"] = {
                    "tense": "NA", "aspect": "none", "voice": "passive",
                    "polarity": "negative", "clause": "declarative", "modal": "can",
                }
                row["source_descriptor_ids"] = ["HELDOUT_C"]
                row["source_mapping_notes"] = {"HELDOUT_C": None}
        mutated = kc_selection.evaluate_fixture(changed, self.config)
        self.assertEqual(original["selected_policy"], mutated["selected_policy"])
        self.assertNotEqual(original["evaluation"]["split_audit"], mutated["evaluation"]["split_audit"])

    def test_scope_invariance_keeps_varying_operations_diagnostic_only(self) -> None:
        _partition, discovery = self.discover()
        diagnostics = {row["kc_id"]: row for row in discovery["diagnostics"]}
        self.assertEqual(diagnostics["KC_OP_DO_SUPPORT"]["scope"], "realisation")
        self.assertTrue(diagnostics["KC_OP_DO_SUPPORT"]["scope_mixed_cell_ids"])
        self.assertFalse(diagnostics["KC_OP_DO_SUPPORT"]["selection_eligible"])
        self.assertEqual(diagnostics["KC_OP_BE_PASSIVE"]["scope"], "cell")
        self.assertFalse(diagnostics["KC_OP_BE_PASSIVE"]["selection_eligible"])
        self.assertIn(
            "collapsed into an identical development activation class",
            diagnostics["KC_OP_BE_PASSIVE"]["rejection_reasons"],
        )

    def test_interactions_require_parents_and_residual_structure(self) -> None:
        _partition, discovery = self.discover()
        candidates = {row["kc_id"]: row for row in discovery["candidates"]}
        diagnostics = {row["kc_id"]: row for row in discovery["diagnostics"]}
        interaction = candidates["KC_INT_PERFECT_PROGRESSIVE_CHAIN"]
        parent_kcs = {
            next(row["kc_id"] for row in discovery["candidates"] if row["candidate_id"] == parent_id)
            for parent_id in interaction["requires_selected_ids"]
        }
        self.assertEqual(parent_kcs, {"KC_ASPECT_PERFECT", "KC_ASPECT_PROGRESSIVE"})
        self.assertEqual(
            diagnostics["KC_INT_PERFECT_PROGRESSIVE_CHAIN"]["residual_realization_facts"],
            ["chain_edge:perfect>progressive"],
        )
        self.assertFalse(diagnostics["KC_INT_PERFECT_PROGRESSIVE_CHAIN"]["selection_eligible"])
        no_residual = diagnostics["KC_INT_PERFECT_PASSIVE_CHAIN"]
        self.assertIn("conjunction has no stable residual realization/dependency fact", no_residual["rejection_reasons"])

    def test_frozen_policy_composes_but_does_not_invent_novel_feature_kcs(self) -> None:
        result = kc_selection.evaluate_fixture(copy.deepcopy(self.fixture), self.config)
        policy = result["selected_policy"]
        evaluation = result["evaluation"]
        compositional = evaluation["selected_ontology"]["compositional_holdout"]
        novel = evaluation["selected_ontology"]["novel_feature_holdout"]
        self.assertEqual(compositional["coverage"], 1.0)
        self.assertEqual(compositional["fact_recall"], 1.0)
        self.assertEqual(compositional["component_reuse"], 1.0)
        self.assertEqual(novel["coverage"], 0.0)
        self.assertEqual(novel["fact_recall"], 0.0)
        self.assertEqual(evaluation["split_audit"]["status"], "PASS")
        self.assertEqual(evaluation["split_audit"]["compositional_holdout"]["misclassified_cell_ids"], [])
        self.assertEqual(evaluation["split_audit"]["novel_feature_holdout"]["misclassified_cell_ids"], [])
        self.assertTrue(evaluation["selected_ontology"]["absence_of_full_cell_memorisation"])
        baselines = {row["label"]: row for row in evaluation["baselines"]}
        self.assertIn("CURRENT_FACTORIZED", baselines)
        self.assertIn("CURRENT_FACTORIZED_PLUS_INTERACTIONS", baselines)
        self.assertIn("FULL_CELL_ALL_TRANSDUCTIVE", baselines)
        self.assertEqual(baselines["FULL_CELL_DEV_FROZEN"]["compositional_holdout"]["coverage"], 0.0)
        self.assertFalse(baselines["FULL_CELL_DEV_FROZEN"]["absence_of_full_cell_memorisation"])
        negation_equivalence = next(
            row
            for row in evaluation["post_freeze_equivalence_diagnostics"]
            if {"KC_NEGATION", "KC_OP_NEGATION_PLACEMENT"} <= set(row["member_kc_ids"])
        )
        self.assertEqual(negation_equivalence["development_conclusion"], "unidentifiable: identical activation columns")
        self.assertTrue(negation_equivalence["holdout_results_are_evaluation_only"])
        self.assertIn(
            "CELL_FIX_NEGATIVE_IMPERATIVE",
            negation_equivalence["holdout"]["compositional_holdout"]["separating_cell_ids"],
        )
        self.assertEqual(evaluation["held_out_cell_ids_referenced_by_selected_policy"], [])
        serialized = json.dumps(policy, sort_keys=True)
        self.assertNotIn("CELL_FIX_PERFECT_PASSIVE", serialized)
        self.assertNotIn("CELL_FIX_WOULD", serialized)


if __name__ == "__main__":
    unittest.main()
