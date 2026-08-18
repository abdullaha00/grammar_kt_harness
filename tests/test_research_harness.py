from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import yaml

from modules.stage_5_kc.policy import explain_policy, load_policy, materialize
from scripts.compare_runs import compare_normalization
from shared.utils.config import diff_values, resolve_experiment
from shared.utils.contracts import validate_value
from shared.utils.experiment import ensure_run_metadata
from shared.utils.io import ROOT, read_json, read_jsonl, write_json
from shared.utils.model_backend import get_backend
from shared.utils.model_units import begin_attempt, begin_model_unit, completed_model_unit, finish_attempt, invocation_reuse_key, select_attempt
from shared.utils.stages import DEPENDENCIES, MODULE_PACKAGE_DIRS, STAGES, stage_config


class ExperimentTests(unittest.TestCase):
    def test_short_name_inheritance_and_direct_diff(self) -> None:
        current = resolve_experiment("current")
        variant = resolve_experiment("full_cell")
        self.assertEqual(current.resolved["kc"]["policy"], "factorized")
        self.assertEqual(variant.resolved["kc"]["policy"], "full_cell")
        changes = diff_values(variant.parent_resolved, variant.resolved)
        self.assertEqual(
            {row["path"] for row in changes},
            {"experiment_id", "kc.policy"},
        )

    def test_manifest_and_parent_diff_are_written_before_stage_work(self) -> None:
        resolution = resolve_experiment("kt_bkt_only")
        with tempfile.TemporaryDirectory() as temporary:
            run, manifest = ensure_run_metadata(resolution, run_dir=Path(temporary) / "run")
            self.assertTrue(manifest.is_file())
            diff = read_json(run / "diff_from_parent.json")
            self.assertEqual(
                {row["path"] for row in diff["changed"]},
                {"kt.techniques"},
            )

    def test_reference_manifest_retains_accepted_operational_design(self) -> None:
        config = resolve_experiment("current").resolved
        expected = read_json(ROOT / "reference/current/expected_counts.json")
        self.assertEqual(config["kc"]["policy"], "factorized")
        self.assertEqual(config["simulation"]["learners"], expected["learners"])
        self.assertEqual(config["simulation"]["events_per_learner"], expected["events_per_learner"])
        self.assertEqual(config["kt"]["techniques"], ["empirical", "bkt", "logistic"])


class ModuleContractTests(unittest.TestCase):
    def test_package_directories_follow_numbered_pipeline_order(self) -> None:
        self.assertEqual(
            [MODULE_PACKAGE_DIRS[stage] for stage in STAGES],
            [f"stage_{index}_{stage}" for index, stage in enumerate(STAGES, start=1)],
        )

    def test_every_stage_has_four_part_contract(self) -> None:
        for stage in STAGES:
            path = ROOT / "modules" / MODULE_PACKAGE_DIRS[stage] / "contract.yaml"
            value = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertTrue({"input", "configuration", "procedure", "output"} <= set(value), stage)

    def test_declared_dependency_graph_is_strict(self) -> None:
        self.assertEqual(DEPENDENCIES["items"], ("realization", "kc"))
        self.assertEqual(DEPENDENCIES["qmatrix"], ("items", "kc"))
        self.assertEqual(DEPENDENCIES["simulation"], ("items", "qmatrix"))
        self.assertEqual(DEPENDENCIES["kt"], ("simulation",))
        item_code = "\n".join(
            (ROOT / "modules/stage_6_items" / name).read_text(encoding="utf-8")
            for name in ("generate.py", "validate.py")
        )
        self.assertNotIn('run_dir / "normalization"', item_code)
        q_code = (ROOT / "modules/stage_7_qmatrix/run.py").read_text(encoding="utf-8")
        self.assertNotIn('run_dir / "canonical"', q_code)
        self.assertNotIn("modules.stage_4_realization", q_code)
        kt_code = (ROOT / "modules/stage_9_kt/run.py").read_text(encoding="utf-8")
        self.assertNotIn("oracle_interactions", kt_code.lower())
        self.assertIn('"oracle_used": False', kt_code)

    def test_kc_stage_config_hashes_only_the_selected_policy(self) -> None:
        config = resolve_experiment("current").resolved
        scoped = stage_config("kc", config)
        self.assertEqual(scoped["policy"], "factorized")
        self.assertEqual(set(scoped["policies"]), {"factorized"})

    def test_run_one_defaults_are_local_and_isolated_from_current(self) -> None:
        from modules.stage_1_source import run_one as source
        from modules.stage_2_normalization import run_one as normalization
        from modules.stage_3_canonical import run_one as canonical
        from modules.stage_4_realization import run_one as realization
        from modules.stage_5_kc import run_one as kc
        from modules.stage_6_items import run_one as items
        from modules.stage_8_simulation import run_one as simulation

        defaults = (
            (source.DEFAULT_EGP_ID, source.DEFAULT_INPUT),
            (normalization.DEFAULT_EGP_ID, normalization.DEFAULT_INPUT),
            (canonical.DEFAULT_EGP_ID, canonical.DEFAULT_INPUT),
            (realization.DEFAULT_CELL_ID, realization.DEFAULT_INPUT),
            (kc.DEFAULT_CELL_ID, kc.DEFAULT_INPUT),
            (items.DEFAULT_OPPORTUNITY_ID, items.DEFAULT_INPUT),
            (simulation.DEFAULT_LEARNER_ID, simulation.DEFAULT_ITEMS),
            (simulation.DEFAULT_LEARNER_ID, simulation.DEFAULT_QMATRIX),
        )
        for identifier, path in defaults:
            self.assertTrue(identifier)
            self.assertTrue(path.is_file(), path)
            self.assertIn("fixtures", path.parts)
        self.assertEqual(
            {
                source.DEFAULT_EXPERIMENT,
                normalization.DEFAULT_EXPERIMENT,
                canonical.DEFAULT_EXPERIMENT,
                realization.DEFAULT_EXPERIMENT,
                kc.DEFAULT_EXPERIMENT,
                items.DEFAULT_EXPERIMENT,
                simulation.DEFAULT_EXPERIMENT,
            },
            {"run_one_demo"},
        )
        demo = resolve_experiment("run_one_demo")
        self.assertEqual(demo.resolved["experiment_id"], "run_one_demo")
        self.assertEqual(demo.parent_resolved["experiment_id"], "current")
        self.assertEqual(
            {row["path"] for row in diff_values(demo.parent_resolved, demo.resolved)},
            {"experiment_id", "source.path", "source.records", "source.sha256"},
        )

    def test_core_normalization_fixtures_are_typed_and_cover_named_cases(self) -> None:
        schema = ROOT / "modules/stage_1_source/schemas/source_descriptor.schema.json"
        rows = read_jsonl(ROOT / "modules/stage_2_normalization/fixtures/core.jsonl")
        for row in rows:
            validate_value(row, schema, label=row["fixture_label"])
        self.assertEqual(
            {row["fixture_label"] for row in rows},
            {
                "exact_simple_tense", "closed_present_past_ambiguity", "generic_modal",
                "generic_question", "imperative", "passive", "out_of_scope",
            },
        )


class ExplanationAndBackendTests(unittest.TestCase):
    def test_kc_explanation_covers_active_and_inactive_rules(self) -> None:
        opportunity = read_jsonl(ROOT / "modules/stage_5_kc/fixtures/core.jsonl")[3]
        policy = load_policy(ROOT / "modules/stage_5_kc/policies/factorized_v0.json")
        explanation = explain_policy(policy, opportunity)
        self.assertEqual(explanation["activated_kcs"], ["KC_FINITE_PRESENT", "KC_POLAR_QUESTION"])
        self.assertTrue(any(not row["activated"] for row in explanation["rules"]))
        projections, _ = materialize(policy, [opportunity])
        self.assertEqual(projections[0]["kc_ids"], explanation["activated_kcs"])

    def test_fixture_backend_writes_exact_invocation_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            response = root / "response.json"
            response.write_text('{"ok":true}\n', encoding="utf-8")
            schema = root / "schema.json"
            schema.write_text('{"type":"object"}\n', encoding="utf-8")
            instructions = root / "instructions.md"
            instructions.write_text("fixture instructions\n", encoding="utf-8")
            unit = root / "unit"
            begin_model_unit(unit, {"id": "one"})
            attempt = begin_attempt(unit, 1)
            backend_config = {"response_file": str(response), "backend": "fixture_file"}
            scientific_inputs: list[dict[str, object]] = []
            implementation: list[dict[str, object]] = []
            result = get_backend("fixture_file").invoke(
                prompt="EXACT PROMPT\n",
                output_schema=schema,
                instructions=instructions,
                raw_path=attempt / "raw_output.txt",
                log_dir=attempt,
                stem="one",
                config=backend_config,
                context={
                    "unit_id": "one",
                    "scientific_inputs": scientific_inputs,
                    "implementation": implementation,
                },
                invocation_dir=attempt,
            )
            parsed = json.loads(result.raw_path.read_text(encoding="utf-8"))
            finish_attempt(attempt, parsed=parsed, validation={"valid": True, "errors": []})
            select_attempt(unit, attempt)
            for name in (
                "input.json", "rendered_prompt.txt", "invocation.json",
                "raw_output.txt", "parsed_output.json", "validation.json",
            ):
                self.assertTrue((unit / name).is_file(), name)
            self.assertEqual((unit / "rendered_prompt.txt").read_text(encoding="utf-8"), "EXACT PROMPT\n")
            invocation = read_json(unit / "invocation.json")
            self.assertEqual(invocation["backend"], "fixture_file")
            self.assertIn("prompt_sha256", invocation)
            self.assertIn("schema", invocation)
            expected = invocation_reuse_key(
                prompt="EXACT PROMPT\n",
                config=backend_config,
                scientific_inputs=scientific_inputs,
                implementation=implementation,
            )
            self.assertTrue(completed_model_unit(unit, {"id": "one"}, expected))
            changed = invocation_reuse_key(
                prompt="CHANGED PROMPT\n",
                config=backend_config,
                scientific_inputs=scientific_inputs,
                implementation=implementation,
            )
            self.assertFalse(completed_model_unit(unit, {"id": "one"}, changed))

    def test_normalization_phase2_reuse_preserves_verbatim_json_order(self) -> None:
        from modules.stage_2_normalization.run import _annotate, _load_validator

        resolution = resolve_experiment("run_one_demo")
        config = dict(resolution.resolved["normalization"])
        validator = _load_validator(ROOT / config["validator"])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            response = root / "mapping.json"
            response.write_text(
                '{"egp_id":"FIX_REUSE","result":"partial","cells":'
                '[{"tense":"present","aspect":"none","voice":"active",'
                '"polarity":null,"clause":"declarative","modal":"none"}],'
                '"note":"phase2 eligible: none"}\n',
                encoding="utf-8",
            )
            config.update(
                {
                    "backend": "fixture_file",
                    "response_file": str(response),
                    "max_attempts": 1,
                }
            )
            output = root / "normalization"
            task = {
                "unit_id": "fixture_reuse",
                "egp_id": "FIX_REUSE",
                "duplicate_of": None,
                "record": {
                    "egp_id": "FIX_REUSE",
                    "supercategory": "VERBS",
                    "subcategory": "present simple",
                    "guideword": "PRESENT SIMPLE",
                    "can_do": "Can use the present simple for routines.",
                },
            }

            def annotate(phase: int, value: dict[str, object]) -> dict[str, object]:
                return _annotate(
                    phase=phase,
                    task=value,
                    config=config,
                    output=output,
                    parse_raw=validator.parse_raw_mapping,
                    validate_mapping=validator.validate_mapping,
                    validate_transition=validator.validate_phase2_transition,
                )

            phase1 = annotate(1, task)
            phase2_task = {
                **task,
                "phase1_mapping": phase1["mapping"],
                "examples": ["She works every day."],
            }
            annotate(2, phase2_task)
            reused_phase1 = annotate(1, task)
            self.assertTrue(reused_phase1["unit_reused"])
            self.assertEqual(
                list(reused_phase1["mapping"]),
                ["egp_id", "result", "cells", "note"],
            )
            reused_phase2 = annotate(
                2,
                {**phase2_task, "phase1_mapping": reused_phase1["mapping"]},
            )
            self.assertTrue(reused_phase2["unit_reused"])


class ComparisonTests(unittest.TestCase):
    def test_force_backups_are_not_counted_as_active_units(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            mapping = {
                "egp_id": "EGP_ONE",
                "result": "out_of_scope",
                "cells": [],
                "note": "fixture",
            }
            for run_name in ("a", "b"):
                units = root / run_name / "normalization/units"
                write_json(units / "u001/result.json", {"final_mapping": mapping})
                write_json(
                    units / "u001.backup-20260101T000000Z/result.json",
                    {"final_mapping": mapping},
                )
            comparison = compare_normalization(root / "a", root / "b")
            self.assertEqual(comparison["counts"]["run_a"], {"out_of_scope": 1})
            self.assertEqual(comparison["counts"]["run_b"], {"out_of_scope": 1})


if __name__ == "__main__":
    unittest.main()
