#!/usr/bin/env python3
"""Run one transformation from the five-module scientific architecture."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

sys.path.remove(str(Path(__file__).resolve().parent))

from grammar_kt.evaluation import kt, simulation
from grammar_kt.generation.generators import generate_items
from grammar_kt.generation.validation import validate_items
from grammar_kt.grammar import canonical, normalisation, source
from grammar_kt.io import ROOT, read_json, read_jsonl, read_yaml, repo_path
from grammar_kt.knowledge import policy, qmatrix, selection
from grammar_kt.measurement.opportunities import build_measurement_opportunities


FIXTURE_CELL = {
    "canonical_cell_id": "CELL_FIX_PAST_NEGATIVE",
    "cell": {
        "tense": "past", "aspect": "none", "voice": "active",
        "polarity": "negative", "clause": "declarative", "modal": "none",
    },
    "source_descriptor_ids": ["FIXTURE_EGP"],
    "source_mapping_notes": {"FIXTURE_EGP": None},
}


def show(before: object, after: object) -> None:
    print("=== BEFORE ===")
    print(json.dumps(before, ensure_ascii=False, indent=2, sort_keys=True))
    print("=== AFTER ===")
    print(json.dumps(after, ensure_ascii=False, indent=2, sort_keys=True, default=str))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "stage",
        choices=(
            "source", "normalisation", "canonical", "measurement", "generation",
            "validation", "selection", "policy", "qmatrix", "simulation", "kt",
        ),
    )
    parser.add_argument("--input", type=Path)
    parser.add_argument("--dialogue", action="store_true")
    parser.add_argument("--live", action="store_true", help="use configured live model backend")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    settings = read_yaml(ROOT / "experiments" / "base.yaml")
    supplied = read_json(args.input) if args.input else None

    if args.stage == "source":
        before = supplied or read_jsonl(ROOT / "modules/grammar/source/fixtures/core.jsonl")[0]
        after = source.phase1_record(before)
    elif args.stage == "normalisation":
        before = supplied or read_jsonl(ROOT / "modules/grammar/normalisation/fixtures/core.jsonl")[0]
        method = settings["normalisation"]
        backend = read_yaml(method["backend_config"])
        if not args.live:
            root = Path(tempfile.mkdtemp(prefix="grammar-kt-normalisation-fixture-"))
            response = root / "response.json"
            from grammar_kt.io import write_json
            write_json(
                response,
                {"egp_id": before["egp_id"], "result": "complete", "cells": [FIXTURE_CELL["cell"]], "note": None},
            )
            backend = {"kind": "fixture_file", "response_file": str(response)}
        after = normalisation.normalise_one(
            before,
            phase1_template=repo_path(method["phase1_prompt"]).read_text(encoding="utf-8"),
            phase2_template=repo_path(method["phase2_prompt"]).read_text(encoding="utf-8"),
            backend_config=backend,
            max_attempts=1,
            output=args.output,
            phase1_only=True,
        )
    elif args.stage == "canonical":
        before = supplied or {
            "egp_id": "FIXTURE_EGP", "result": "complete",
            "cells": [FIXTURE_CELL["cell"]], "note": None,
        }
        cells, edges = canonical.build([before.get("output", before)])
        after = {"cells": cells, "source_cell_edges": edges}
    else:
        opportunities = build_measurement_opportunities(
            [FIXTURE_CELL],
            {"include_predicate_class_contrasts": False, "include_agreement_variants": False},
        )
        opportunity = opportunities[0]
        if args.stage == "measurement":
            before, after = FIXTURE_CELL, opportunity
        elif args.stage in {"generation", "validation", "policy", "qmatrix", "simulation"}:
            generator = (
                "modules/generation/generators/llm_dialogue_v0.yaml"
                if args.dialogue and args.live
                else "modules/generation/generators/llm_dialogue_fixture_v0.yaml"
                if args.dialogue
                else "modules/generation/generators/llm_standalone_v0.yaml"
                if args.live
                else "modules/generation/generators/llm_standalone_fixture_v0.yaml"
            )
            generated = generate_items(opportunities, generator, evidence_root=args.output)
            item = generated["candidates"][0]
            if args.stage == "generation":
                before, after = opportunity, item
            else:
                validated = validate_items(
                    [item], opportunities,
                    "modules/generation/validation/blind_v0.yaml" if args.live else "modules/generation/validation/blind_fixture_v0.yaml",
                )
                accepted = validated["accepted"][0]
                if args.stage == "validation":
                    before, after = item, {"item": accepted, "report": validated["report"]}
                else:
                    accepted["canonical_split"] = "development"
                    selected_policy = policy.load_policy(ROOT / "modules/knowledge/policies/factorized.json")
                    projections, cards = policy.project_items([accepted], opportunities, selected_policy)
                    if args.stage == "policy":
                        before, after = {"opportunity": opportunity, "item": accepted}, {"projection": projections[0], "cards": cards}
                    elif args.stage == "qmatrix":
                        columns, rows, edges, audit = qmatrix.build([accepted], cards, projections)
                        before, after = projections, {"columns": columns, "rows": rows, "edges": edges, "audit": audit}
                    else:
                        parameters = simulation.load_simulation_parameters(settings["simulation"]["parameters"])
                        parameters.update({"seed": settings["simulation"]["seed"], "learners_per_profile": 1, "item_passes_per_learner": 2})
                        oracle_projection, feature_ids = simulation.project_oracle_items([accepted], opportunities, parameters)
                        oracle_by_item = {accepted["item_id"]: oracle_projection[0]["oracle_feature_ids"]}
                        observed, private, learners, _ = simulation.simulate_records(
                            parameters, {accepted["item_id"]: accepted}, oracle_by_item, feature_ids, 1, 2, target_learner="L0001"
                        )
                        before, after = {"opportunity": opportunity, "surface_item": accepted}, {"base_events": observed, "oracle_evidence": private, "learners": learners}
        elif args.stage == "selection":
            before = read_json(ROOT / "modules/knowledge/selection/fixtures/core.json")
            after = selection.evaluate_fixture(
                before, read_json(settings["knowledge_selection"]["config"])
            )
        elif args.stage == "kt":
            before = read_json(ROOT / "modules/evaluation/kt/fixtures/compositional_probe.json")
            acquisition, probes, supported, counts = kt.project_compositional_interactions(
                before["acquisition_events"], before["probe_events"], before["item_projections"]
            )
            states = kt.frozen_development_statistics(acquisition)
            after = {
                "development_supported_kc_ids": sorted(supported),
                "frozen_counts": {learner: dict(value) for learner, value in counts.items()},
                "frozen_states": states,
                "probes": probes,
                "probe_updates_candidate_state": False,
            }
        else:
            raise AssertionError(args.stage)
    show(before, after)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
