from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from grammar_kt.grammar.canonical import build
from grammar_kt.io import ROOT, read_json, read_jsonl, sha256_file, write_json, write_jsonl
from grammar_kt.runner import STAGE_NAMES, run_experiment

from .helpers import PAST_NEGATIVE


class FixtureEndToEndTests(unittest.TestCase):
    def test_complete_five_module_pipeline(self) -> None:
        cell_id = build(
            [{"egp_id": "E1", "result": "complete", "cells": [PAST_NEGATIVE], "note": None}]
        )[0][0]["canonical_cell_id"]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_path = root / "source.jsonl"
            write_jsonl(
                source_path,
                [
                    {
                        "egp_id": "E1",
                        "supercategory": "VERBS",
                        "subcategory": "past",
                        "guideword": "PAST NEGATIVE",
                        "can_do": "Can use the negative past.",
                        "examples": ["She did not work."],
                    }
                ],
                sort_keys=False,
            )
            (root / "ids.txt").write_text("E1\n", encoding="utf-8")
            write_jsonl(root / "metadata.jsonl", [{"egp_id": "E1"}])
            write_jsonl(
                root / "units.jsonl",
                [{"unit_id": "U1", "egp_id": "E1", "duplicate_of": None}],
            )
            response = root / "normalisation_response.json"
            write_json(
                response,
                {"egp_id": "E1", "result": "complete", "cells": [PAST_NEGATIVE], "note": None},
            )
            normalisation_backend = root / "normalisation_backend.json"
            write_json(
                normalisation_backend,
                {"kind": "fixture_file", "response_file": str(response)},
            )
            measurement_config = root / "measurement.json"
            write_json(
                measurement_config,
                {
                    "measurement_policy_id": "FIXTURE_MEASUREMENT",
                    "include_predicate_class_contrasts": False,
                    "include_agreement_variants": False,
                },
            )
            fold = root / "fold.json"
            write_json(
                fold,
                {
                    "fold_id": "FIXTURE_FOLD",
                    "require_exact_inventory": True,
                    "require_all_declared_cells": True,
                    "development_cell_ids": [cell_id],
                    "compositional_holdout_cell_ids": [],
                    "novel_feature_holdout_cell_ids": [],
                },
            )
            fold_setting = {"fold_manifest": str(fold)}
            settings = {
                "experiment": "fixture_e2e",
                "source": {
                    "path": str(source_path),
                    "sha256": sha256_file(source_path),
                    "records": 1,
                    "selected_descriptors": 1,
                    "sample_ids": str(root / "ids.txt"),
                    "sample_metadata": str(root / "metadata.jsonl"),
                    "annotation_units": str(root / "units.jsonl"),
                },
                "normalisation": {
                    "phase1_prompt": "modules/grammar/normalisation/prompts/phase1.txt",
                    "phase2_prompt": "modules/grammar/normalisation/prompts/phase2.txt",
                    "backend_config": str(normalisation_backend),
                    "workers": 1,
                    "max_attempts": 1,
                },
                "canonical": {},
                "measurement": {"config": str(measurement_config)},
                "generation": {
                    "generator": "modules/generation/generators/llm_standalone_fixture_v0.yaml",
                    "validation": "modules/generation/validation/blind_fixture_v0.yaml",
                },
                "knowledge_selection": {
                    **fold_setting,
                    "mode": "structural",
                    "config": "modules/knowledge/selection/configs/deterministic_v0.json",
                },
                "knowledge": fold_setting,
                "qmatrix": {},
                "simulation": {
                    **fold_setting,
                    "parameters": "modules/evaluation/simulation/configs/structural_oracle_v0.json",
                    "seed": 42,
                },
                "kt": {
                    **fold_setting,
                    "parameters": "modules/evaluation/kt/configs/default.json",
                    "techniques": ["empirical", "bkt"],
                },
            }
            with patch("grammar_kt.runner.load_experiment", return_value=(settings, None)):
                run = run_experiment("fixture_e2e", runs_root=root / "runs")

            metadata = read_json(run / "metadata.json")
            self.assertEqual(set(metadata["stages"]), set(STAGE_NAMES))
            self.assertEqual(read_json(run / "generation/validation_report.json")["status"], "PASS")
            self.assertEqual(len(read_jsonl(run / "generation/accepted_items.jsonl")), 1)
            self.assertEqual(read_json(run / "qmatrix/audit.json")["status"], "PASS")
            self.assertEqual(read_json(run / "simulation/audit.json")["status"], "PASS")
            self.assertFalse(read_json(run / "kt/metrics.json")["oracle_used"])
            checked = subprocess.run(
                [sys.executable, "scripts/validate.py", str(run)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)


if __name__ == "__main__":
    unittest.main()
