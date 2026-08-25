from __future__ import annotations

import copy
import unittest

from grammar_kt.evaluation import kt, simulation
from grammar_kt.io import ROOT, read_json
from grammar_kt.knowledge import policy
from grammar_kt.records import observable_base_event

from .helpers import paired_accepted_items


class SimulationInvarianceTests(unittest.TestCase):
    def _simulate(self, item, opportunity):
        item = {**item, "canonical_split": "development"}
        params = simulation.load_simulation_parameters(
            "modules/evaluation/simulation/configs/structural_oracle_v0.json"
        )
        params.update(
            {
                "seed": 77,
                "learners_per_profile": 1,
                "item_passes_per_learner": 2,
                "profiles": {"mixed": params["profiles"]["mixed"]},
            }
        )
        projections, feature_ids = simulation.project_oracle_items([item], [opportunity], params)
        oracle_by_item = {item["item_id"]: projections[0]["oracle_feature_ids"]}
        observed, _oracle, _learners, _private = simulation.simulate_records(
            params,
            {item["item_id"]: item},
            oracle_by_item,
            feature_ids,
            1,
            2,
        )
        return observed, projections

    def test_surface_generator_does_not_change_difficulty_or_outcomes(self) -> None:
        opportunity, standalone, dialogue = paired_accepted_items()
        left, left_projection = self._simulate(standalone, opportunity)
        right, right_projection = self._simulate(dialogue, opportunity)
        self.assertNotEqual(standalone["item_id"], dialogue["item_id"])
        self.assertEqual(
            [(row["measurement_opportunity_id"], row["item_difficulty"], row["correct"]) for row in left],
            [(row["measurement_opportunity_id"], row["item_difficulty"], row["correct"]) for row in right],
        )
        self.assertEqual(
            simulation.opportunity_outcome_fingerprint(left),
            simulation.opportunity_outcome_fingerprint(right),
        )
        self.assertEqual(left_projection[0]["oracle_feature_ids"], right_projection[0]["oracle_feature_ids"])

    def test_simulation_oracle_does_not_read_candidate_policy(self) -> None:
        opportunity, standalone, _ = paired_accepted_items()
        observed_before, _ = self._simulate(standalone, opportunity)
        factorized = policy.load_policy(ROOT / "modules/knowledge/policies/factorized.json")
        full_cell = policy.load_policy(ROOT / "modules/knowledge/policies/full_cell.json")
        self.assertNotEqual(
            policy.apply_policy(factorized, opportunity)["activated_kcs"],
            policy.apply_policy(full_cell, opportunity)["activated_kcs"],
        )
        observed_after, _ = self._simulate(standalone, opportunity)
        self.assertEqual(observed_before, observed_after)


class FrozenKTTests(unittest.TestCase):
    def test_kt_projection_rejects_oracle_fields(self) -> None:
        row = {
            "event_id": "EVENT_1",
            "learner_id": "L1",
            "item_id": "ITEM_1",
            "measurement_opportunity_id": "OPP_1",
            "canonical_cell_id": "CELL_1",
            "canonical_split": "development",
            "sequence_index": 1,
            "timestamp": "2026-01-01T00:00:00+00:00",
            "correct": 1,
            "item_difficulty": 0.0,
            "dataset_split": "train",
            "pre_mastery": {"ORACLE_1": 0.5},
        }
        with self.assertRaisesRegex(ValueError, "leakage"):
            observable_base_event(row)
        with self.assertRaisesRegex(ValueError, "leakage"):
            kt.project_interactions(
                [row],
                [
                    {
                        "item_id": "ITEM_1",
                        "measurement_opportunity_id": "OPP_1",
                        "canonical_cell_id": "CELL_1",
                        "canonical_split": "development",
                        "kc_ids": ["KC_1"],
                    }
                ],
            )

    def test_probe_order_cannot_change_frozen_state(self) -> None:
        fixture = read_json("modules/evaluation/kt/fixtures/compositional_probe.json")
        second = {
            **fixture["probe_events"][0],
            "event_id": "PROBE_2",
            "sequence_index": 4,
            "timestamp": "2027-01-01T00:04:00+00:00",
        }
        probes = [fixture["probe_events"][0], second]
        first_projection = kt.project_compositional_interactions(
            fixture["acquisition_events"], probes, fixture["item_projections"]
        )
        reversed_projection = kt.project_compositional_interactions(
            fixture["acquisition_events"], list(reversed(probes)), fixture["item_projections"]
        )
        first_acquisition, first_probes, first_supported, first_counts = first_projection
        second_acquisition, second_probes, second_supported, second_counts = reversed_projection
        self.assertEqual(first_acquisition, second_acquisition)
        self.assertEqual(first_supported, second_supported)
        self.assertEqual(first_counts, second_counts)
        self.assertEqual(
            {row["event_id"]: row["opportunity_indices"] for row in first_probes},
            {row["event_id"]: row["opportunity_indices"] for row in second_probes},
        )
        self.assertEqual(
            kt.frozen_development_statistics(first_acquisition),
            kt.frozen_development_statistics(second_acquisition),
        )

    def test_cold_and_zero_kc_fallbacks_remain_defined(self) -> None:
        fixture = read_json("modules/evaluation/kt/fixtures/compositional_probe.json")
        projections = copy.deepcopy(fixture["item_projections"])
        projections[1]["kc_ids"] = ["KC_COLD"]
        acquisition, probes, supported, _ = kt.project_compositional_interactions(
            fixture["acquisition_events"], fixture["probe_events"], projections
        )
        self.assertEqual(supported, {"KC_COMPONENT"})
        self.assertEqual(probes[0]["cold_kc_ids"], ["KC_COLD"])
        projections[1]["kc_ids"] = []
        _acquisition, zero_probes, _supported, _ = kt.project_compositional_interactions(
            fixture["acquisition_events"], fixture["probe_events"], projections
        )
        self.assertFalse(zero_probes[0]["covered"])


if __name__ == "__main__":
    unittest.main()
