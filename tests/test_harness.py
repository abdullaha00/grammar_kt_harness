from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from grammar_kt import STAGES, canonical, item_generation, kc, qmatrix, realisation, simulation
from grammar_kt.backend import get_backend, save_model_result
from grammar_kt.config import changed_values, resolve_experiment
from grammar_kt.io import read_json, read_jsonl, write_json, write_jsonl
from grammar_kt.normalisation import render_prompt
from grammar_kt.normalisation_validation import validate_mapping, validate_phase2_transition
from grammar_kt.runner import RUNNERS, prepared_config, run_experiment


CELL = {"tense": "past", "aspect": "none", "voice": "active", "polarity": "positive", "clause": "declarative", "modal": "none"}


class ExperimentTests(unittest.TestCase):
    def test_inheritance_changes_only_declared_component(self) -> None:
        base = resolve_experiment("base")
        variant = resolve_experiment("kc_full_cell")
        self.assertEqual(variant.parent, "base")
        self.assertEqual(variant.resolved["kc"]["policy"], "full_cell")
        changes = changed_values(base.resolved, variant.resolved)
        self.assertEqual({row["path"] for row in changes}, {"experiment", "kc.policy"})

    def test_pipeline_order_is_defined_once_without_numbered_modules(self) -> None:
        self.assertEqual(STAGES, ["source", "normalisation", "canonical", "realisation", "kc", "items", "simulation", "kt"])
        self.assertEqual(list(RUNNERS), STAGES)
        self.assertFalse(list((ROOT / "modules").glob("stage_*")), "legacy numbered modules remain")

    def test_baseline_declares_accepted_design_counts(self) -> None:
        config = resolve_experiment("base").resolved
        expected = read_json(ROOT / "reference/current/expected_counts.json")
        self.assertEqual(config["source"]["selected_descriptors"], expected["unique_source_descriptors"])
        self.assertEqual(config["kc"]["policy"], "factorized")
        self.assertEqual(config["simulation"]["learners"], expected["learners"])
        self.assertEqual(config["simulation"]["events_per_learner"], expected["events_per_learner"])

    def test_from_stage_reuse_is_explicit_and_records_parent(self) -> None:
        resolution = resolve_experiment("kc_full_cell")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            parent = root / "base"
            for stage in STAGES[:STAGES.index("kc")]:
                (parent / stage).mkdir(parents=True)
                (parent / stage / "marker.txt").write_text(stage, encoding="utf-8")

            def fake(stage: str):
                def execute(run: Path, _config: dict) -> dict:
                    (run / stage).mkdir()
                    return {"stage": stage}
                return execute

            replacements = {stage: fake(stage) for stage in STAGES[STAGES.index("kc"): ]}
            def fake_q(run: Path) -> dict:
                (run / "qmatrix").mkdir()
                return {"stage": "qmatrix"}

            with patch("grammar_kt.runner.resolve_experiment", return_value=resolution), patch.dict(RUNNERS, replacements), patch("grammar_kt.runner.qmatrix.run", side_effect=fake_q):
                output = run_experiment("kc_full_cell", from_stage="kc", runs_root=root)
            metadata = read_json(output / "metadata.json")
            self.assertEqual(metadata["reused_from"]["run"], "base")
            self.assertEqual(metadata["stages"]["realisation"]["status"], "reused")
            self.assertEqual(metadata["stages"]["kc"]["status"], "executed")


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
        config = resolve_experiment("base").resolved["normalisation"]
        record = read_jsonl(ROOT / "modules/normalisation/fixtures/core.jsonl")[0]
        prompt = render_prompt(1, config, {"record": record})
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
            result = get_backend("fixture_file").invoke(prompt="EXACT PROMPT\n", output_schema=schema, instructions=instructions, unit_dir=unit, config={"backend": "fixture_file", "response_file": str(response)})
            save_model_result(unit, json.loads(result.raw_path.read_text()), [])
            self.assertEqual((unit / "rendered_prompt.txt").read_text(), "EXACT PROMPT\n")
            for name in ("input.json", "invocation.json", "raw_output.txt", "parsed_output.json", "validation.json"):
                self.assertTrue((unit / name).is_file())
            self.assertNotIn("prompt_sha256", read_json(unit / "invocation.json"))


class ComponentTests(unittest.TestCase):
    def test_canonical_deduplicates_only_complete_cells(self) -> None:
        mappings = [
            {"egp_id": "A", "result": "complete", "cells": [CELL], "note": None},
            {"egp_id": "B", "result": "complete", "cells": [dict(CELL)], "note": None},
            {"egp_id": "C", "result": "partial", "cells": [{**CELL, "tense": ["past"]}], "note": "phase2 eligible: tense"},
        ]
        cells, edges = canonical.build(mappings)
        self.assertEqual((len(cells), len(edges)), (1, 2))

    def test_realisation_and_kc_run_one(self) -> None:
        fixture = read_jsonl(ROOT / "modules/realisation/fixtures/core.jsonl")[0]
        config = resolve_experiment("base").resolved
        result = realisation.run_one(fixture, config["realisation"])
        self.assertTrue(result["valid"])
        opportunity = read_json(ROOT / "modules/kc/fixtures/perfect_progressive.json")
        factorized = kc.run_one(opportunity, "factorized")
        interactions = kc.run_one(opportunity, "factorized_plus_interactions")
        self.assertEqual(factorized["output"]["kc_ids"], ["KC_ASPECT_PERFECT", "KC_ASPECT_PROGRESSIVE", "KC_FINITE_PRESENT"])
        self.assertIn("KC_INT_PERFECT_PROGRESSIVE_CHAIN", interactions["output"]["kc_ids"])

    def test_new_supported_policy_requires_no_python_change(self) -> None:
        opportunity = read_json(ROOT / "modules/kc/fixtures/perfect_progressive.json")
        with tempfile.TemporaryDirectory() as temporary:
            policy = Path(temporary) / "new_policy.json"
            policy.write_text(json.dumps({"policy_id": "TEST", "kind": "rules", "rules": [{"kc_id": "KC_TEST", "name": "test", "definition": "test", "activation_rule": {"cell": {"aspect": "perfect_progressive"}}, "required_conditions": [], "includes": [], "excludes": [], "realization_dependencies": [], "near_neighbours": [], "rationale": "test"}]}), encoding="utf-8")
            self.assertEqual(kc.run_one(opportunity, str(policy))["output"]["kc_ids"], ["KC_TEST"])

    def test_generic_run_one_cli(self) -> None:
        result = subprocess.run([sys.executable, "scripts/run_one.py", "kc", "--fixture", "perfect_progressive", "--policy", "factorized"], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("=== BEFORE ===", result.stdout)
        self.assertIn("KC_ASPECT_PERFECT", result.stdout)

    def test_qmatrix_is_derived_from_frozen_projection(self) -> None:
        item = {"item_id": "ITEM_A", "canonical_cell_id": "CELL_A", "all_kc_ids": ["KC_A"], "realization_spec": {"realization_id": "REAL_A"}, "source_descriptor_ids": ["E"]}
        card = {"kc_id": "KC_A", "activation_rule": {"cell": {"tense": "past"}}}
        projection = {"canonical_cell_id": "CELL_A", "kc_ids": ["KC_A"]}
        columns, rows, edges, audit = qmatrix.build([item], [card], [projection])
        self.assertEqual((columns, rows, len(edges), audit["status"]), (["KC_A"], [("ITEM_A", [1])], 1, "PASS"))

    def test_simulation_observable_has_no_oracle_fields(self) -> None:
        config = resolve_experiment("base").resolved["simulation"]
        result = simulation.run_one("L0001", config)
        for row in result["observable_interactions"]:
            self.assertFalse(simulation.FORBIDDEN_OBSERVABLE & set(row))

    def test_small_fixture_pipeline_through_qmatrix(self) -> None:
        config = prepared_config(resolve_experiment("base"))
        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary)
            (run / "normalisation").mkdir()
            write_jsonl(run / "normalisation/final_mappings.jsonl", [{"egp_id": "FIX", "result": "complete", "cells": [CELL], "note": None}], sort_keys=False)
            canonical.run(run, {})
            realisation.run(run, config["realisation"])
            kc.run(run, config["kc"])
            (run / "items").mkdir()
            generated = item_generation.run_generation(run / "items", run, config["items"])
            candidates = read_jsonl(run / "items/generation/candidate_items.jsonl")
            (run / "items/validation").mkdir()
            write_jsonl(run / "items/validation/accepted_items.jsonl", candidates)
            q_summary = qmatrix.run(run)
            self.assertEqual(generated["candidate_items"], 5)
            self.assertEqual(q_summary, {"rows": 5, "columns": 1, "edges": 5})


if __name__ == "__main__":
    unittest.main()
